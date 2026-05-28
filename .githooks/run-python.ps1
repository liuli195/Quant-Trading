$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Project virtualenv Python not found. Create or repair .venv before running hooks."
    Write-Error "Expected: .venv\Scripts\python.exe"
    exit 127
}

& $Python @args
exit $LASTEXITCODE
