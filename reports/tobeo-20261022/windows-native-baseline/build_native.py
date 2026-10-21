"""Build an unchanged Strata revision with native MSVC, Ninja, and CUDA 13.2.

No WSL executable is used. All compiler environment changes are process-local.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
ROOT = REPO / "build-native-baseline"
REVISION = "83e6b05cd7b97ee194f330f0247faa76deb73f1b"
GGML_REVISION = "3cf03257f219afbe7334045ff7c6a06ac68c627d"
SOURCE = ROOT / ("src-" + REVISION)
BUILD = ROOT / ("build-" + REVISION + "-cuda132-sm120")
CUDA = ROOT / "toolchains/cuda-13.2.0"
HOST_TESTS = ["conversation_cache_test", "conversation_split_failure_test", "conversation_memory_test",
              "conversation_file_test", "session_save_reclaim_test", "message_boundary_test",
              "split_ring_test", "conv_cache_test", "draft_kv_plan_test", "coupled_draft_test",
              "spec_prob_test", "bf16_bits_test", "batch_rows_test", "batch_groups_test"]


def compiler_environment():
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    vs = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-version", "[17.0,18.0)",
                                  "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                                  "-property", "installationPath"], text=True).strip()
    if not vs:
        raise RuntimeError("VS 2022 C++ Build Tools was not found (including standalone products)")
    vcvars = Path(vs) / "VC/Auxiliary/Build/vcvars64.bat"
    batch = ROOT / "export-msvc-env.bat"
    batch.write_text(f'@echo off\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b 1\nset\n')
    result = subprocess.run(["cmd.exe", "/d", "/c", str(batch)], capture_output=True, text=True, check=True)
    env = {key.upper(): value for key, value in os.environ.items()}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key and not key.startswith("="):
            env[key.upper()] = value
    cmake_dir = Path(vs) / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin"
    ninja = shutil.which("ninja.exe")
    if not ninja:
        raise RuntimeError("Ninja not found")
    env["PATH"] = os.pathsep.join([str(CUDA / "bin/x64"), str(CUDA / "bin"), str(cmake_dir), str(Path(ninja).parent), env["PATH"]])
    env["CUDA_PATH"] = str(CUDA)
    env["CUDACXX"] = str(CUDA / "bin/nvcc.exe")
    env["CUDA_MODULE_LOADING"] = "EAGER"
    return env, str(cmake_dir / "cmake.exe"), vs


def prepare_source():
    if (SOURCE / ".source-ready.json").exists():
        return
    archive = ROOT / ("source-" + REVISION + ".zip")
    subprocess.run(["git", "-C", str(REPO), "archive", "--format=zip", "--output", str(archive), REVISION], check=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(SOURCE)
    ggml_archive = ROOT / ("llama-" + GGML_REVISION + ".tar.gz")
    if not ggml_archive.exists():
        subprocess.run(["curl.exe", "--fail", "--location", "--retry", "8", "--retry-all-errors",
                        "--continue-at", "-", "--output", str(ggml_archive),
                        "https://codeload.github.com/ggml-org/llama.cpp/tar.gz/" + GGML_REVISION], check=True)
    unpacked = ROOT / "ggml-extracted"
    unpacked.mkdir(exist_ok=True)
    with tarfile.open(ggml_archive) as tf:
        tf.extractall(unpacked, filter="data")
    ggml_source = unpacked / ("llama.cpp-" + GGML_REVISION)
    shutil.copytree(ggml_source, SOURCE / "third_party/llama.cpp", dirs_exist_ok=True)
    metadata = {"revision": REVISION, "ggml_revision": GGML_REVISION,
                "ggml_archive_sha256": hashlib.file_digest(ggml_archive.open("rb"), "sha256").hexdigest()}
    (SOURCE / ".source-ready.json").write_text(json.dumps(metadata, indent=2))
    (OUT / "source-manifest.json").write_text(json.dumps(metadata, indent=2))


def main():
    ROOT.mkdir(exist_ok=True)
    # Windows exclusive file lock avoids two Ninja processes sharing the build tree.
    import msvcrt
    with (ROOT / "build.lock").open("a+b") as lock:
        lock.seek(0)
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        prepare_source()
        env, cmake, vs = compiler_environment()
        cl = shutil.which("cl.exe", path=env["PATH"])
        if not cl:
            raise RuntimeError("vcvars64 did not provide an x64 compiler")
        ctest = str(Path(cmake).with_name("ctest.exe"))
        commands = [
            [cmake, "--version"], [cl], [str(CUDA / "bin/nvcc.exe"), "--version"],
            [cmake, "-S", str(SOURCE), "-B", str(BUILD), "-G", "Ninja",
             "-DCMAKE_BUILD_TYPE=Release", "-DSTRATA_ENABLE_CUDA=ON", "-DCMAKE_CUDA_ARCHITECTURES=120",
             "-DCUDAToolkit_ROOT=" + CUDA.as_posix(), "-DCMAKE_CUDA_COMPILER=" + (CUDA / "bin/nvcc.exe").as_posix(),
             "-DCMAKE_C_COMPILER=" + Path(cl).as_posix(), "-DCMAKE_CXX_COMPILER=" + Path(cl).as_posix(),
             "-DCMAKE_CUDA_HOST_COMPILER=" + Path(cl).as_posix(),
             "-DSTRATA_GGML_DIR=" + (SOURCE / "third_party/llama.cpp").as_posix(),
             "-DSTRATA_BUILD_TESTS=OFF", "-DSTRATA_BUILD_CONVERSATION_TESTS=ON",
             "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"],
            [cmake, "--build", str(BUILD), "--target", "strata", "strata-q36", *HOST_TESTS, "--parallel", "8"],
            [ctest, "--test-dir", str(BUILD), "--output-on-failure", "-R", "^(" + "|".join(HOST_TESTS) + ")$"],
            [str(BUILD / "strata.exe"), "--version"], [str(BUILD / "strata.exe"), "--families"],
        ]
        if "--runtime-only" in sys.argv:
            commands = commands[-2:]
            report = json.loads((OUT / "build-summary.json").read_text())
            build_ok = any("--build" in row["command"] and row["exit_code"] == 0
                           for row in report["commands"])
            tests_ok = any(Path(row["command"][0]).name.lower() == "ctest.exe" and row["exit_code"] == 0
                           for row in report["commands"])
            if report["revision"] != REVISION or not (build_ok and tests_ok):
                raise RuntimeError("runtime-only requires a successful build and selected tests on this revision")
        else:
            report = {"revision": REVISION, "vs_path": vs, "build": str(BUILD), "commands": []}
        with (OUT / "build-native.log").open("a", encoding="utf-8") as log:
            try:
                for i, command in enumerate(commands):
                    print("RUN", subprocess.list2cmdline(command), flush=True)
                    log.write("\nRUN " + subprocess.list2cmdline(command) + "\n")
                    log.flush()
                    started = time.monotonic()
                    result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
                    report["commands"].append({"command": command, "exit_code": result.returncode,
                                                "wall_s": time.monotonic() - started})
                    # cl with no input prints its version but exits nonzero.
                    if result.returncode and Path(command[0]).name.lower() != "cl.exe":
                        raise RuntimeError(f"command failed with {result.returncode}: {command}")
                report["passed"] = True
                report["binaries"] = {name: hashlib.file_digest((BUILD / name).open("rb"), "sha256").hexdigest()
                                      for name in ("strata.exe", "strata-q36.exe")}
            finally:
                (OUT / "build-summary.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
