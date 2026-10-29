"""Publish only the reviewed evidence directory using a separate Git index."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PUB = OUT / 'publication'
REL = 'bench/results/2026-10-29-community-rtx5060ti-deepseek41-windows'
BRANCH = 'evidence/deepseek41-windows-20261029'
REPO = 'Thymos2027/Strata'


def git(*args, env=None, data=None):
    r = subprocess.run(['git', *args], input=data, cwd=ROOT, env=env, capture_output=True, check=True)
    return r.stdout.decode().strip()


subprocess.run([str(ROOT/'.venv/Scripts/python.exe'), str(PUB/REL/'verify_public.py')],check=True,cwd=ROOT)
before = git('status','--porcelain=v1','--untracked-files=no')
remote = git('ls-remote','origin',f'refs/heads/{BRANCH}')
assert remote and remote.split()[1] == f'refs/heads/{BRANCH}'
base = remote.split()[0]
git('fetch','--no-tags','origin',f'refs/heads/{BRANCH}')
env = dict(os.environ, GIT_INDEX_FILE=str(OUT/'publication-index'),
           GIT_AUTHOR_NAME='Thymos2027', GIT_AUTHOR_EMAIL='187644295+Thymos2027@users.noreply.github.com',
           GIT_COMMITTER_NAME='Thymos2027', GIT_COMMITTER_EMAIL='187644295+Thymos2027@users.noreply.github.com')
git('read-tree',base,env=env)
files=[]
for path in sorted((PUB/REL).rglob('*')):
    if path.is_file():
        target=path.relative_to(PUB).as_posix()
        sha=git('hash-object','-w','--stdin',data=path.read_bytes())
        git('update-index','--add','--cacheinfo','100644',sha,target,env=env)
        files.append({'path':target,'git_blob_sha':sha,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
tree=git('write-tree',env=env)
changed=git('diff','--name-only',base,tree).splitlines()
assert sorted(changed)==sorted(f['path'] for f in files)
assert len(files)==25 and all(p.startswith(REL+'/') for p in changed)
message=OUT/'evidence-commit-message.txt'
message.write_text('docs: record DeepSeek Windows commit-headroom evidence\n\nRecorded 2026-10-29; automatic-store failure and bounded64GB case.\nNo engine or default changes. No upstream pull request.\n',encoding='utf-8')
commit=git('commit-tree',tree,'-p',base,'-F',str(message),env=env)
assert git('status','--porcelain=v1','--untracked-files=no')==before
git('push','origin',f'{commit}:refs/heads/{BRANCH}')
assert git('ls-remote','origin',f'refs/heads/{BRANCH}').split()[0]==commit
result={'repository':REPO,'branch':BRANCH,'parent':base,'commit':commit,'tree':tree,
        'directory':REL,'files':files,'worktree_and_real_index_unchanged':True,
        'url':f'https://github.com/{REPO}/blob/{commit}/{REL}/README.md'}
(OUT/'evidence-publication.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['repository','branch','commit','url','worktree_and_real_index_unchanged']},indent=2))
