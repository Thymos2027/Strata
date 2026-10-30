"""Authorized one-comment publication using the existing Git credential manager, never logging credentials."""
import os,json,subprocess,urllib.request,urllib.error
from pathlib import Path
P=Path(__file__).resolve().parent
REPO='Niko1221/Strata'
env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
c=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,env=env,timeout=25)
if c.returncode:raise RuntimeError('Existing Git credential manager could not supply a noninteractive credential')
fields=dict(line.split('=',1) for line in c.stdout.splitlines() if '=' in line)
secret=fields.get('password');assert secret,'No existing Git credential'
def api(path,data=None):
 req=urllib.request.Request('https://api.github.com/'+path,data=None if data is None else json.dumps(data).encode('utf-8'),headers={'Authorization':'Bearer '+secret,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Strata-authorized-evidence-publication'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
profile=api('user');assert profile['login']=='Thymos2027','Unexpected Git credential account'
body=(P/'comment-3905.md').read_text(encoding='utf-8')
comments=api('repos/'+REPO+'/issues/3905/comments?per_page=100')
existing=[x for x in comments if x['user']['login']=='Thymos2027' and x['body'].startswith('### Follow-up: CPU sampling, staging dependencies and completion-order job paths')]
assert len(existing)<=1,'Duplicate follow-up comments already exist'
if existing:
 result=existing[0];assert result['body']==body,'Existing follow-up differs; not posting another'
else:result=api('repos/'+REPO+'/issues/3905/comments',{'body':body})
(P/'publication-post.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
read=api('repos/'+REPO+'/issues/comments/'+str(result['id']));assert read['body']==body and read['user']['login']=='Thymos2027'
(P/'publication-readback.json').write_text(json.dumps(read,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'passed':True,'url':read['html_url'],'id':read['id'],'created_at':read['created_at'],'account':read['user']['login'],'body_exact_match':True}))
