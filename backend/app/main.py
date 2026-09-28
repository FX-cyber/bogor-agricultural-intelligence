import asyncio
import csv
import io
import math
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.services.pipeline import Pipeline
from app.services.bps_client import BPSError
from app.services.analytics import filtered, records
from app.services.attribution import NOTICE, source_url

pipeline = Pipeline()
refresh_admitted_at = None
REFRESH_INTERVAL_SECONDS = 900
PUBLIC_DEPLOYMENT = os.getenv('PUBLIC_DEPLOYMENT', 'false').lower() == 'true'
ALLOWED_ORIGINS = [o.strip().rstrip('/') for o in os.getenv('ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000').split(',') if o.strip()]


async def refresh_safely():
    try:
        await pipeline.refresh()
    except BPSError:
        pass


@asynccontextmanager
async def lifespan(app):
    task = None
    if pipeline.settings.configured and pipeline.status()['stale']:
        task = asyncio.create_task(refresh_safely())
    yield
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title='Bogor Agricultural Intelligence', description=NOTICE, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


def filters(request):
    result = {k: v for k, v in request.query_params.items() if k in
              ('year', 'district', 'commodity', 'category', 'unit', 'indicator') and v}
    if 'year' in result:
        try:
            result['year'] = int(result['year'])
        except ValueError:
            raise HTTPException(422, 'Year must be an integer.') from None
    return result


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/bps/status')
def status():
    return pipeline.status()


@app.get('/api/bps/tables')
def tables():
    snapshot = pipeline.snapshot or {}
    return {'selected': [{**t, 'source_url': source_url(t['id'])} for t in snapshot.get('tables', [])],
            'candidates': snapshot.get('candidates', [])}


@app.post('/api/bps/refresh', status_code=202)
async def refresh(request: Request):
    global refresh_admitted_at
    # Origin is not authentication. Public visitors cannot trigger BPS traffic.
    if PUBLIC_DEPLOYMENT:
        raise HTTPException(403, 'Public deployment is read-only. Synchronization is managed by the operator.')
    origin = request.headers.get('origin')
    if origin and origin not in ('http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:8000', 'http://127.0.0.1:8000'):
        raise HTTPException(403, 'Refresh is restricted to the local application.')
    if pipeline.lock.locked():
        return {'message': 'Refresh already running.'}
    if not pipeline.settings.configured:
        raise HTTPException(503, 'BPS API key belum dikonfigurasi. Tambahkan BPS_API_KEY ke backend/.env.')
    remaining = REFRESH_INTERVAL_SECONDS - (time.monotonic() - refresh_admitted_at) if refresh_admitted_at is not None else 0
    if remaining > 0:
        raise HTTPException(429, 'Penyegaran dibatasi sekali per 15 menit untuk menjaga layanan BPS. Data tersimpan tetap tersedia.',
                            headers={'Retry-After': str(math.ceil(remaining))})
    refresh_admitted_at = time.monotonic()
    asyncio.create_task(refresh_safely())
    return {'message': 'Refresh started.'}


@app.get('/api/agriculture/options')
def options():
    rows = (pipeline.snapshot or {}).get('rows', [])
    return {**{field: sorted({r[field] for r in rows if r[field] is not None}) for field in
               ('year', 'district', 'commodity', 'category', 'unit', 'indicator')},
            'defaults': (pipeline.snapshot or {}).get('default_filters', {})}


@app.get('/api/agriculture/data')
def data(request: Request, search: str = '', sort: str = 'year', direction: str = 'desc',
         page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200), export: str = ''):
    frame = filtered((pipeline.snapshot or {}).get('rows', []), filters(request))
    if search:
        mask = frame[['district', 'commodity', 'source_table_title']].fillna('').apply(
            lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
        frame = frame[mask]
    if sort not in ('year', 'district', 'commodity', 'indicator', 'value', 'unit', 'category'):
        raise HTTPException(422, 'Unsupported sort column.')
    frame = frame.sort_values(sort, ascending=direction == 'asc', na_position='last')
    if export == 'csv':
        frame = frame.copy()
        frame['api_notice'] = NOTICE
        frame['processing_note'] = 'Data BPS dinormalisasi oleh aplikasi independen; bukan keluaran analisis resmi BPS.'
        columns = [c for c in frame.columns if c != 'metadata']
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(columns)
        for row in records(frame[columns]):
            values = [row[c] for c in columns]
            # Protect CSV consumers from formula execution in textual BPS metadata.
            writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in values])
        return Response('\ufeff' + stream.getvalue(), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="bogor-agriculture.csv"'})
    return {'rows': records(frame.iloc[(page-1)*page_size:page*page_size]), 'total': len(frame),
            'page': page, 'page_size': page_size}


@app.get('/api/agriculture/dashboard')
def dashboard(request: Request):
    return pipeline.analyze(filters(request))


@app.get('/api/agriculture/{kind}')
def analysis(kind: str, request: Request):
    if kind not in ('summary', 'trends', 'clusters', 'insights'):
        raise HTTPException(404, 'Analysis not found.')
    return pipeline.analyze(filters(request))[kind]
