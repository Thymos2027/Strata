"""Prepare SHA-256-verified official Windows Nsight Systems, without an installer."""
import argparse
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import time
import urllib.request
import zipfile

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
TOOLS = REPO / 'build-native-baseline/toolchains'
DOWNLOADS = TOOLS / 'downloads'


def download_ranges(url, path, size, workers):
    """Keep the previous 8 MiB part format, with configurable concurrency."""
    chunk = 8 * 1024 * 1024
    parts = path.with_name(path.name + '.parts')
    parts.mkdir(exist_ok=True)
    count = (size + chunk - 1) // chunk

    def fetch(index):
        start, end = index * chunk, min(size, (index+1)*chunk)-1
        part = parts / str(index)
        for attempt in range(12):
            have = part.stat().st_size if part.exists() else 0
            if have == end-start+1:
                return
            if have > end-start+1:
                invalid = part.with_name(part.name + '.invalid-' + str(time.time_ns()))
                part.replace(invalid)
                print('Quarantined oversized partial:', invalid, flush=True)
                have = 0
            try:
                req = urllib.request.Request(url, headers={'Range': f'bytes={start+have}-{end}'})
                with urllib.request.urlopen(req, timeout=45) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start+have}-{end}/{size}':
                        raise RuntimeError('Unexpected HTTP range response')
                    with part.open('ab') as dst:
                        while data := response.read(256*1024):
                            dst.write(data)
                if part.stat().st_size == end-start+1:
                    return
            except Exception as exc:
                print('range retry', index, attempt, str(exc)[:160], flush=True)
                time.sleep(min(3*(attempt+1),15))
        raise RuntimeError('Incomplete range: ' + str(index))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, i) for i in range(count)]
        for n, future in enumerate(concurrent.futures.as_completed(futures),1):
            future.result()
            print('range progress',n,'/',count,flush=True)
    assembled = path.with_name(path.name + '.assembled')
    with assembled.open('wb') as dst:
        for i in range(count):
            with (parts / str(i)).open('rb') as src:
                shutil.copyfileobj(src,dst)
    assembled.replace(path)


def prepare():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest-version', default='13.3.1')
    parser.add_argument('--workers', type=int, choices=range(1,33), default=16)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        'verified_downloader', REPO / 'reports/tobeo-20261021/qwen36-source-baseline/prepare_cuda.py')
    downloader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(downloader)
    downloader.DOWNLOADS = DOWNLOADS
    downloader.download_ranges = lambda url,path,size: download_ranges(url,path,size,args.workers)
    manifest_path = DOWNLOADS / ('redistrib_' + args.manifest_version + '.json')
    if not manifest_path.exists():
        urllib.request.urlretrieve(downloader.BASE + manifest_path.name, manifest_path)
    manifest = json.loads(manifest_path.read_text())
    component = manifest['nsight_systems']
    name, archive, entry = downloader.download(('nsight_systems', component['windows-x86_64']))
    destination = TOOLS / ('nsight-systems-' + component['version'])
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(destination)
    record = {'component': name, 'version': component['version'], **entry,
              'destination': str(destination), 'manifest': str(manifest_path)}
    (OUT / ('nsight-installed-' + args.manifest_version + '.json')).write_text(json.dumps(record, indent=2))
    commands = list(destination.rglob('nsys.exe'))
    print('NSYS commands:', [str(p) for p in commands], flush=True)
    for command in commands:
        subprocess.run([str(command), '--version'], check=True)


def main():
    import msvcrt
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    with (DOWNLOADS / 'nsight-prepare.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            prepare()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
