"""Synthetic calculation cases are explicitly test-only; never served by the app."""
import copy
import gzip
import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from tempfile import TemporaryDirectory
from app.config import Settings
from app.services.normalizer import parse_number, district_name, normalize_detail, validate_rows
from app.services.analytics import summarize, yoy, trends
from app.services.clustering import features, cluster
from app.services.insight_engine import insights
from app.services.pipeline import Pipeline
from app.services.bps_client import BPSError


def synthetic():
    result=[]
    for year in (2021,2022,2023,2024):
        for district in range(8):
            for commodity in range(3):
                result.append(dict(year=year,district_code=str(district),district=f'TEST District {district}',
                  commodity=f'TEST Crop {commodity}',category='TEST',indicator='Produksi',
                  value=(district+1)*(commodity+1)*(1+(year-2021)*.1)*100,unit='kw',source='TEST ONLY',
                  source_table_id='TEST',source_table_title='Synthetic mathematical test',last_updated='2024-01-01',
                  last_synced='2024-01-01T00:00:00+00:00',geography_level='kecamatan',metadata={}))
    return result


class NormalizerTests(unittest.TestCase):
    def test_indonesian_numbers(self):
        for raw,expected in [('1.234,56',1234.56),('20.598',20598),('54.099,04',54099.04),('12,5',12.5),('0',0),('12.34',12.34)]:
            self.assertAlmostEqual(parse_number(raw),expected)
        self.assertTrue(math.isnan(parse_number('12.34.56')))
        self.assertTrue(math.isnan(parse_number('1,234.56')))

    def test_missing_not_zero(self):
        for raw in ['-', '–', '...', None,'NA','N/A','',True]:
            self.assertTrue(math.isnan(parse_number(raw)))
        self.assertEqual(parse_number('–',zero_symbols=['–']),0)

    def test_district_names(self):
        self.assertEqual(district_name('Kecamatan CIBINONG'),'Cibinong')

    def test_duplicates_and_conflicts(self):
        rows=synthetic()
        clean,quality=validate_rows(rows+[rows[0]])
        self.assertEqual(quality['duplicates_removed'],1)
        self.assertEqual(len(clean),len(rows))
        other={**rows[0],'value':99999}
        with self.assertRaises(BPSError):validate_rows(rows+[other])

    def test_real_sanitized_fixture(self):
        fixture=json.loads((Path(__file__).parent/'fixtures'/'simdasi_excerpt.json').read_text(encoding='utf-8'))
        rows,diagnostics=normalize_detail(fixture['response'],fixture['table'],fixture['fetched_at'])
        self.assertEqual(diagnostics['aggregate_rows_excluded'],1)
        self.assertEqual(rows[0]['district'],'Nanggung')
        self.assertEqual(rows[0]['commodity'],'Alpukat')
        self.assertEqual(rows[0]['unit'],'kw')
        self.assertEqual(rows[0]['value'],7278)
        self.assertTrue(math.isnan(rows[1]['value']))
        self.assertNotIn('3201000',[r['district_code'] for r in rows])
        # Synthetic mutation of the real contract verifies explicit scale preservation.
        payload=copy.deepcopy(fixture['response'])
        body=payload['data'][1]
        first=next(iter(body['kolom'].values()))
        first['nama_variabel']='Produksi Test (ribu ton)'
        first['satuan']='ton'
        scaled,_=normalize_detail(payload,fixture['table'],fixture['fetched_at'])
        self.assertEqual(scaled[0]['unit'],'ribu ton')

    def test_province_excludes_kota_bogor(self):
        fixture=json.loads((Path(__file__).parent/'fixtures'/'static_province.json').read_text(encoding='utf-8'))
        rows,_=normalize_detail(fixture['response'],fixture['table'],fixture['fetched_at'])
        self.assertEqual(len(rows),5)
        self.assertTrue(all(r['district']=='Kabupaten Bogor' for r in rows))
        self.assertEqual(next(r['value'] for r in rows if r['commodity']=='Cabai Merah Besar'),29931)
        self.assertNotIn(3510,[r['value'] for r in rows])


