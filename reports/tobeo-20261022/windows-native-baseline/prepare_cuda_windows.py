"""Prepare official CUDA 13.2 Windows redistributables without installing a driver.

Shares the resumable SHA-256-checked downloader with the earlier WSL preparation
script. Extraction and all installed binaries here are Windows native.
"""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
TOOLS = REPO / "build-native-baseline/toolchains"
VERSION = "13.2.0"
DOWNLOADS = TOOLS / "downloads"
TOOLKIT = TOOLS / ("cuda-" + VERSION)
COMPONENTS = ["cuda_nvcc", "cuda_cudart", "cuda_cccl", "cuda_crt", "libnvvm", "libcublas"]


def main():
    spec = importlib.util.spec_from_file_location(
        "verified_downloader", REPO / "reports/tobeo-20261021/qwen36-source-baseline/prepare_cuda.py")
    downloader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(downloader)
    downloader.DOWNLOADS = DOWNLOADS
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    TOOLKIT.mkdir(parents=True, exist_ok=True)
    manifest_path = DOWNLOADS / ("redistrib_" + VERSION + ".json")
    if not manifest_path.exists():
        urllib.request.urlretrieve(downloader.BASE + manifest_path.name, manifest_path)
    manifest = json.loads(manifest_path.read_text())
    items = [(name, manifest[name]["windows-x86_64"]) for name in COMPONENTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(downloader.download, items))
    records = []
    for name, archive, entry in archives:
        unpacked = DOWNLOADS / (name + "-" + VERSION + "-windows-extracted")
        unpacked.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(unpacked)
        children = list(unpacked.iterdir())
        if len(children) != 1 or not children[0].is_dir():
            raise RuntimeError(f"unexpected archive layout: {name}")
        shutil.copytree(children[0], TOOLKIT, dirs_exist_ok=True)
        records.append({"name": name, **entry})
    (TOOLKIT / "installed-manifest.json").write_text(json.dumps(records, indent=2))
    (OUT / "cuda-installed-manifest.json").write_text(json.dumps(records, indent=2))
    subprocess.run([str(TOOLKIT / "bin/nvcc.exe"), "--version"], check=True)
    print("Windows toolkit ready:", TOOLKIT, flush=True)


if __name__ == "__main__":
    main()
