"""Summarize every run, preserve failures, and export a standalone context curve."""
import csv
import json
from pathlib import Path
import re
import statistics as stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent


def summary(values):
    return {"median": stats.median(values), "min": min(values), "max": max(values), "runs": values}


def main():
    report = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    rows = report["rows"]
    good = [row for row in rows if row["status"] == "ok"]
    metrics = ["decode_tok_s", "decode_ms_per_token", "prompt_tok_s", "client_ttft_s", "client_total_s",
               "client_tpot_ms", "prompt_ms", "decode_ms", "generated_tokens"]
    groups = []
    for target in (1024, 4096, 8192, 16384):
        for mtp in (0, 2):
            subset = sorted([r for r in good if r["target_tokens"] == target and r["mtp"] == mtp],
                            key=lambda r: r["repetition"])
            if not subset:
                continue
            group = {"target_tokens": target, "mtp": mtp, "n": len(subset),
                     "actual_prompt_tokens": [r["prompt_tokens"] for r in subset],
                     "accepted": sum(r["draft_accepted"] for r in subset),
                     "offered": sum(r["draft_offered"] for r in subset)}
            group.update({key: summary([r[key] for r in subset]) for key in metrics})
            groups.append(group)
    paired = []
    for target in (1024, 4096, 8192, 16384):
        pairs = []
        for rep in range(3):
            match = {r["mtp"]: r for r in good if r["target_tokens"] == target and r["repetition"] == rep}
            if 0 in match and 2 in match:
                a, b = match[0], match[2]
                pairs.append({"repetition": rep, "same_input": a["prompt_ids_sha256"] == b["prompt_ids_sha256"],
                              "same_output": a["output_sha256"] == b["output_sha256"],
                              "decode_ratio": b["decode_tok_s"] / a["decode_tok_s"]})
        if pairs:
            paired.append({"target_tokens": target, "pairs": pairs,
                           "ratio": summary([p["decode_ratio"] for p in pairs])})
    resources = [r["resources"] for r in good]
    samples = [s for resource in resources for s in resource["samples"]]
    arm_checks = []
    affinity_signatures = []
    for arm in report["arms"]:
        log = (OUT / (arm["arm"] + ".engine.log")).read_text(errors="replace")
        placement = re.search(r"hybrid experts: (\d+) of (\d+) per layer in VRAM \(([^)]+)\), all ([^\n]+?)host memory", log)
        chunk = re.search(r"context (\d+) cells, prompt chunk (\d+)", log)
        swaps = re.findall(r"(\d+) slot replacements", log)
        masks = sorted((t["group"], t["mask"]) for t in arm.get("thread_affinities", [])
                       if "mask" in t and int(t["mask"], 16).bit_count() == 1)
        affinity_signatures.append(masks)
        arm_checks.append({"arm": arm["arm"], "placement": placement.group(0) if placement else None,
                           "context": int(chunk[1]) if chunk else None, "chunk": int(chunk[2]) if chunk else None,
                           "slot_replacements": [int(s) for s in swaps], "single_cpu_thread_masks": masks,
                           "affinity_query_errors": [t for t in arm.get("thread_affinities", []) if "error" in t]})
    telemetry = {"sample_count": len(samples),
                 "rss_peak_gib": max(x["rss_peak_bytes"] for x in resources) / 2**30,
                 "private_peak_gib": max(x["private_peak_bytes"] for x in resources) / 2**30,
                 "whole_card_vram_peak_gib": max(x["card_vram_peak_bytes"] for x in resources) / 2**30,
                 "system_available_min_gib": min(x["system_available_min_bytes"] for x in resources) / 2**30,
                 "process_page_fault_deltas": [r["process_page_fault_delta"] for r in resources],
                 "sampling_errors": [r["error"] for r in resources if r["error"]]}
    for key in ("system_pages_input_s", "system_page_reads_s"):
        # The first rate sample covers time before the request (warm-up/idle).
        paging_samples = [s for resource in resources for s in resource["samples"][1:]]
        values = [s[key] for s in paging_samples if s[key] is not None]
        telemetry[key + "_max"] = max(values) if values else None
        telemetry[key + "_missing_samples"] = len(paging_samples) - len(values)
    checks = {"24_successful_requests": len(good) == 24 and len(rows) == 24,
              "three_per_cell": len(groups) == 8 and all(g["n"] == 3 for g in groups),
              "all_fresh": all(r["reused_tokens"] == 0 for r in good),
              "all_have_expected_mtp_state": all((r["draft_offered"] > 0) == (r["mtp"] == 2) for r in good),
              "all_same_paired_input": all(p["same_input"] for g in paired for p in g["pairs"]),
              "all_same_paired_output": all(p["same_output"] for g in paired for p in g["pairs"]),
              "fixed_context_chunk_placement": len(arm_checks) == 6 and all(
                  a["context"] == 32768 and a["chunk"] == 512 and a["placement"] is not None
                  and "64 of 256" in a["placement"] and bool(a["slot_replacements"])
                  and all(v == 0 for v in a["slot_replacements"])
                  for a in arm_checks),
              "same_seven_worker_cpu_masks": bool(affinity_signatures) and all(
                  masks == affinity_signatures[0] and len(masks) == 7 for masks in affinity_signatures),
              "telemetry_no_errors": not telemetry["sampling_errors"]}
    results = {"groups": groups, "paired": paired, "checks": checks, "telemetry": telemetry,
               "arms": arm_checks, "failures": [r for r in rows if r["status"] != "ok"]}
    (OUT / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    fields = ["arm", "case", "repetition", "mtp", "prompt_tokens", "generated_tokens", "reused_tokens",
              "prompt_ms", "decode_ms", "decode_ms_per_token", "decode_tok_s", "client_ttft_s", "client_total_s",
              "finish", "draft_accepted", "draft_offered", "output_sha256", "status"]
    with (OUT / "runs.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for mtp, color in ((0, "#2563eb"), (2, "#e67e22")):
        subset = [g for g in groups if g["mtp"] == mtp]
        xs = [stats.median(g["actual_prompt_tokens"]) for g in subset]
        for axis, metric, label in ((axes[0], "decode_ms_per_token", "Engine decode (ms/token)"),
                                    (axes[1], "client_ttft_s", "Protocol client TTFT (s)")):
            ys = [g[metric]["median"] for g in subset]
            lower = [g[metric]["min"] for g in subset]
            upper = [g[metric]["max"] for g in subset]
            axis.plot(xs, ys, "o-", label=f"MTP {mtp}", color=color)
            axis.fill_between(xs, lower, upper, color=color, alpha=0.15)
            for x, group in zip(xs, subset):
                axis.scatter([x] * len(group[metric]["runs"]), group[metric]["runs"], color=color, s=15, alpha=0.7)
            axis.set_ylabel(label)
    xs = [g["target_tokens"] for g in paired]
    axes[2].plot(xs, [g["ratio"]["median"] for g in paired], "o-", color="#16856b")
    axes[2].fill_between(xs, [g["ratio"]["min"] for g in paired], [g["ratio"]["max"] for g in paired],
                         color="#16856b", alpha=0.15)
    axes[2].axhline(1, color="gray", linestyle="--", linewidth=1)
    axes[2].set_ylabel("Paired decode tok/s ratio (MTP 2 / 0)")
    for axis in axes:
        axis.set_xticks([1024, 4096, 8192, 16384], ["1K", "4K", "8K", "16K"])
        axis.set_xlabel("Prompt tokens (K = 1024)")
        axis.grid(alpha=0.2)
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Qwen3.6 UD-Q4_K_XL | RTX 5060 Ti 16GB | native Windows | fixed 32K context, 64 expert slots")
    fig.text(0.5, 0.015, "3 repetitions per cell; lines = medians, bands = min/max; one synthetic mixed workload; no profiler", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(OUT / "context-curve.svg")
    fig.savefig(OUT / "context-curve.png", dpi=180)
    print(json.dumps({"checks": checks, "telemetry": telemetry, "groups": [
        {"tokens": g["actual_prompt_tokens"], "mtp": g["mtp"], "decode": g["decode_tok_s"],
         "ms_token": g["decode_ms_per_token"]["median"], "ttft": g["client_ttft_s"]["median"]}
        for g in groups]}, indent=2))


if __name__ == "__main__":
    main()
