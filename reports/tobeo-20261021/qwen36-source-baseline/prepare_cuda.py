"""Install pinned NVIDIA redistributables into a user-owned WSL toolkit directory.

Run with Linux Python. Archives are resumed by curl and verified against NVIDIA's
SHA-256 manifest before extraction. No driver is installed or replaced.
"""
import concurrent.futures
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

BASE = "https://developer.download.nvidia.com/compute/cuda/redist/"
VERSION = "13.2.0"
ROOT = pathlib.Path.home() / "strata-research" / "toolchains"
DOWNLOADS = ROOT / "downloads"
TOOLKIT = ROOT / ("cuda-" + VERSION)
COMPONENTS = ["cuda_nvcc", "cuda_cudart", "cuda_cccl", "cuda_crt",
              "cuda_culibos", "libnvvm", "libcublas"]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def download(item):
    name, entry = item
    path = DOWNLOADS / pathlib.Path(entry["relative_path"]).name
    size = int(entry["size"])
    if size > 8 * 1024 * 1024 and (not path.exists() or path.stat().st_size != size):
        download_ranges(BASE + entry["relative_path"], path, size)
    elif not path.exists() or path.stat().st_size != size:
        print("downloading", name, entry["size"], flush=True)
        subprocess.run(["curl", "--fail", "--location", "--continue-at", "-",
                        "--retry", "8", "--retry-all-errors", "--retry-delay", "3", "--connect-timeout", "30",
                        "--output", str(path), BASE + entry["relative_path"]], check=True)
    actual = digest(path)
    if actual != entry["sha256"]:
        raise RuntimeError(f"SHA256 mismatch: {name}: {actual}")
    print("verified", name, actual, flush=True)
    return name, path, entry


def download_ranges(url, path, size):
    """Bound each request to 8 MiB; resume partial ranges after connection failures."""
    chunk = 8 * 1024 * 1024
    parts = path.with_name(path.name + ".parts")
    parts.mkdir(exist_ok=True)
    count = (size + chunk - 1) // chunk
    # Preserve usable bytes from an earlier single-stream download.
    if path.exists():
        with path.open("rb") as src:
            for i in range(count):
                data = src.read(chunk)
                if not data:
                    break
                part = parts / str(i)
                if not part.exists():
                    part.write_bytes(data)

    def fetch(i):
        start, end = i * chunk, min(size, (i + 1) * chunk) - 1
        part = parts / str(i)
        for attempt in range(10):
            have = part.stat().st_size if part.exists() else 0
            if have == end - start + 1:
                return i
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={start + have}-{end}"})
                with urllib.request.urlopen(req, timeout=45) as response:
                    expected = f"bytes {start + have}-{end}/{size}"
                    if response.status != 206 or response.headers.get("Content-Range") != expected:
                        raise RuntimeError(f"range not honored: {response.status}: {response.headers}")
                    with part.open("ab") as dst:
                        while data := response.read(256 * 1024):
                            dst.write(data)
                if part.stat().st_size == end - start + 1:
                    return i
            except Exception as exc:
                print("range retry", path.name, i, attempt, str(exc)[:140], flush=True)
                time.sleep(min(3 * (attempt + 1), 15))
        raise RuntimeError(f"range incomplete: {path.name}: {i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for done, _ in enumerate(pool.map(fetch, range(count)), 1):
            print("range progress", path.name, done, "/", count, flush=True)
    assembled = path.with_name(path.name + ".assembled")
    with assembled.open("wb") as dst:
        for i in range(count):
            with (parts / str(i)).open("rb") as src:
                shutil.copyfileobj(src, dst)
    assembled.replace(path)


def main():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    TOOLKIT.mkdir(parents=True, exist_ok=True)
    manifest_path = DOWNLOADS / ("redistrib_" + VERSION + ".json")
    if not manifest_path.exists():
        urllib.request.urlretrieve(BASE + manifest_path.name, manifest_path)
    manifest = json.loads(manifest_path.read_text())
    items = [(name, manifest[name]["linux-x86_64"]) for name in COMPONENTS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(download, items))
    records = []
    for name, path, entry in archives:
        unpacked = DOWNLOADS / (name + "-" + VERSION + "-extracted")
        unpacked.mkdir(exist_ok=True)
        with tarfile.open(path) as tf:
            tf.extractall(unpacked, filter="data")
        children = list(unpacked.iterdir())
        if len(children) != 1 or not children[0].is_dir():
            raise RuntimeError(f"unexpected archive layout: {name}")
        shutil.copytree(children[0], TOOLKIT, dirs_exist_ok=True, symlinks=True)
        records.append({"name": name, **entry})
    (TOOLKIT / "installed-manifest.json").write_text(json.dumps(records, indent=2))
    # Redistributable archives use lib/, while nvcc's Linux profile searches lib64/.
    if not (TOOLKIT / "lib64").exists():
        (TOOLKIT / "lib64").symlink_to("lib", target_is_directory=True)
    print("toolkit", TOOLKIT, flush=True)
    subprocess.run([str(TOOLKIT / "bin/nvcc"), "--version"], check=True)


if __name__ == "__main__":
    main()
