"""Journalled, same-volume local layout migration and real inference validation."""
from pathlib import Path
from datetime import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import psutil

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'migration-01'
MODELS = Path('D:/Models')
STRATA = MODELS / 'Strata'
QWEN = MODELS / 'Qwen'
DEEP = MODELS / 'DeepSeek'
ARCHIVE = STRATA / 'archive/2026-10-29-layout'
Q38 = QWEN / 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S'
DSNAME = 'deepseek-v4.1-flash-IST-DAS-2.25bpw'
DAILY = ROOT / 'strata-iq3_s.json'
Q36 = ROOT / 'strata-qwen36-q4.json'
DSCFG = ROOT / 'strata-deepseek41-ist-das-2.25bpw.json'
R = {'started': datetime.now().astimezone().isoformat(), 'phase': 'preflight', 'moves': [], 'hashes': []}


def save():
    R['updated'] = datetime.now().astimezone().isoformat()
    (OUT / 'results.tmp').write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'results.tmp').replace(OUT / 'results.json')
    print(R['updated'], R['phase'], flush=True)


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def api(path, data=None, port=8080, timeout=30):
    base = f'http://127.0.0.1:{port}'
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'Content-Type': 'application/json', 'Origin': base})
    with urllib.request.urlopen(req, timeout=timeout) as h:
        return json.load(h)


def safe(p):
    p = p.resolve()
    assert p.is_relative_to(MODELS.resolve()) and p != MODELS.resolve(), p
    assert not p.is_symlink() and not p.is_junction(), p
    return p


def stop_tree(p):
    children = p.children(recursive=True)
    for c in reversed(children):
        try: c.terminate()
        except psutil.NoSuchProcess: pass
    try: p.terminate()
    except psutil.NoSuchProcess: pass
    _, alive = psutil.wait_procs(children + [p], timeout=15)
    for c in alive:
        c.kill()


