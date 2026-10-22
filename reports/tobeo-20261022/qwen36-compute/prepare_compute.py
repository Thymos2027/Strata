"""Prepare official Windows Nsight Compute with resumable, verified downloads."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
TOOLS = REPO / 'build-native-baseline/toolchains'
DOWNLOADS = TOOLS / 'downloads'


def main():
    import msvcrt
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, choices=range(1,33), default=16)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('nsight_download',
        OUT.parent / 'qwen36-profiling/prepare_nsight.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    spec = importlib.util.spec_from_file_location('verified_download',
        REPO / 'reports/tobeo-20261021/qwen36-source-baseline/prepare_cuda.py')
    download = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(download)
    download.DOWNLOADS = DOWNLOADS
    download.download_ranges = lambda url,path,size: helper.download_ranges(url,path,size,args.workers)
    manifest_path = DOWNLOADS / 'redistrib_13.3.1.json'
    manifest = json.loads(manifest_path.read_text())
    component = manifest['nsight_compute']
    with (DOWNLOADS / 'nsight-compute-prepare.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            name, archive, entry = download.download(('nsight_compute', component['windows-x86_64']))
            destination = TOOLS / ('nsight-compute-' + component['version'])
            destination.mkdir(exist_ok=True)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(destination)
            commands = list(destination.rglob('ncu.exe'))
            if len(commands) != 1:
                raise RuntimeError(f'Expected one ncu.exe, got {commands}')
            record = {'component':name, 'version':component['version'], **entry,
                      'destination':str(destination), 'command':str(commands[0]), 'manifest':str(manifest_path)}
            (OUT/'compute-installed.json').write_text(json.dumps(record,indent=2))
            subprocess.run([str(commands[0]),'--version'],check=True)
            print('Nsight Compute ready:',commands[0],flush=True)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
