"""Restore the locally tested, frozen research study on the first cloud run."""
from pathlib import Path
import hashlib,zipfile
root=Path(__file__).resolve().parents[1]
archive=root/'data/forecast/research-seed.zip'
if not (root/'data/forecast/research/research.json').exists() and archive.exists():
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==(archive.with_suffix('.sha256')).read_text().strip()
    target=root/'data/forecast/research';target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            dest=target/item.filename
            assert dest.resolve().is_relative_to(target.resolve())
            dest.write_bytes(z.read(item))
