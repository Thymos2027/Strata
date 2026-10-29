"""Build a pinned, unchanged upstream snapshot; never replace earlier evidence."""
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
ROOT = REPO / 'build-native-baseline'
REVISION = '46c152a1310f77cd2f0ce2c7cd213962df14fe83'
SOURCE = ROOT / 'src-main-46c152a1'
BUILD = ROOT / 'build-main-46c152a1-cuda132-sm120'
GGML_REVISION = '3cf03257f219afbe7334045ff7c6a06ac68c627d'
GGML_SHA = 'c076d7534afa0e5d0ec2a0d425b11e791c16f3de0d727221aea071cef156a280'
DEPENDENCIES = ROOT / 'deps-main-46c152a1'
CUDA = ROOT / 'toolchains/cuda-13.2.0'
MODEL = Path('D:/Models/Qwen/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf')
MODEL_SHA = '55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1'


def stamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def git(*args, cwd=REPO):
    return subprocess.check_output(['git', '-C', str(cwd), *args], text=True).strip()


def helper(relative, name):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('STRATA_', 'DS4_'))}
    env.update(STRATA_MMQ_KQ='1', STRATA_Q8_PACKED='1',
               CUDA_VISIBLE_DEVICES='0', CUDA_MODULE_LOADING='EAGER')
    env['PATH'] = os.pathsep.join([str(CUDA / 'bin/x64'), str(CUDA / 'bin'), str(BUILD), env.get('PATH', '')])
    return env


def source_version():
    text = (SOURCE / 'CMakeLists.txt').read_text(encoding='utf-8')
    match = re.search(r'project\(strata VERSION ([0-9.]+)', text)
    if not match:
        raise RuntimeError('Could not identify source engine version')
    return {'version': match.group(1), 'source': 'CMakeLists.txt',
            'standalone_cli_version_supported': False,
            'note': 'strata-q36 has no --version option; source version is not an installed release claim'}


