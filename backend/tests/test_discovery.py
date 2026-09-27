"""Synthetic contract tests, not production BPS observations."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import httpx
from app.config import Settings
from app.services.bps_client import BPSClient, BPSError
from app.services.bps_discovery import available_years, score_table, verify_simdasi


class MetadataTests(unittest.TestCase):
    def test_only_explicit_years(self):
        self.assertEqual(available_years({'ketersediaan_tahun': [2021, '2023', 2021]}), [2021, 2023])
        self.assertEqual(available_years({'title': 'Production 2025'}), [])

    def test_score_prefers_district_production(self):
        self.assertGreater(score_table({'judul': 'Produksi Sayuran Menurut Kecamatan'}),
                           score_table({'judul': 'Pertanian'}))
        self.assertEqual(score_table({'title': 'Produksi listrik'}), 0)

    def test_regions_fail_closed(self):
        for name, code in [('Kota Bogor', '3271000'), ('Kabupaten Bandung', '3201000'),
                           ('Kabupaten Bogor', '3271000')]:
            with self.assertRaises(BPSError):
                verify_simdasi({'data': {'wilayah': name, 'induk': code, 'data': []}}, '3201000')
        with self.assertRaises(BPSError):
            verify_simdasi({'data': []}, '3201000')
        self.assertTrue(verify_simdasi({'data': {'wilayah': 'Kabupaten Bogor',
                           'induk': '3201000', 'data': []}}, '3201000'))

    def test_placeholder(self):
        self.assertFalse(Settings(api_key='PUT_MY_BPS_API_KEY_HERE').configured)
        self.assertNotIn('private-secret', repr(Settings(api_key='private-secret')))

    def test_host_restriction(self):
        with self.assertRaises(ValueError):
            Settings(base_url='https://example.com').validate()


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_access_restriction_stops_further_requests(self):
        for status in (401, 403, 429):
            seen = []
            def handler(request):
                seen.append(request)
                return httpx.Response(status, headers={'Retry-After': '3600'})
            async with BPSClient(Settings(api_key='test-secret'), httpx.MockTransport(handler)) as client:
                for _ in range(2):
                    with self.assertRaises(BPSError):
                        await client.get('/v1/api/domain', {}, 'TEST')
            self.assertEqual(len(seen), 1)

    async def test_redaction_and_pagination(self):
        seen = []
        def handler(request):
            seen.append(request.url.params.get('page', '1'))
            self.assertEqual(request.url.params['key'], 'private-secret')
            return httpx.Response(200, json={'status': 'OK', 'data-availability': 'available',
                'data': [{'pages': 2}, [{'domain_id': '3201'}]], 'key': 'private-secret',
                'echo': 'url?key=private-secret'})
        with TemporaryDirectory() as directory:
            async with BPSClient(Settings(api_key='private-secret', cache=Path(directory)),
                                 httpx.MockTransport(handler)) as client:
                pages = [p async for p in client.pages('/v1/api/domain', {}, 'TEST')]
                self.assertEqual(len(pages), 2)
                self.assertEqual(seen, ['1', '2'])
                for file in Path(directory).glob('*.json'):
                    self.assertNotIn('private-secret', file.read_text())

    async def test_errors_do_not_leak(self):
        for response in (httpx.Response(401, text='private-secret'),
                         httpx.Response(200, text='<html>private-secret</html>'),
                         httpx.Response(200, json={'status': 'Error', 'message': 'private-secret'})):
            async with BPSClient(Settings(api_key='private-secret'),
                                 httpx.MockTransport(lambda request: response)) as client:
                with self.assertRaises(BPSError) as raised:
                    await client.get('/v1/api/domain', {}, 'TEST')
                self.assertNotIn('private-secret', str(raised.exception))

    async def test_missing_key_never_calls_network(self):
        def handler(request):
            self.fail('Network called without a key')
        async with BPSClient(Settings(), httpx.MockTransport(handler)) as client:
            with self.assertRaises(BPSError):
                await client.get('/v1/api/domain', {}, 'TEST')


if __name__ == '__main__':
    unittest.main()
