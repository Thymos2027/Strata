#!/usr/bin/env bash
set -euo pipefail
research_root="$HOME/strata-research"
revision=83e6b05cd7b97ee194f330f0247faa76deb73f1b
source_dir="$research_root/src-$revision"
build_dir="$research_root/build-$revision-cuda132-sm120"
cuda_dir="$research_root/toolchains/cuda-13.2.0"
export PATH="$cuda_dir/bin:/usr/local/bin:/usr/bin:/bin"
export LD_LIBRARY_PATH="$cuda_dir/lib:$cuda_dir/lib64:/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}"
export CUDACXX="$cuda_dir/bin/nvcc"
mkdir -p "$research_root/logs"
exec 9> "$research_root/build-baseline.lock"
flock -n 9 || { echo 'Another baseline build is already running'; exit 1; }
exec > >(tee "$research_root/logs/build-baseline.log") 2>&1
cmake -S "$source_dir" -B "$build_dir" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCUDAToolkit_ROOT="$cuda_dir" \
  -DCMAKE_C_COMPILER=/usr/bin/gcc-14 -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14 \
  -DSTRATA_GGML_DIR="$source_dir/third_party/llama.cpp" \
  -DSTRATA_BUILD_TESTS=OFF -DSTRATA_BUILD_CONVERSATION_TESTS=ON
cmake --build "$build_dir" --target strata strata-q36 conversation_cache_test conversation_split_failure_test conversation_memory_test --parallel 8
ctest --test-dir "$build_dir" --output-on-failure -R '^conversation_(cache|split_failure|memory)_test$'
"$build_dir/strata" --version
"$build_dir/strata" --families
