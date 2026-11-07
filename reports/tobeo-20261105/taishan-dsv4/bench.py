"""Bounded client-side throughput probe for the existing taishan service."""

import datetime as dt
import json
from pathlib import Path
import time

import requests


ROOT = Path(__file__).resolve().parent
BASE = "http://192.168.137.11:18080"
TZ = dt.timezone(dt.timedelta(hours=8))


def stamp():
    return dt.datetime.now(TZ).isoformat()


def write_status(**fields):
    (ROOT / "status.json").write_text(
        json.dumps({"updated_at": stamp(), **fields}, indent=2), encoding="utf-8"
    )


def main():
    session = requests.Session()
    session.trust_env = False
    health = session.get(BASE + "/health", timeout=15)
    health.raise_for_status()
    models = session.get(BASE + "/v1/models", timeout=15)
    models.raise_for_status()
    model = models.json()["data"][0]["id"]
    if "DeepSeek-V4-Flash-W8A8" not in model:
        raise RuntimeError(f"Unexpected model: {model}")

    seed = "The record describes a local inference system, its memory layout, request timing, and measured behavior. "
    cases = []
    for target in (1024, 4096):
        count = max(1, target // 20)
        for _ in range(8):
            prompt = f"Benchmark input {target}: " + seed * count + " Continue with a detailed explanation."
            response = session.post(BASE + "/tokenize", json={"prompt": prompt}, timeout=30)
            response.raise_for_status()
            tokenized = response.json()
            actual = int(tokenized["count"])
            if abs(actual - target) <= 64:
                break
            count = max(1, round(count * target / actual))
        else:
            raise RuntimeError(f"Could not reach {target} tokens: {actual}")
        cases.append((target, actual, prompt))

    write_status(phase="running", model=model, cases=[{"target": t, "tokens": n} for t, n, _ in cases], completed=0)
    results = []
    # One short warmup, then alternating lengths to reduce order effects.
    order = [(1024, 0)] + [(target, rep) for rep in range(1, 4) for target in ((1024, 4096) if rep % 2 else (4096, 1024))]
    by_target = {target: (actual, prompt) for target, actual, prompt in cases}
    for target, rep in order:
        actual, prompt = by_target[target]
        started = time.monotonic()
        first = None
        last_meta = {}
        done = False
        chunks = 0
        body = {
            "text": prompt,
            "sampling_params": {"temperature": 0, "max_new_tokens": 256 if rep else 32, "ignore_eos": True},
            "stream": True,
        }
        with session.post(BASE + "/generate", json=body, stream=True, timeout=(15, 600)) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    done = True
                    break
                event = json.loads(payload)
                if event.get("text") and first is None:
                    first = time.monotonic()
                if event.get("text"):
                    chunks += 1
                last_meta = event.get("meta_info") or last_meta
        finished = time.monotonic()
        output = int(last_meta.get("completion_tokens") or 0)
        if first is None or output < (32 if rep == 0 else 256):
            raise RuntimeError(f"Incomplete generation: target={target}, rep={rep}, output={output}, done={done}")
        item = {
            "target": target,
            "rep": rep,
            "input_tokens": actual,
            "output_tokens": output,
            "cached_tokens": last_meta.get("cached_tokens"),
            "ttft_s": first - started,
            "total_s": finished - started,
            "prefill_est_tok_s": actual / (first - started),
            "decode_est_tok_s": (output - 1) / (finished - first),
            "chunks": chunks,
            "done": done,
            "meta_info": last_meta,
            "completed_at": stamp(),
        }
        results.append(item)
        with (ROOT / "results.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(json.dumps({k: item[k] for k in ("target", "rep", "input_tokens", "output_tokens", "ttft_s", "total_s", "prefill_est_tok_s", "decode_est_tok_s")}), flush=True)
        write_status(phase="running", model=model, completed=len(results), total=len(order), latest=item["completed_at"])

    write_status(phase="completed", model=model, completed=len(results), total=len(order))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_status(phase="failed", error=repr(exc))
        raise
