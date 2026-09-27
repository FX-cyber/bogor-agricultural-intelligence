import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app, pipeline
from test_analytics import synthetic
import time
from app.services.attribution import NOTICE, TABLE_URLS
from app.config import Settings


class APITests(unittest.TestCase):
    def setUp(self):
        self.previous=pipeline.snapshot
        pipeline.snapshot={'rows':synthetic(),'default_filters':{'year':2024,'unit':'kw'}}
        pipeline.memo.clear()
        self.client=TestClient(app)

    def tearDown(self):
        pipeline.snapshot=self.previous
        pipeline.memo.clear()

    def test_health_and_analytics(self):
        self.assertEqual(self.client.get('/api/health').json(),{'status':'ok'})
        for route in ['summary','trends','clusters','insights','dashboard']:
            response=self.client.get(f'/api/agriculture/{route}?year=2024&unit=kw')
            self.assertEqual(response.status_code,200,response.text)

    def test_filtered_export_and_validation(self):
        response=self.client.get('/api/agriculture/data?year=2024&search=District%207')
        self.assertEqual(response.json()['total'],3)
        self.assertEqual(self.client.get('/api/agriculture/data?year=no').status_code,422)
        csv=self.client.get('/api/agriculture/data?year=2024&search=District%207&export=csv').text
        self.assertEqual(len(csv.strip().splitlines()),4)
        self.assertNotIn('TEST District 6',csv)

    def test_empty_state(self):
        pipeline.snapshot=None
        pipeline.memo.clear()
        self.assertEqual(self.client.get('/api/agriculture/dashboard').status_code,200)
        self.assertEqual(self.client.get('/api/agriculture/data').json()['total'],0)

    def test_refresh_origin(self):
        self.assertEqual(self.client.post('/api/bps/refresh',headers={'Origin':'https://example.com'}).status_code,403)

    def test_refresh_cooldown_never_starts_network(self):
        with patch('app.main.refresh_admitted_at', time.monotonic()), patch.object(pipeline, 'settings', Settings(api_key='test-secret')), patch('app.main.asyncio.create_task') as task:
            response = self.client.post('/api/bps/refresh')
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response.headers)
            task.assert_not_called()

    def test_citation_survives_csv_and_provenance(self):
        for row in pipeline.snapshot['rows']:
            row['source_table_id'] = next(iter(TABLE_URLS))
        result = self.client.get('/api/agriculture/summary?year=2024&unit=kw').json()
        self.assertTrue(result['provenance'][0]['source_url'].endswith('?year=2024'))
        csv = self.client.get('/api/agriculture/data?year=2024&export=csv').text
        self.assertIn(NOTICE, csv)
        self.assertIn('https://bogorkab.bps.go.id/id/statistics-table/', csv)
