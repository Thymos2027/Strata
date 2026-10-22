"""Export completed supported-driver traces with the matching Nsight CLI."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'cuda133-process'


def main():
    installed = json.loads((ROOT / 'nsight-installed-13.3.1.json').read_text())
    commands = list(Path(installed['destination']).rglob('nsys.exe'))
    if len(commands) != 1:
        raise RuntimeError('Expected one matching Nsight CLI')
    for mtp in (0, 2):
        for case in ('r0-l1024', 'r0-l16384'):
            tag = case + '-mtp' + str(mtp)
            result = json.loads((OUT / (tag + '.json')).read_text())
            if not result.get('validation_passed'):
                raise RuntimeError('Capture validation missing: ' + tag)
            database = OUT / (tag + '.sqlite')
            if database.exists():
                print('Keeping existing SQLite:', tag, flush=True)
                continue
            with (OUT / (tag + '.export.log')).open('w') as log:
                subprocess.run([str(commands[0]), 'export', '--type=sqlite', '--output=' + str(database),
                                str(OUT / (tag + '.nsys-rep'))], stdout=log, stderr=subprocess.STDOUT, check=True)
            print('Exported:', tag, flush=True)


if __name__ == '__main__':
    main()