class AnalyticsTests(unittest.TestCase):
    def test_yoy_edge_cases(self):
        self.assertEqual(yoy(120,100),20)
        for a,b in [(1,0),(None,5),(5,None),(float('nan'),5)]:self.assertIsNone(yoy(a,b))

    def test_totals_rankings_and_yoy(self):
        rows=synthetic()
        summary=summarize(rows,{'year':2024,'unit':'kw'})
        self.assertAlmostEqual(summary['total'],28080)
        self.assertEqual(summary['top_commodities'][0]['name'],'TEST Crop 2')
        self.assertEqual(summary['top_districts'][0]['name'],'TEST District 7')
        self.assertAlmostEqual(summary['yoy']['change_percent'],100/12)
        self.assertEqual(summary['yoy']['matched_observations'],24)

    def test_units_never_mixed(self):
        rows=synthetic()+[{**synthetic()[0],'unit':'kg','value':1000000}]
        self.assertIsNone(summarize(rows,{'year':2021})['total'])
        self.assertLess(summarize(rows,{'year':2021,'unit':'kw'})['total'],1000000)

    def test_yoy_matched_panel(self):
        rows=synthetic()
        # A missing current cell must also remove its previous-year counterpart.
        rows=[{**r,'value':None} if r['year']==2024 and r['district_code']=='7' else r for r in rows]
        self.assertEqual(summarize(rows,{'year':2024,'unit':'kw'})['yoy']['matched_observations'],21)
        self.assertAlmostEqual(summarize(rows,{'year':2024,'unit':'kw'})['yoy']['change_percent'],100/12)

    def test_insight_evidence(self):
        result=insights(synthetic(),{'year':2024,'unit':'kw'})
        self.assertTrue(any(r['type']=='leader' for r in result))
        self.assertTrue(all(r['evidence'] and r['provenance'] for r in result))
        self.assertLessEqual(len(result),6)
        self.assertEqual(insights([],{}),[])

    def test_trend_requires_three_years(self):
        self.assertEqual(trends([r for r in synthetic() if r['year']>=2023],{'unit':'kw'})['commodity_trends'],[])
        self.assertTrue(all(t['classification']=='Increasing' for t in trends(synthetic(),{'unit':'kw'})['commodity_trends']))

    def test_clustering(self):
        frame,unit,year=features(synthetic(),{'year':2024,'unit':'kw'})
        self.assertEqual(len(frame),8)
        self.assertEqual(frame.iloc[0].active_commodities,3)
        result=cluster(synthetic(),{'year':2024,'unit':'kw'})
        self.assertTrue(result['available'])
        self.assertIn(result['k'],range(2,7))
        self.assertNotIn('district',result['features'])
        self.assertFalse(cluster([], {})['available'])


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_refresh_retains_full_cache(self):
        with TemporaryDirectory() as directory:
            settings=Settings(api_key='test-only',cache=Path(directory))
            snapshot={'schema_version':1,'rows':synthetic(),'last_sync':'2024-01-01T00:00:00+00:00'}
            path=settings.cache/'normalized.json'
            path.write_text(json.dumps(snapshot),encoding='utf-8')
            pipeline=Pipeline(settings)
            table={'id':'TEST','title':'Produksi menurut kecamatan','domain':'3201','source':'SIMDASI','years':[2024],'metadata':{}}
            with patch('app.services.pipeline.get_settings',return_value=settings), patch('app.services.pipeline.Discovery') as mocked, patch('app.services.pipeline.normalize_detail',return_value=(synthetic(),{'rows_rejected':0,'aggregate_rows_excluded':0})):
                discovery=mocked.return_value
                discovery.domains=AsyncMock()
                discovery.candidates=AsyncMock(return_value=[table])
                discovery.report={'details':[],'errors':['DATA FETCH: HTTP 503'],'simdasi_connected':True}
                async def fetch(table):
                    discovery.report['details'].append({'response':{}})
                discovery.fetch_details=fetch
                result=await pipeline.refresh(emit=lambda text:None)
            self.assertIn('previous valid dataset preserved',result['error'])
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),snapshot)

    async def test_failed_refresh_retains_valid_cache(self):
        with TemporaryDirectory() as directory:
            settings=Settings(cache=Path(directory))
            snapshot={'schema_version':1,'rows':synthetic(),'last_sync':'2024-01-01T00:00:00+00:00'}
            path=settings.cache/'normalized.json'
            path.write_text(json.dumps(snapshot),encoding='utf-8')
            pipeline=Pipeline(settings)
            with patch('app.services.pipeline.get_settings',return_value=settings):
                status=await pipeline.refresh(emit=lambda text:None)
            self.assertTrue(status['using_cache'])
            self.assertIsNotNone(status['error'])
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),snapshot)

    def test_bundled_snapshot_is_read_only_fallback(self):
        with TemporaryDirectory() as directory:
            cache=Path(directory)/'cache'
            snapshot=Path(directory)/'snapshot'
            cache.mkdir()
            snapshot.mkdir()
            bundled={'schema_version':1,'rows':synthetic(),'last_sync':'2026-09-27T00:00:00+00:00'}
            with gzip.open(snapshot/'normalized.json.gz','wt',encoding='utf-8') as handle:
                json.dump(bundled,handle)
            settings=Settings(cache=cache,snapshot=snapshot)
            self.assertFalse(settings.configured)
            pipeline=Pipeline(settings)
            self.assertEqual(pipeline.snapshot,bundled)
            self.assertIsNone(pipeline.status()['error'])
            self.assertTrue(pipeline.status()['using_cache'])
            fresh={'schema_version':1,'rows':synthetic(),'last_sync':'2026-09-28T00:00:00+00:00'}
            (cache/'normalized.json').write_text(json.dumps(fresh),encoding='utf-8')
            self.assertEqual(Pipeline(settings).snapshot,fresh)


if __name__=='__main__':unittest.main()
