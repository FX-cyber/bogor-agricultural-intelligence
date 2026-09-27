from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default='', repr=False)
    province: str = '3200'
    domain: str = '3201'
    wilayah: str = '3201000'
    base_url: str = 'https://webapi.bps.go.id'
    cache: Path = ROOT / 'data' / 'cache'

    @property
    def configured(self):
        value = self.api_key.strip().lower()
        return bool(value) and not any(x in value for x in ('put_my_', 'your_bps_', 'paste_my_'))

    def validate(self):
        if self.base_url.rstrip('/') != 'https://webapi.bps.go.id':
            raise ValueError('Only the official HTTPS BPS API host is permitted.')
        if (self.province, self.domain, self.wilayah) != ('3200', '3201', '3201000'):
            raise ValueError('This project requires identifiers 3200 / 3201 / 3201000; discovery verifies them at runtime.')


def get_settings():
    load_dotenv(ROOT / '.env', override=False)
    settings = Settings(
        api_key=os.getenv('BPS_API_KEY', ''),
        province=os.getenv('BPS_PROVINCE_DOMAIN', '3200'),
        domain=os.getenv('BPS_BOGOR_DOMAIN', '3201'),
        wilayah=os.getenv('BPS_BOGOR_SIMDASI_WILAYAH', '3201000'),
        base_url=os.getenv('BPS_API_BASE_URL', 'https://webapi.bps.go.id'),
    )
    settings.validate()
    return settings
