"""Opt in: RUN_BPS_INTEGRATION=1, then unittest discover -s tests/integration."""
import os
import unittest
from app.config import get_settings
from app.services.bps_client import BPSClient
from app.services.bps_discovery import Discovery


@unittest.skipUnless(os.getenv('RUN_BPS_INTEGRATION')=='1','Explicit live integration opt-in required')
class LiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_bogor_domains(self):
        async with BPSClient(get_settings()) as client:
            discovery=Discovery(client)
            await discovery.domains()
            self.assertTrue(discovery.report['bogor_domain_verified'])
