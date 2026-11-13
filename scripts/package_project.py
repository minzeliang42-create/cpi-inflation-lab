"""Package source, audit trail and only the current static data release."""
from pathlib import Path
import json
import zipfile

root=Path(__file__).resolve().parents[1]
version=json.loads((root/'dist/current.json').read_text(encoding='utf-8'))['version']
target=root.parent/'CPI_Inflation_Lab_20261113.zip'
roots=['cpi','scripts','tests','web','data','.github']
files=[root/n for n in ['README.md','VALIDATION.md','requirements.txt','.gitignore']]
for folder in roots:
    files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend(p for p in (root/'dist').iterdir() if p.is_file())
files.extend(p for p in (root/'dist/vendor').rglob('*') if p.is_file())
files.extend(p for p in (root/'dist/data'/version).rglob('*') if p.is_file())
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)): z.write(p,'cpi-inflation-lab/'+p.relative_to(root).as_posix())
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert not any('/output/' in n or '/.staging/' in n or 'edge-profile' in n for n in z.namelist())
print(f'{target}\n{target.stat().st_size:,} bytes; {len(files)} files; release {version}')
