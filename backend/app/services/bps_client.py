"""Authenticated, bounded BPS transport. Never expose request URLs or exception text."""
import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import quote
import httpx

from app.config import Settings


class BPSError(Exception):
    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f'{stage}: {reason}')


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class BPSClient:
    def __init__(self, settings: Settings, transport=None, use_cache=False):
        settings.validate()
        self.settings = settings
        self.use_cache = use_cache
        self.network_successes = 0
        self.fetched_times = []
        self.last_request_at = None
        self.blocked = False
        self.request_lock = asyncio.Lock()
        # httpx INFO logging includes query parameters, including credentials.
        for name in ('httpx', 'httpcore'):
            logging.getLogger(name).disabled = True
        self.http = httpx.AsyncClient(base_url=settings.base_url, timeout=30,
                                     follow_redirects=False, transport=transport)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.http.aclose()

    def sanitize(self, value):
        if isinstance(value, dict):
            return {k: self.sanitize(v) for k, v in value.items()
                    if k.lower() not in ('key', 'api_key', 'bps_api_key', 'token')}
        if isinstance(value, list):
            return [self.sanitize(v) for v in value]
        if isinstance(value, str) and self.settings.api_key:
            for secret in (self.settings.api_key, quote(self.settings.api_key, safe='')):
                value = value.replace(secret, '[REDACTED]')
        return value

    def save(self, name, value):
        self.settings.cache.mkdir(parents=True, exist_ok=True)
        target = self.settings.cache / f'{name}.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(self.sanitize(value), ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, target)

    async def get(self, path, params, stage):
        if self.blocked:
            raise BPSError(stage, 'BPS restricted access; remaining requests in this synchronization were stopped.')
        if not self.settings.configured:
            raise BPSError('API KEY', 'BPS API key belum dikonfigurasi. Tambahkan BPS_API_KEY ke backend/.env.')
        if not path.startswith('/v1/') or '?' in path:
            raise BPSError(stage, 'Invalid API path.')
        request_params = {**params, 'key': self.settings.api_key}
        fingerprint = hashlib.sha256(json.dumps([path, params], sort_keys=True).encode()).hexdigest()[:24]
        cache_file = self.settings.cache / f'raw-{fingerprint}.json'
        if self.use_cache and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding='utf-8'))
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached['fetched_at'])).total_seconds()
                if age < 86400:
                    self.fetched_times.append(cached['fetched_at'])
                    return cached['response']
            except (ValueError, KeyError, OSError):
                pass
        for attempt in range(3):
            try:
                async with self.request_lock:
                    if self.blocked:
                        raise BPSError(stage, 'BPS restricted access; synchronization stopped.')
                    if self.last_request_at is not None:
                        await asyncio.sleep(max(0, 1.0 - (time.monotonic() - self.last_request_at)))
                    self.last_request_at = time.monotonic()
                    response = await self.http.get(path, params=request_params)
                    if response.status_code in (401, 403, 429):
                        self.blocked = True
            except httpx.RequestError:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise BPSError(stage, 'Network/TLS/timeout failure after 3 attempts.') from None
            if self.blocked:
                raise BPSError(stage, f'HTTP {response.status_code}; access restricted. Synchronization stopped; check BPS account/quota before retrying.')
            if response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
            if not response.is_success:
                raise BPSError(stage, f'HTTP {response.status_code}; check credentials, quota and endpoint.')
            try:
                payload = response.json()
            except ValueError:
                raise BPSError(stage, 'Expected JSON; received a non-JSON response.') from None
            if not isinstance(payload, dict) or str(payload.get('status', '')).upper() != 'OK':
                raise BPSError(stage, 'BPS response status is not OK; check credentials and endpoint availability.')
            if payload.get('data-availability') != 'available':
                raise BPSError(stage, 'BPS reports no available data.')
            for node in walk(payload):
                if 'condition' in node and str(node['condition']).upper() != 'OK':
                    raise BPSError(stage, 'Nested BPS response condition is not OK.')
            payload = self.sanitize(payload)
            self.network_successes += 1
            self.fetched_times.append(datetime.now(timezone.utc).isoformat())
            fingerprint = hashlib.sha256(json.dumps([path, params], sort_keys=True).encode()).hexdigest()[:24]
            self.save(f'raw-{fingerprint}', {'fetched_at': datetime.now(timezone.utc).isoformat(),
                      'path': path, 'params': params, 'response': payload})
            return payload
        raise BPSError(stage, 'Retry budget exhausted.')

    async def pages(self, path, params, stage):
        first = await self.get(path, params, stage)
        yield first
        counts = [int(n['pages']) for n in walk(first) if 'pages' in n]
        pages = max(counts, default=1)
        if pages > 500:
            raise BPSError(stage, 'Pagination exceeds safety bound (500); narrow discovery.')
        for page in range(2, pages + 1):
            yield await self.get(path, {**params, 'page': page}, stage)
