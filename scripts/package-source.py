"""Create a source-only GitHub upload archive using explicit allowlists."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DIRS = ('.github', 'frontend/app', 'frontend/components', 'frontend/lib',
        'frontend/public', 'backend/app', 'backend/scripts', 'backend/tests',
        'docs', 'scripts')
FILES = ('.gitignore', 'README.md', 'render.yaml', 'backend/Dockerfile',
         'backend/.dockerignore', 'backend/.env.example', 'backend/requirements.txt',
         'backend/requirements.lock.txt', 'backend/README.md', 'backend/data/cache/.gitkeep',
         'frontend/.env.example', 'frontend/package.json', 'frontend/package-lock.json',
         'frontend/next.config.ts', 'frontend/next-env.d.ts', 'frontend/tsconfig.json',
         'frontend/postcss.config.mjs')
ALLOWED_SUFFIXES = {'.py', '.tsx', '.ts', '.json', '.md', '.css', '.mjs', '.yml',
                    '.yaml', '.ps1', '.png', '.svg', '.ico', '.html', '.txt'}
files = {ROOT / p for p in FILES if (ROOT / p).is_file()}
for directory in DIRS:
    for p in (ROOT / directory).rglob('*'):
        if p.is_file() and not p.is_symlink() and p.suffix in ALLOWED_SUFFIXES and '__pycache__' not in p.parts and not p.name.startswith('.env'):
            files.add(p)
output = ROOT / 'dist' / 'bogor-agricultural-intelligence-github.zip'
output.parent.mkdir(exist_ok=True)
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for p in sorted(files):
        archive.write(p, p.relative_to(ROOT).as_posix())
print(f'Created {output.name}: {len(files)} source/documentation files; no runtime cache or .env.')
