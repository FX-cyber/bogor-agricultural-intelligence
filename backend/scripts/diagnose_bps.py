"""Run from backend: python scripts/diagnose_bps.py. Never prints credentials."""
import asyncio
from pathlib import Path
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.services.bps_client import BPSClient, BPSError
from app.services.bps_discovery import Discovery


async def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--cached', action='store_true', help='Reuse raw responses younger than 24h; no fresh connection claim.')
    parser.add_argument('--discovery-only', action='store_true')
    args = parser.parse_args()
    print('=' * 60)
    print('BOGOR AGRICULTURAL INTELLIGENCE\nBPS API DIAGNOSTIC')
    print('=' * 60)
    try:
        settings = get_settings()
    except ValueError as exc:
        print(f'[CONFIGURATION] {exc}\nSTATUS: BLOCKED')
        return 2
    print('[1] API KEY')
    if not settings.configured:
        print('BPS API key belum dikonfigurasi.\nTambahkan BPS_API_KEY ke backend/.env.')
        print('Domain, SIMDASI, tables, years and numeric rows: NOT VERIFIED')
        print('STATUS: BLOCKED (API KEY)')
        return 2
    print('API key detected (redacted)')
    try:
        if not args.discovery_only:
            from app.services.pipeline import Pipeline
            pipeline = Pipeline(settings)
            status = await pipeline.refresh(use_cache=args.cached)
            print(f"Years: {status['quality'].get('years', [])}")
            print(f"Quality: {status['quality']}")
            return 0 if pipeline.snapshot and not status['error'] else 1
        async with BPSClient(settings, use_cache=args.cached) as client:
            report = await Discovery(client).run()
        print(f"Details retrieved: {len(report['details'])}")
        print('Rows normalized: NOT VERIFIED; inspect sanitized raw responses before implementing adapters.')
        print('STATUS: PARTIAL — discovery scaffold; live normalization and analytics pending')
        return 1
    except BPSError as exc:
        print(f'{exc}\nSTATUS: BLOCKED ({exc.stage})')
        return 2


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
