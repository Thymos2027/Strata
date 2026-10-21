"""Windows entry point: unload the existing local service, test, restore in finally."""
import json
from pathlib import Path
import subprocess
import urllib.request

OUT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8080"


def request(path, post=False, timeout=600):
    req = urllib.request.Request(URL + path, data=b"{}" if post else None,
                                 headers={"Content-Type": "application/json", "Origin": URL})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def main():
    state = {"health_before": request("/health", timeout=10)}
    unloaded = False
    result = 1
    try:
        state["unload"] = request("/unload?wait=30", post=True)
        if state["unload"].get("status") not in ("unloaded", "not loaded"):
            raise RuntimeError(f"service did not release model: {state['unload']}")
        unloaded = True
        print("Service model unloaded; starting WSL correctness checks", flush=True)
        with (OUT / "correctness-run.console.log").open("w", encoding="utf-8") as log:
            result = subprocess.call(
                ["wsl", "-d", "Ubuntu", "--", "python3", "-u",
                 "/mnt/e/Coder/LLM/Strata/reports/tobeo-20261021/qwen36-source-baseline/run_correctness.py"],
                stdout=log, stderr=subprocess.STDOUT)
        state["correctness_exit_code"] = result
    finally:
        try:
            if unloaded and state["health_before"].get("loaded"):
                print("Restoring original service model", flush=True)
                state["load"] = request("/load", post=True)
                state["health_after"] = request("/health", timeout=10)
        except Exception as exc:
            state["restore_error"] = repr(exc)
            raise
        finally:
            (OUT / "service-transition.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    if state.get("health_before", {}).get("loaded") and not state.get("health_after", {}).get("loaded"):
        raise RuntimeError("original model did not restore")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