def finalize_built():
    """Accept completed build/tests after fixing only the metadata probe."""
    path = OUT / 'build-results.json'
    record = json.loads(path.read_text(encoding='utf-8'))
    assert record.get('error') == "RuntimeError('Built engine version failed')"
    assert not record['passed'] and len(record['commands']) == 4
    assert all(command['exit_code'] == 0 for command in record['commands'])
    assert digest(OUT / 'build-attempt-02.json') == digest(path)
    assert record['script_sha256'] == digest(OUT / 'build-attempt-02.py')
    assert '100% tests passed, 0 tests failed out of 17' in (OUT / 'build-2.log').read_text()
    assert 'no work to do' in (OUT / 'build-3.log').read_text()
    assert git('rev-parse', 'HEAD', cwd=SOURCE) == REVISION
    assert not git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE)
    assert all(digest(BUILD / name) == sha for name, sha in record['binaries'].items())
    record['unsupported_version_probe'] = record.pop('engine_version')
    record['engine_version'] = source_version()
    record['previous_metadata_failure'] = 'build-attempt-02.json'
    record['finalizer_sha256'] = digest(__file__)
    record['tracked_changes_after'] = ''
    record['build_completed_at'] = record['finished']
    record['finished'] = stamp()
    record['passed'] = True
    del record['error']
    save(path, record)
    print('Build accepted: pinned source version, 17 tests, unchanged binaries', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-preparation', action='store_true')
    parser.add_argument('--finalize-built', action='store_true')
    args = parser.parse_args()
    if args.finalize_built:
        finalize_built()
        return
    destination = OUT / 'build-results.json'
    resume = args.resume_preparation
    if resume:
        previous = json.loads(destination.read_text(encoding='utf-8'))
        if previous.get('passed') or previous['commands'] or not (OUT / 'build-attempt-01.json').exists() or BUILD.exists():
            raise RuntimeError('Only an archived pre-build preparation failure can resume')
    elif destination.exists() or SOURCE.exists() or BUILD.exists() or DEPENDENCIES.exists():
        raise RuntimeError('Baseline evidence/source/build exists; do not overwrite')
    record = {'started': stamp(), 'passed': False, 'revision': REVISION,
              'source': str(SOURCE), 'build': str(BUILD), 'commands': [],
              'script_sha256': digest(__file__), 'plan_sha256': digest(OUT / 'experiment-plan.md'),
              'upstream_at_prepare': git('rev-parse', 'upstream/main'),
              'workspace_head': git('rev-parse', 'HEAD'), 'workspace_status': git('status', '--short'),
              'qwen_paths_changed_since_old': git('diff', '--name-only', '5e8a4cca', REVISION, '--', 'src/qwen35', 'tools/qwen35')}
    if resume:
        record['previous_preparation_failure'] = 'build-attempt-01.json'
    save(destination, record)
    try:
        if record['upstream_at_prepare'] != REVISION:
            raise RuntimeError('Unexpected upstream identity')
        if not resume:
            subprocess.run(['git', 'worktree', 'add', '--detach', str(SOURCE), REVISION], check=True)
        if git('rev-parse', 'HEAD', cwd=SOURCE) != REVISION or git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE):
            raise RuntimeError('Source has tracked edits')
        record['source_tree'] = git('rev-parse', 'HEAD^{tree}', cwd=SOURCE)
        archive = ROOT / ('llama-' + GGML_REVISION + '.tar.gz')
        record['ggml'] = {'revision': GGML_REVISION, 'archive': str(archive), 'sha256': digest(archive)}
        if record['ggml']['sha256'] != GGML_SHA:
            raise RuntimeError('ggml source archive changed')
        if not resume:
            DEPENDENCIES.mkdir()
            with tarfile.open(archive) as tar:
                tar.extractall(DEPENDENCIES, filter='data')
        ggml = DEPENDENCIES / ('llama.cpp-' + GGML_REVISION)
        record['ggml']['source'] = str(ggml)
        # Fingerprint actual dependency files used, including any later local changes.
        files = {p.relative_to(ggml).as_posix(): digest(p) for p in sorted(ggml.rglob('*')) if p.is_file()}
        if resume:
            if json.loads((OUT / 'ggml-files.json').read_text()) != files:
                raise RuntimeError('Prepared dependency files changed')
        else:
            save(OUT / 'ggml-files.json', files)
        record['ggml']['file_count'] = len(files)
        record['ggml']['files_manifest_sha256'] = digest(OUT / 'ggml-files.json')
        record['model'] = {'path': str(MODEL), 'bytes': MODEL.stat().st_size, 'sha256': digest(MODEL)}
        if record['model']['sha256'] != MODEL_SHA or record['model']['bytes'] != 22853663008:
            raise RuntimeError('Model fingerprint mismatch')
        native_path = 'reports/tobeo-20261022/windows-native-baseline/build_native.py'
        native = helper(native_path, 'native_build')
        # The helper only discovers vcvars/CMake; no old build entry point is run.
        record['compiler_helper_sha256'] = digest(REPO / native_path)
        python_dir = Path(sys.executable).parent
        os.environ['PATH'] = os.pathsep.join([str(python_dir / 'Scripts'), str(python_dir / 'Library/bin'), os.environ['PATH']])
        env, cmake, vs = native.compiler_environment()
        env = {k: v for k, v in env.items() if not k.startswith(('STRATA_', 'DS4_'))}
        cl = shutil.which('cl.exe', path=env['PATH'])
        ninja = shutil.which('ninja.exe', path=env['PATH'])
        tests = [*native.HOST_TESTS, 'model_family_test', 'qwen35_sampling_test', 'nv_defaults_test']
        record['tests'] = tests
        record['toolchain'] = {'vs': vs, 'cl': cl, 'cmake': cmake, 'ninja': ninja, 'cuda': str(CUDA), 'python': sys.executable}
        for name, command in {'cl': [cl], 'cmake': [cmake, '--version'], 'ninja': [ninja, '--version'],
                              'nvcc': [str(CUDA / 'bin/nvcc.exe'), '--version']}.items():
            result = subprocess.run(command, env=env, capture_output=True)
            raw = result.stdout + result.stderr
            (OUT / (name + '-version.log')).write_bytes(raw)
            record['toolchain'][name + '_version'] = raw.decode('utf-8', errors='replace').strip()
        commands = [
            [cmake, '-S', str(SOURCE), '-B', str(BUILD), '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             '-DSTRATA_ENABLE_CUDA=ON', '-DCMAKE_CUDA_ARCHITECTURES=120',
             '-DCUDAToolkit_ROOT=' + CUDA.as_posix(), '-DCMAKE_CUDA_COMPILER=' + (CUDA / 'bin/nvcc.exe').as_posix(),
             '-DCMAKE_C_COMPILER=' + Path(cl).as_posix(), '-DCMAKE_CXX_COMPILER=' + Path(cl).as_posix(),
             '-DCMAKE_CUDA_HOST_COMPILER=' + Path(cl).as_posix(), '-DSTRATA_GGML_DIR=' + ggml.as_posix(),
             '-DSTRATA_BUILD_TESTS=ON', '-DSTRATA_BUILD_CONVERSATION_TESTS=ON', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],
            [cmake, '--build', str(BUILD), '--target', 'strata-q36', 'strata_kq', *tests, '--parallel', '8'],
            [str(Path(cmake).with_name('ctest.exe')), '--test-dir', str(BUILD), '--output-on-failure', '-R', '^(' + '|'.join(tests) + ')$'],
            [ninja, '-C', str(BUILD), '-n', 'strata-q36', 'strata_kq', *tests],
        ]
        for i, command in enumerate(commands):
            print('RUN', i, subprocess.list2cmdline(command), flush=True)
            started = time.monotonic()
            with (OUT / f'build-{i}.log').open('w', encoding='utf-8') as log:
                result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            record['commands'].append({'command': command, 'exit_code': result.returncode, 'seconds': time.monotonic() - started})
            save(destination, record)
            if result.returncode:
                raise RuntimeError('Build/check failed at command ' + str(i))
        record['binaries'] = {name: digest(BUILD / name) for name in ['strata-q36.exe', 'strata_kq.dll']}
        record['build_files'] = {name: digest(BUILD / name) for name in ['CMakeCache.txt', 'compile_commands.json', 'build.ninja']}
        record['engine_version'] = source_version()
        record['tracked_changes_after'] = git('status', '--porcelain', '--untracked-files=no', cwd=SOURCE)
        if record['tracked_changes_after']:
            raise RuntimeError('Source changed')
        record['passed'] = True
    except BaseException as exc:
        record['error'] = repr(exc)
        raise
    finally:
        record['finished'] = stamp()
        save(destination, record)


if __name__ == '__main__':
    main()
