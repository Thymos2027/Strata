import argparse,json,sys,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path.cwd()))
from strata_cli import update_cmd
from strata_control import dsv41_engine
out=Path('reports/tobeo-20261029/deepseek41-case')
root=Path('D:/Models/Strata/engine-dsv41')
source=update_cmd._feed_source(argparse.Namespace(feed=None),root.parent)
print('Feed',source,flush=True)
exe=dsv41_engine.find(root) or dsv41_engine.install(root,source,emit=lambda s:print(s,flush=True))
assert exe,'DeepSeek package installation failed'
result={'date':datetime.now(timezone(timedelta(hours=8))).isoformat(),'feed':source,'exe':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'build':json.loads((exe.parent/'BUILD.json').read_text())}
(out/'engine.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
