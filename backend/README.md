# Backend

See the root README for setup, verified sources, methods and limitations.

Run from backend after configuring .env:

```powershell
python -m pip install -r requirements.lock.txt
python scripts/diagnose_bps.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Offline tests: `python -m unittest discover -s tests -v`.
Live tests: set `RUN_BPS_INTEGRATION=1`, then `python -m unittest discover -s tests/integration -v`.
API reference: `/docs`. Keep this local unless hosted access controls are added.
