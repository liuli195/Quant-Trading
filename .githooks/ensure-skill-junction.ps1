$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$AgentsSkills = Join-Path $RepoRoot ".agents\skills"
$ClaudeDir = Join-Path $RepoRoot ".claude"
$ClaudeSkills = Join-Path $ClaudeDir "skills"

function Resolve-ExistingPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    } catch {
        return $null
    }
}

function Test-ExpectedJunction {
    if (-not (Test-Path -LiteralPath $ClaudeSkills)) {
        return $false
    }

    $Item = Get-Item -LiteralPath $ClaudeSkills -Force
    if ($Item.LinkType -ne "Junction") {
        return $false
    }

    $Expected = Resolve-ExistingPath -Path $AgentsSkills
    foreach ($Target in @($Item.Target)) {
        if (-not $Target) {
            continue
        }
        $ResolvedTarget = Resolve-ExistingPath -Path $Target
        if ($ResolvedTarget -and $Expected -and $ResolvedTarget -eq $Expected) {
            return $true
        }
    }
    return $false
}

if (-not (Test-Path -LiteralPath $AgentsSkills -PathType Container)) {
    Write-Error ".agents\skills does not exist; cannot create .claude\skills Junction."
    exit 1
}

if (Test-ExpectedJunction) {
    exit 0
}

if (Test-Path -LiteralPath $ClaudeSkills) {
    $ResolvedClaudeSkills = (Resolve-Path -LiteralPath $ClaudeSkills).Path
    $ExpectedClaudeSkills = Join-Path $ClaudeDir "skills"
    if ($ResolvedClaudeSkills -ne $ExpectedClaudeSkills) {
        Write-Error "Refusing to remove unexpected path: $ResolvedClaudeSkills"
        exit 1
    }
    Remove-Item -LiteralPath $ClaudeSkills -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $ClaudeDir | Out-Null
$Result = cmd.exe /c mklink /J "$ClaudeSkills" "$AgentsSkills"
if ($LASTEXITCODE -ne 0) {
    Write-Error ($Result -join "`n")
    exit $LASTEXITCODE
}
