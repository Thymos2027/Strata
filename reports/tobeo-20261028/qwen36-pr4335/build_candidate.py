"""Reuse the audited native build procedure for the unchanged PR4335 head."""
import runpy
import shutil
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
PREVIOUS=OUT.parent/'qwen36-pr4347'
sys.path.insert(0,str(PREVIOUS))
import build_pair as build

REVISION='bdf0bce2e5520680524efd3a5cf79db984c3902c'
build.OUT=OUT
build.CANDIDATE=REVISION
build.ARMS={'pr4335':{'revision':REVISION,
    'source':build.ROOT/'src-pr4335-bdf0bce2',
    'build':build.ROOT/'build-pr4335-bdf0bce2-cuda132-sm120'}}
build.main()
shutil.copyfile(PREVIOUS/'file_entry.cpp',OUT/'file_entry.cpp')
runpy.run_path(str(PREVIOUS/'build_file_entry.py'),run_name='__main__')
