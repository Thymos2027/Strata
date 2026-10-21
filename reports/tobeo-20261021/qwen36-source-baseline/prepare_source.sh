#!/usr/bin/env bash
set -euo pipefail
research_root="$HOME/strata-research"
revision=83e6b05cd7b97ee194f330f0247faa76deb73f1b
ggml_revision=3cf03257f219afbe7334045ff7c6a06ac68c627d
source_dir="$research_root/src-$revision"
mkdir -p "$source_dir" "$research_root/downloads" "$research_root/logs"
git -C /mnt/e/Coder/LLM/Strata archive "$revision" | tar -x -C "$source_dir"
archive="$research_root/downloads/llama-$ggml_revision.tar.gz"
curl --fail --location --continue-at - --retry 8 --retry-all-errors --retry-delay 3 \
  --output "$archive" "https://codeload.github.com/ggml-org/llama.cpp/tar.gz/$ggml_revision"
tar -tzf "$archive" > "$research_root/logs/ggml-archive-files.txt"
mkdir -p "$source_dir/third_party/llama.cpp"
tar -xzf "$archive" --strip-components=1 -C "$source_dir/third_party/llama.cpp"
sha256sum "$archive" > "$research_root/logs/ggml-archive.sha256"
printf '%s\n' "$revision" > "$research_root/logs/source-revision.txt"
printf '%s\n' "$source_dir"
