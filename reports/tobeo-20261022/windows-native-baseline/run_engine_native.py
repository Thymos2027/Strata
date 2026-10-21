"""Launch the native Strata binary with its isolated CUDA runtime DLL directory."""
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "build-native-baseline"
BUILD = ROOT / "build-83e6b05cd7b97ee194f330f0247faa76deb73f1b-cuda132-sm120"
CUDA = ROOT / "toolchains/cuda-13.2.0"

if __name__ == "__main__":
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(CUDA / "bin/x64"), str(CUDA / "bin"),
                                  str(BUILD), env.get("PATH", "")])
    raise SystemExit(subprocess.call([str(BUILD / "strata.exe"), *sys.argv[1:]], env=env))