def start_daily():
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', STRATA_COMPONENTS_DIR=str(STRATA / 'components'))
    h1 = (OUT / 'daily.stdout.log').open('ab'); h2 = (OUT / 'daily.stderr.log').open('ab')
    p = subprocess.Popen([sys.executable, '-u', '-m', 'serve.server', '--engine', 'strata', '--config', str(DAILY), '--port', '8080'],
                         cwd=ROOT, env=env, stdout=h1, stderr=h2, stdin=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    h1.close(); h2.close(); R['daily_new_pid'] = p.pid
    until = time.monotonic() + 600
    while time.monotonic() < until:
        if p.poll() is not None: raise RuntimeError(f'Daily server exited: {p.returncode}')
        try:
            h = api('/health', timeout=3)
            if h.get('loaded'):
                assert h['model'] == 'qwen3.8-flash-next-iq3_s'
                R['health_after'] = h
                return
        except (OSError, TimeoutError): pass
        time.sleep(2)
    raise TimeoutError('Daily restart exceeded 600 seconds')


def main():
    OUT.mkdir(exist_ok=False)
    save()
    assert not DSCFG.exists()
    R['health_before'] = api('/health'); assert R['health_before']['loaded']
    listeners = [c.pid for c in psutil.net_connections(kind='tcp') if c.status == 'LISTEN' and c.laddr.port == 8080]
    assert len(set(listeners)) == 1, listeners
    daily_proc = psutil.Process(listeners[0])
    assert 'serve.server' in daily_proc.cmdline() and str(DAILY).lower() in ' '.join(daily_proc.cmdline()).lower()
    while daily_proc.parent() and 'serve.server' in daily_proc.parent().cmdline():
        daily_proc = daily_proc.parent()
    R['daily_old_pid'] = daily_proc.pid; R['daily_old_command'] = daily_proc.cmdline()
    assert not [c for c in psutil.net_connections(kind='tcp') if c.status == 'LISTEN' and c.laddr.port == 8081]
    moves = [
        (STRATA / 'IQ3_S', Q38),
        (STRATA / 'mtp', QWEN / 'Qwen3.8-Flash-Next-shared/mtp'),
        (STRATA / 'packs/iq3_s', Q38 / 'strata-pack'),
        (STRATA / 'packs/qwen36-ud-q4_k_xl', QWEN / 'Qwen3.6-35B-A3B-MTP-GGUF/strata-pack'),
        (STRATA / DSNAME, DEEP / DSNAME),
        (STRATA / 'deepseek-v4.1-flash-shared', DEEP / 'deepseek-v4.1-flash-shared'),
        (STRATA / 'deployment-backups', ARCHIVE / 'deployment-backups'),
        (STRATA / 'optimization-20261021', ARCHIVE / 'optimization-20261021'),
        (STRATA / 'engine-dsv41.work', ARCHIVE / 'download-residue/engine-dsv41.work'),
    ]
    for name in ['COMPLETE.json', 'download_all.py', 'download_iq3s.py', 'download.log', 'download.err.log', '__pycache__']:
        moves.append((STRATA / name, ARCHIVE / 'qwen38-download' / name))
    for p in (STRATA / 'components/.updates/partial').iterdir():
        assert p.is_file()
        moves.append((p, ARCHIVE / 'download-residue/components-partial' / p.name))
    for a, b in moves:
        safe(a); safe(b); assert a.exists() and not b.exists(), (a,b)
    R['planned_moves'] = [{'from': str(a), 'to': str(b)} for a,b in moves]
    backup = OUT / 'config-backup'; backup.mkdir()
    originals = {p: p.read_bytes() for p in [DAILY, Q36]}
    for p, data in originals.items(): (backup / p.name).write_bytes(data)
    pack_old = STRATA / DSNAME / 'maya-ds4/ds4.txt'
    original_pack = pack_old.read_bytes(); (backup / 'ds4.txt').write_bytes(original_pack)
    expected = {}
    for x in json.loads((ROOT / 'reports/tobeo-20261029/deepseek41-case/model-verification.json').read_text(encoding='utf-8')):
        expected[str(Path(x['path']))] = (x['sha256'], x['size'], 'prior DeepSeek full verification')
    for x in json.loads((STRATA / 'COMPLETE.json').read_text(encoding='utf-8'))['files']:
        expected[str(STRATA / 'IQ3_S' / x['name'])] = (x['sha256'], x['bytes'], 'pinned Qwen download record')
    for x in json.loads((STRATA / 'mtp/mtp-manifest.json').read_text(encoding='utf-8')):
        expected[str(STRATA / 'mtp' / x['file'])] = (x['sha256'], x['bytes'], 'MTP source tensor manifest')
    files = []
    R['phase'] = 'recording-file-identities'; save()
    for a,b in moves:
        for f in sorted(a.rglob('*')) if a.is_dir() else [a]:
            if not f.is_file(): continue
            safe(f); st = f.stat(); dest = b / f.relative_to(a) if a.is_dir() else b
            sha, size, origin = expected.get(str(f), (None, st.st_size, 'fresh pre-move hash'))
            assert st.st_size == size, f
            files.append({'from': str(f), 'to': str(dest), 'bytes': size, 'file_id': st.st_ino,
                          'expected_sha256': sha or digest(f), 'expected_origin': origin})
    R['files'] = files; save()
    stopped = False; committed = False
    try:
        R['phase'] = 'unloading-daily'; save()
        R['unload'] = api('/unload?wait=30', {}, timeout=90)
        assert not api('/health')['loaded']
        stop_tree(daily_proc); stopped = True
        for a,b in moves:
            b.parent.mkdir(parents=True, exist_ok=True)
            safe(a); safe(b); assert not b.exists()
            os.rename(a,b)
            R['moves'].append({'from': str(a), 'to': str(b)}); save()
        replacements = [(str(a), str(b)) for a,b in moves[:6]]
        def replace(v):
            if isinstance(v,str):
                for a,b in replacements: v = v.replace(a,b)
                return v
            if isinstance(v,list): return [replace(x) for x in v]
            if isinstance(v,dict): return {k:replace(x) for k,x in v.items()}
            return v
        for p in [DAILY,Q36]:
            p.write_text(json.dumps(replace(json.loads(originals[p])),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        pack_new = DEEP / DSNAME / 'maya-ds4/ds4.txt'
        pack_new.write_bytes(original_pack.replace(str(STRATA / DSNAME).encode(),str(DEEP / DSNAME).encode()))
        assert pack_new.read_bytes() != original_pack
        cfg = replace(json.loads((ROOT / 'reports/tobeo-20261029/deepseek41-case/execution-03/config.json').read_text(encoding='utf-8')))
        cfg['log'] = str(OUT / 'deepseek-engine.log')
        DSCFG.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        R['phase'] = 'full-post-move-hash-verification'; save()
        for f in files:
            p = Path(f['to']); s = p.stat()
            expected_size = f['bytes']
            if p == pack_new:
                expected_size = len(original_pack.replace(str(STRATA / DSNAME).encode(),str(DEEP / DSNAME).encode()))
            assert s.st_size == expected_size and s.st_ino == f['file_id'], p
            expected_sha = f['expected_sha256']
            if p == pack_new:
                expected_sha = hashlib.sha256(original_pack.replace(str(STRATA / DSNAME).encode(),str(DEEP / DSNAME).encode())).hexdigest()
            actual = digest(p); assert actual == expected_sha, p
            R['hashes'].append({'path':str(p),'sha256':actual,'passed':True,'same_file_id':True,'intentional_pack_path_patch':p==pack_new}); save()
        exe = Path(cfg['exe'])
        command = [str(exe),'--pack',str(pack_new.parent),'--pack-info']
        cp = subprocess.run(command,capture_output=True,timeout=90)
        (OUT/'pack-info.stdout.log').write_bytes(cp.stdout);(OUT/'pack-info.stderr.log').write_bytes(cp.stderr)
        R['pack_info'] = {'command':command,'exit_code':cp.returncode};assert cp.returncode==0
        committed = True
        for path in [DAILY,Q36,DSCFG]:
            data=json.loads(path.read_text(encoding='utf-8'))
            for value in [data.get('tokenizer','')]+data.get('args',[]):
                if value.startswith(('D:\\','E:\\')): assert Path(value).exists(),value
        # Use the frozen controller helpers without changing the old evidence or controller.
        spec = importlib.util.spec_from_file_location('frozen_case',ROOT/'reports/tobeo-20261029/deepseek41-case/run_case.py')
        m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        m.RUN=OUT/'deepseek-validation';m.RUN.mkdir();m.record={'config':cfg,'loads':[]};m.write(m.RUN/'config.json',cfg)
        for key in ['DS4_EG_DIRECT','DS4_EG_CHECK','DS4_ENGRAM_CACHE_MB','DS4_STORE_GB']:
            os.environ.pop(key,None)
        R['phase']='deepseek-real-load-and-request';save()
        try:
            m.start_server('moved-pack')
            row=m.ask('paris',m.user('What is the capital of France? Answer only the city name.'),32)
            assert 'paris' in row['content'].lower(),row
            R['deepseek_request']=row
            m.api('/unload?wait=30',{},timeout=90)
        finally:m.stop_server()
        R['phase']='restoring-daily';save()
    except Exception as e:
        R['error']=repr(e)
        if not committed and stopped:
            R['phase']='rolling-back';save()
            for step in reversed(R['moves']):
                a,b=Path(step['from']),Path(step['to']);safe(a);safe(b)
                assert not a.exists();a.parent.mkdir(parents=True,exist_ok=True);os.rename(b,a)
            for p,data in originals.items():p.write_bytes(data)
            pack_old.write_bytes(original_pack)
            if DSCFG.exists():DSCFG.unlink()
            R['rolled_back']=True
        raise
    finally:
        if stopped:
            try:start_daily();R['daily_restored']=True
            except Exception as e:R['restore_error']=repr(e)
        save()
    assert R.get('daily_restored') and not R.get('error') and not R.get('restore_error')
    R['phase']='qwen-real-request';save()
    response=api('/v1/chat/completions',{'model':'qwen3.8-flash-next-iq3_s','messages':[{'role':'user','content':'What is the capital of France? Answer only the city name.'}],
                 'max_tokens':32,'temperature':0,'stream':False,'chat_template_kwargs':{'enable_thinking':False}},timeout=180)
    (OUT/'qwen-response.json').write_text(json.dumps(response,ensure_ascii=False,indent=2),encoding='utf-8')
    assert 'paris' in response['choices'][0]['message']['content'].lower(),response
    R['qwen_request_passed']=True
    for p in [DAILY,Q36,DSCFG]:
        R.setdefault('config_after',[]).append({'path':str(p),'sha256':digest(p)})
    # Only remove a verified empty container; preserve every archived file.
    old_packs=safe(STRATA/'packs')
    if old_packs.exists() and not list(old_packs.iterdir()):old_packs.rmdir()
    R['phase']='complete';R['passed']=True;R['finished']=datetime.now().astimezone().isoformat();save()


if __name__=='__main__':
    try:main()
    except Exception as e:
        R['error']=repr(e);R['phase']='failed'
        if OUT.exists():save()
        raise
