"""Publish an allowlisted historical site; old research remains in repository only."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def publish(out=None):
    out=Path(out or ROOT/'_site');out.mkdir(exist_ok=True)
    # Only this dedicated publication directory is ever cleared.
    assert out.resolve()==(ROOT/'_site').resolve()
    for item in out.iterdir():
        if item.is_dir():shutil.rmtree(item)
        else:item.unlink()
    for name in ['current.json','status.json','card_estimates.json']:
        p=ROOT/'dist'/name
        if p.exists():shutil.copy2(p,out/name)
    manifest=json.loads((out/'current.json').read_text())
    bundle=Path(manifest['path']).parent
    assert len(bundle.parts)==2 and bundle.parts[0]=='data' and '..' not in bundle.parts
    shutil.copytree(ROOT/'dist'/bundle,out/bundle)
    allowed=['index.html','app.js','history.js','history.css','style.css','card-estimates.css','pce.json','pce.csv','pce_status.json','pce-growth.js','pce-growth.css','pce_growth.json','pce_growth.csv','pce_growth_status.json']
    for name in allowed:
        p=ROOT/'web'/name
        if p.exists():shutil.copy2(p,out/name)
    shutil.copytree(ROOT/'web/vendor',out/'vendor')
    # Keep active web assets in dist consistent without deleting archived research.
    for name in allowed: 
        if (out/name).exists():shutil.copy2(out/name,ROOT/'dist'/name)
    return out
if __name__=='__main__':print(publish())
