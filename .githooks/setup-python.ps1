$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $RepoRoot

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[Console]::InputEncoding = $Utf8NoBom
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $RepoRoot "requirements-dev.txt"

function Test-Python312 {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$CommandArgs = @()
    )

    try {
        & $Command @CommandArgs -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-BootstrapPython312 {
    $Candidates = @(
        @{ Command = "py"; Args = @("-3.12") },
        @{ Command = "python3.12"; Args = @() },
        @{ Command = "python3"; Args = @() },
        @{ Command = "python"; Args = @() }
    )

    foreach ($Candidate in $Candidates) {
        if (-not (Get-Command $Candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }
        if (Test-Python312 -Command $Candidate.Command -CommandArgs $Candidate.Args) {
            return $Candidate
        }
    }

    return $null
}

$NeedsVenvRepair = $true
if (Test-Path -LiteralPath $VenvPython) {
    $NeedsVenvRepair = -not (Test-Python312 -Command $VenvPython)
}

if ($NeedsVenvRepair) {
    $Bootstrap = Get-BootstrapPython312
    if ($null -eq $Bootstrap) {
        Write-Error "Python 3.12 was not found. Install Python 3.12 or pin Python 3.12 in the Codex environment before running setup."
        exit 127
    }

    & $Bootstrap.Command @($Bootstrap.Args + @("-m", "venv", ".venv"))
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Error "Project virtualenv Python was not created at .venv\Scripts\python.exe"
    exit 127
}

if (-not (Test-Path -LiteralPath $Requirements)) {
    Write-Error "requirements-dev.txt not found"
    exit 127
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r $Requirements

git config core.hooksPath .githooks

Write-Output "Python environment is ready: $VenvPython"
