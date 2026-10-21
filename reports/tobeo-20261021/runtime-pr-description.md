## Problem and result

On Windows, the Python executable inside a venv can be a redirector. `Popen.pid` then belongs to the launcher, while the interpreter writes its own PID to the server's ready file. Both readiness checks require exact PID equality, so an already healthy model stays `starting` and a managed start/update times out.

This accepts the ready PID when it is either the owned process or its direct Windows child. Instance identity, launch attestation and the generation probe are still required. The runtime continues to stop its original owned process/job, not a PID taken from the ready file.

## Related discussion

No matching redirector-PID issue or PR found after searching open and closed discussions for Anaconda, redirector, child.pid and virtual environment. This is a focused lifecycle bug fix; no engine default changes.

The separate Windows default-DACL problem discussed in #3428 affects one existing test below and is not changed here.

## Approach

Use a Tool Help process snapshot to check the direct parent without requiring a query handle to the interpreter. Apply the same check at initial readiness and explicit verification. Snapshot failures and unrelated PIDs do not qualify. Same-PID and non-Windows behavior retain the existing path.

References: [CPython venv redirectors](https://docs.python.org/3.12/library/venv.html), [Microsoft process snapshots](https://learn.microsoft.com/en-us/windows/win32/toolhelp/taking-a-snapshot-and-viewing-processes).

## Validation

Tested diff committed as `41e534b3`, based on `9de04cd4`. Windows 11 Pro 26200, Python 3.12.7 venv created by Anaconda, i7-12700, RTX 5060 Ti 16 GB, 128 GB RAM.

**Passed:**

- `python -m unittest discover -s tests/terminal -p test_winproc_parent.py -v`: 4/4. Includes an actual venv interpreter whose PID differs from its launcher's, invalid IDs and snapshot failure.
- `python -m unittest discover -s tests/terminal -p test_runtime.py -k test_start_profile_revision_restart_and_stop -v`: passes; the same existing test fails on unmodified base with exit code 8 at start.
- `python -m unittest discover -s tests/terminal -p test_updater.py -k test_update_downloads_verifies_test_starts_then_switches -v`: passes.
- Full `test_runtime.py`: 38 pass, 2 platform skips, 1 existing failure detailed below. The new unrelated-PID test, changed-config attestation rejection, zero-token rejection and lifecycle/restart checks pass.
- Real model through the patched managed runtime using the venv: start, explicit verification, Chinese generation and stop pass. Owned launcher PID 27848; ready interpreter PID 27992. Signed CUDA engine 0.1.46, original GSQ-RCO IQ3_S, 64K context, INT8 KV with 32K resident, MTP on. This is lifecycle validation, not a performance claim.
- `git diff --check`.

**Failed:**

- Full `python -m unittest discover -s tests/terminal -p test_runtime.py -v`: 41 run, one failure in `test_liveness_check_does_not_end_the_process_it_asks_about` (`_pid_exists` remains true after killing the victim), two skips.
- That liveness assertion also fails on unmodified `9de04cd4` after `private_files.adopt_user_defaults()`, as CLI entry does. It passes in isolation before that default-DACL change. This is reported separately from the fixed readiness timeout; the suite is not claimed green.

**Not run:**

- Linux/macOS execution, other Python/venv distributions, full Terminal suite.
- CUDA/HIP/SYCL/Metal builds: no native backend source is changed. Real execution above used the published CUDA engine.

## Limits

Only a direct Windows launcher child qualifies; arbitrary descendant trees do not. No file ACLs, process priorities, model data, sampling, cache sizes or engine defaults are changed. The Windows default-DACL failure remains. Draft for review of the ownership check and additional platform coverage.


## Follow-up: separate DACL failure verified (2026-10-21)

On an isolated local validation branch, cherry-picked #3428 commit `14b1d8f095042559f15ad0ae6dd882c4a0a3cc8d` on top of this PR's `41e534b3` (combined local commit `44b16b88`). This PR's branch is unchanged; #3428 is not included here.

Using the same Windows 11 / Python 3.12.7 venv, explicitly called `private_files.adopt_user_defaults()` before discovering and running `test_runtime.py`: **41 tests, 39 passed, 2 platform skips, zero failures**, 242.332 seconds. The previously failing liveness test also passed in isolation with those token defaults applied. `test_private_files.py`: 13 passed, 1 platform skip; `test_winproc_parent.py`: 4 passed.

These results support #3428 as the fix for the separate default-DACL failure. They validate the combined local revision, not an all-green claim for this PR alone. The earlier failed result above remains the result for this PR without #3428. A clean next step is to sync and retest this branch after #3428 lands. At this check, the three workflows attached to this PR's head report `action_required`; no successful CI result is claimed.
