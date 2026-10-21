"""Resumable background download of Strata's pinned Qwen3.6 Q4 artifact."""
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = Path(r'D:\Models\Qwen\Qwen3.6-35B-A3B-MTP-GGUF')
NAME = 'Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
URL = ('https://modelscope.cn/models/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/resolve/'
       '8350b673bcc0b2ae8eb2f7659a19d02fa8c78dc4/' + NAME)
SIZE = 22853663008
SHA256 = '55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1'


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    final = DEST / NAME
    partial = final.with_suffix('.gguf.part')
    status = ROOT / 'qwen36-download-status.json'
    def update(state, **extra):
        data = {'state': state, 'at': datetime.now(timezone.utc).isoformat(),
                'destination': str(final), 'partial': str(partial), 'url': URL,
                'expected_bytes': SIZE, 'expected_sha256': SHA256, **extra}
        temp = status.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temp.replace(status)
    try:
        if final.exists():
            target = final
        else:
            update('starting', downloaded_bytes=partial.stat().st_size if partial.exists() else 0)
            with (ROOT / 'qwen36-curl.log').open('ab') as log:
                proc = subprocess.Popen(['curl.exe', '--location', '--fail', '--silent', '--show-error',
                    '--connect-timeout', '30', '--speed-limit', '1024', '--speed-time', '120',
                    '--retry', '8', '--retry-all-errors', '--retry-delay', '10',
                    '--continue-at', '-', '--output', str(partial), '--url', URL],
                    stdout=log, stderr=log)
                previous = partial.stat().st_size if partial.exists() else 0
                previous_at = time.monotonic()
                while proc.poll() is None:
                    now = time.monotonic()
                    count = partial.stat().st_size if partial.exists() else 0
                    update('downloading', downloaded_bytes=count, curl_pid=proc.pid,
                           recent_bytes_per_second=max(0, count - previous) / max(0.001, now - previous_at))
                    previous, previous_at = count, now
                    time.sleep(10)
                if proc.returncode:
                    raise RuntimeError(f'curl exited {proc.returncode}; partial retained for resume; see qwen36-curl.log')
            target = partial
        if target.stat().st_size != SIZE:
            raise RuntimeError(f'Unexpected size: {target.stat().st_size}, expected {SIZE}')
        update('verifying', downloaded_bytes=SIZE)
        h = hashlib.sha256()
        with target.open('rb') as f:
            for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != SHA256:
            raise RuntimeError('SHA-256 mismatch; file retained for inspection')
        if target == partial:
            partial.rename(final)
        update('completed', downloaded_bytes=SIZE, sha256=h.hexdigest())
        print('Download and SHA-256 verification completed.', flush=True)
    except Exception as e:
        update('failed', error=str(e))
        raise


if __name__ == '__main__':
    main()
