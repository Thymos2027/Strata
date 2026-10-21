"""Windows-native four-arm Qwen3.6 correctness gate, with service restoration.

Reuses the same test matrix/strict comparator as the WSL report but executes .exe
binaries directly. No WSL process is invoked or Linux result used as the oracle.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
ROOT = REPO / "build-native-baseline"
REVISION = "83e6b05cd7b97ee194f330f0247faa76deb73f1b"
SOURCE = ROOT / ("src-" + REVISION)
BUILD = ROOT / ("build-" + REVISION + "-cuda132-sm120")
CUDA = ROOT / "toolchains/cuda-13.2.0"
URL = "http://127.0.0.1:8080"


def request(path, post=False):
    req = urllib.request.Request(URL + path, data=b"{}" if post else None,
                                 headers={"Content-Type": "application/json", "Origin": URL})
    with urllib.request.urlopen(req, timeout=600 if post else 10) as response:
        return json.load(response)


def native_run(command, name, env, timeout=900):
    print("RUN", name, flush=True)
    env = dict(env)
    env["PATH"] = os.pathsep.join([str(CUDA / "bin/x64"), str(CUDA / "bin"), str(BUILD), env.get("PATH", "")])
    started = time.monotonic()
    with (OUT / (name + ".console.log")).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=30)
            raise
    print("DONE", name, code, flush=True)
    return {"name": name, "command": command, "exit_code": code,
            "wall_s": time.monotonic() - started}


def main():
    if not (BUILD / "strata-q36.exe").exists():
        raise RuntimeError("build the Windows engine first")
    spec = importlib.util.spec_from_file_location(
        "correctness_matrix", REPO / "reports/tobeo-20261021/qwen36-source-baseline/run_correctness.py")
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    matrix.OUT, matrix.ROOT = OUT, ROOT
    matrix.SOURCE, matrix.BUILD, matrix.CUDA = SOURCE, BUILD, CUDA
    matrix.MODEL = "D:/Models/Qwen/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"
    matrix.ENVIRONMENT = "Windows native; MSVC 19.42; CUDA 13.2.0; sm_120"
    matrix.run = native_run
    # The shared matrix chooses its platform-specific executable name.
    state = {"health_before": request("/health")}
    unloaded = False
    try:
        state["unload"] = request("/unload?wait=30", post=True)
        if state["unload"].get("status") not in ("unloaded", "not loaded"):
            raise RuntimeError(f"service did not release the model: {state['unload']}")
        unloaded = True
        code = matrix.main()
        summary_path = OUT / "correctness-summary.json"
        summary = json.loads(summary_path.read_text())
        summary["environment"] = "Windows native; MSVC 19.42; CUDA 13.2.0; sm_120"
        summary["note"] = "Windows-only implementation-path parity, not a Linux/Windows speed or quality comparison."
        summary_path.write_text(json.dumps(summary, indent=2))
        state["correctness_exit_code"] = code
    finally:
        try:
            if unloaded and state["health_before"].get("loaded"):
                print("Restoring original Flash-Next service", flush=True)
                state["load"] = request("/load", post=True)
                state["health_after"] = request("/health")
        except Exception as exc:
            state["restore_error"] = repr(exc)
            raise
        finally:
            (OUT / "service-transition.json").write_text(json.dumps(state, indent=2))
    if state["health_before"].get("loaded") and not state.get("health_after", {}).get("loaded"):
        raise RuntimeError("original service did not restore")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
