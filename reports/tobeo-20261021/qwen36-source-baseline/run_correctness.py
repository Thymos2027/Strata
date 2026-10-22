"""Run the repository solo gate on one unchanged WSL source build.

Uses fixed CPU/GPU expert slots to separate kernel/MTP correctness from dynamic
placement rounding. Historical graph-* labels request the default graph mode,
but this revision disables actual graphs in main-hybrid mode. This does not
validate CUDA Graph execution, daily dynamic routing, or quality.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = Path.home() / "strata-research"
REVISION = "83e6b05cd7b97ee194f330f0247faa76deb73f1b"
SOURCE = ROOT / ("src-" + REVISION)
BUILD = ROOT / ("build-" + REVISION + "-cuda132-sm120")
CUDA = ROOT / "toolchains/cuda-13.2.0"
MODEL = "/mnt/d/Models/Qwen/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"
ENVIRONMENT = "WSL Ubuntu; CUDA 13.2.0; sm_120; GCC 14"


def run(command, name, env, timeout=900):
    print("RUN", name, flush=True)
    started = time.monotonic()
    with (OUT / (name + ".console.log")).open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=30)
            raise
    print("DONE", name, code, flush=True)
    return {"name": name, "command": command, "exit_code": code,
            "wall_s": time.monotonic() - started}


def main():
    env = os.environ.copy()
    if os.name != "nt":
        env["LD_LIBRARY_PATH"] = f"{CUDA}/lib:{CUDA}/lib64:/usr/lib/wsl/lib:" + env.get("LD_LIBRARY_PATH", "")
    env["STRATA_Q36_FIXED_SLOTS"] = "1"
    for name in ("STRATA_Q36_OLD_KERNELS", "STRATA_Q36_VERIFY"):
        env.pop(name, None)
    common = (f"--native {MODEL} --max-context 8192 --prefill 512 "
              "--pool-workers 7 --expert-vram 10.0 --expert-slots 64")
    arms = [
        ("old-nograph-mtp0", "--no-graph --mtp 0", {"STRATA_Q36_OLD_KERNELS": "1"}),
        ("verify-nograph-mtp0", "--no-graph --mtp 0", {"STRATA_Q36_VERIFY": "1"}),
        ("graph-mtp0", "--mtp 0", {}),
        ("graph-mtp2", "--mtp 2", {}),
    ]
    exe = BUILD / ("strata-q36.exe" if os.name == "nt" else "strata-q36")
    report = {"revision": REVISION, "exe": str(exe),
              "environment": ENVIRONMENT,
              "fixed_slots": True, "runs": [], "comparisons": [],
              "note": "Correctness baseline, not a speed benchmark or model quality evaluation."}
    report["exe_sha256"] = hashlib.file_digest(exe.open("rb"), "sha256").hexdigest()
    report["prompts_sha256"] = hashlib.file_digest(
        (SOURCE / "tools/qwen35/parity_prompts.ids").open("rb"), "sha256").hexdigest()
    try:
        for name, args, extra in arms:
            arm_env = {**env, **extra}
            command = [sys.executable, str(SOURCE / "tools/qwen35/q36_solo_gate.py"),
                       "--exe", str(exe), "--args", common + " " + args,
                       "--out", str(OUT / (name + ".json")), "--n", "128",
                       "--log", str(OUT / (name + ".engine.log"))]
            result = run(command, name, arm_env)
            result["environment_overrides"] = {"STRATA_Q36_FIXED_SLOTS": "1", **extra}
            report["runs"].append(result)
            if result["exit_code"]:
                raise RuntimeError(f"gate execution failed: {name}")
        reference = json.loads((OUT / (arms[0][0] + ".json")).read_text())["tokens"]
        for name, _, _ in arms[1:]:
            current = json.loads((OUT / (name + ".json")).read_text())["tokens"]
            # Check prompt counts too: the upstream comparison script uses zip.
            identical = len(reference) == len(current) == 10 and reference == current
            command = [sys.executable, str(SOURCE / "tools/qwen35/q36_cmp_gate.py"),
                       str(OUT / (arms[0][0] + ".json")), str(OUT / (name + ".json"))]
            result = run(command, "compare-" + name, env)
            result["strict_identical"] = identical
            report["comparisons"].append(result)
        verify_log = (OUT / "verify-nograph-mtp0.engine.log").read_text(errors="replace")
        report["verify_mismatch_lines"] = [line for line in verify_log.splitlines()
                                           if "VERIFY MISMATCH" in line]
        report["verify_summary_lines"] = [line for line in verify_log.splitlines()
                                          if "VERIFY" in line and "MISMATCH" not in line]
        summaries = re.findall(r"VERIFY: (\d+) comparisons, (\d+) mismatches", verify_log)
        report["verify_completed"] = bool(summaries) and all(int(n) > 0 and int(bad) == 0
                                                            for n, bad in summaries)
        report["passed"] = (all(x["strict_identical"] and x["exit_code"] == 0
                                for x in report["comparisons"])
                            and report["verify_completed"] and not report["verify_mismatch_lines"])
    finally:
        (OUT / "correctness-summary.json").write_text(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
