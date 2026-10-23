param(
    [string]$RunId = '',
    [ValidateRange(1, 86400)][int]$CaptureTimeout = 3600,
    [ValidateSet('application','kernel')][string]$ReplayMode = 'application',
    [ValidateSet('smoke','memory','full')][string]$Scope = 'smoke',
    [ValidateSet('all','none')][string]$CacheControl = 'all',
    [ValidateSet('r0-l1024','r0-l16384','both')][string]$Case = 'r0-l1024',
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$computePython = 'D:\Program Files\Anaconda\python.exe'
if (-not (Test-Path -LiteralPath $computePython)) { throw 'Use the Python environment documented in README.md' }
$computeArguments = @((Join-Path $PSScriptRoot 'run_compute.py'))
$computeArguments += @('--capture-timeout', [string]$CaptureTimeout)
$computeArguments += @('--replay-mode', $ReplayMode, '--scope', $Scope, '--case', $Case)
$computeArguments += @('--cache-control', $CacheControl)
if ($RunId) { $computeArguments += @('--run-id', $RunId) }
if ($DryRun) { $computeArguments += '--dry-run' }
& $computePython @computeArguments
if ($LASTEXITCODE -ne 0) { throw "Compute collection failed (exit $LASTEXITCODE); inspect the preserved logs." }
