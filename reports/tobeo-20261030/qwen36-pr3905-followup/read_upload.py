import sys,json,base64
from pathlib import Path
p=Path(__file__).resolve().parent
s=json.loads((p/'upload-spec.json').read_text())[int(sys.argv[1])]
b=(p/'publication-evidence-02'/s['name']).read_bytes()
a=base64.b64encode(b).decode() if s['binary'] else b.decode('utf-8')
o=int(sys.argv[2]);print(json.dumps({'chunk':a[o:o+60000],'length':len(a),'binary':s['binary']}))
