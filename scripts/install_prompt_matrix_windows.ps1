param(
    [string]$IndexUrl = $(if ($env:PROMPT_MATRIX_PIP_INDEX_URL) { $env:PROMPT_MATRIX_PIP_INDEX_URL } else { "https://nitram1984.github.io/aidrax-prompt-matrix/simple" }),
    [string]$ExtraIndexUrl = $(if ($env:PROMPT_MATRIX_PIP_EXTRA_INDEX_URL) { $env:PROMPT_MATRIX_PIP_EXTRA_INDEX_URL } else { "https://pypi.org/simple" }),
    [string]$PackageName = $(if ($env:PROMPT_MATRIX_PACKAGE_NAME) { $env:PROMPT_MATRIX_PACKAGE_NAME } else { "aidrax-prompt-matrix" }),
    [string]$InstallRoot = "$env:LOCALAPPDATA\PromptMatrix",
    [string]$BinRoot = "$env:USERPROFILE\bin"
)

$ErrorActionPreference = "Stop"

function Get-PythonExe {
    $candidates = @(
        @("py", "-3.13"),
        @("py", "-3.12"),
        @("py", "-3.11"),
        @("py", "-3"),
        @("python")
    )

    foreach ($candidate in $candidates) {
        try {
            & $candidate[0] $candidate[1..($candidate.Length - 1)] --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }

    throw "Python 3 wurde auf Windows nicht gefunden."
}

function Invoke-Python {
    param(
        [string[]]$PythonCommand,
        [string[]]$Arguments
    )

    & $PythonCommand[0] $PythonCommand[1..($PythonCommand.Length - 1)] @Arguments
}

function Invoke-Checked {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Befehl fehlgeschlagen: $Executable $($Arguments -join ' ')"
    }
}

if (-not $IndexUrl) {
    throw "IndexUrl fehlt. Setze PROMPT_MATRIX_PIP_INDEX_URL oder uebergib -IndexUrl."
}

$pythonCommand = Get-PythonExe
$venvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"
$launcherPath = Join-Path $InstallRoot "prompt-manager-launcher.ps1"
$pipArgs = @()
if ($IndexUrl) {
    $pipArgs += @("--index-url", $IndexUrl)
}
if ($ExtraIndexUrl) {
    $pipArgs += @("--extra-index-url", $ExtraIndexUrl)
}

New-Item -ItemType Directory -Force -Path $InstallRoot, $BinRoot | Out-Null

if (-not (Test-Path $venvPython)) {
    Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "venv", (Join-Path $InstallRoot ".venv"))
}

Invoke-Checked -Executable $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked -Executable $venvPython -Arguments (@("-m", "pip", "install") + $pipArgs + @($PackageName))

$launcherContent = @"
param(
    [ValidateSet("cli", "gui", "manus")]
    [string]`$Mode = "cli",
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$ForwardArgs
)

`$ErrorActionPreference = "Stop"
`$PackageName = "$PackageName"
`$IndexUrl = "$IndexUrl"
`$ExtraIndexUrl = "$ExtraIndexUrl"
`$InstallRoot = "$InstallRoot"
`$VenvPython = Join-Path `$InstallRoot ".venv\Scripts\python.exe"
`$VenvScripts = Join-Path `$InstallRoot ".venv\Scripts"

function Get-InstalledVersion {
    try {
        (& `$VenvPython -c "import importlib.metadata as m; print(m.version('$PackageName'))" 2>`$null).Trim()
    } catch {
        ""
    }
}

function Get-LatestVersion {
    try {
        `$args = @("-m", "pip", "index", "versions", `$PackageName)
        if (`$IndexUrl) { `$args += @("--index-url", `$IndexUrl) }
        if (`$ExtraIndexUrl) { `$args += @("--extra-index-url", `$ExtraIndexUrl) }
        `$output = & `$VenvPython @args 2>`$null
        foreach (`$line in `$output) {
            if (`$line -match "LATEST:\s*([0-9A-Za-z.\-]+)") {
                return `$Matches[1]
            }
        }
        return ""
    } catch {
        return ""
    }
}

function Update-PackageIfNeeded {
    if (`$env:PROMPT_MATRIX_DISABLE_AUTO_UPDATE -eq "1") {
        return
    }

    `$installed = Get-InstalledVersion
    if (-not `$installed) {
        return
    }

    `$latest = Get-LatestVersion
    if (-not `$latest -or `$latest -eq `$installed) {
        return
    }

    Write-Host "Prompt Matrix-Update verfuegbar: `$installed -> `$latest"
    `$args = @("-m", "pip", "install", "--upgrade")
    if (`$IndexUrl) { `$args += @("--index-url", `$IndexUrl) }
    if (`$ExtraIndexUrl) { `$args += @("--extra-index-url", `$ExtraIndexUrl) }
    `$args += `$PackageName
    & `$VenvPython @args | Out-Null
}

Update-PackageIfNeeded

switch (`$Mode) {
    "cli" { & (Join-Path `$VenvScripts "prompt-manager.exe") @ForwardArgs }
    "gui" { & (Join-Path `$VenvScripts "prompt-manager-gui.exe") @ForwardArgs }
    "manus" { & (Join-Path `$VenvScripts "manus-web.exe") @ForwardArgs }
}
"@

Set-Content -Path $launcherPath -Value $launcherContent -Encoding UTF8

$promptManagerCmd = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "$launcherPath" cli %*
"@
$promptManagerGuiCmd = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "$launcherPath" gui %*
"@
$manusWebCmd = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "$launcherPath" manus %*
"@

Set-Content -Path (Join-Path $BinRoot "prompt-manager.cmd") -Value $promptManagerCmd -Encoding ASCII
Set-Content -Path (Join-Path $BinRoot "prompt-manager-gui.cmd") -Value $promptManagerGuiCmd -Encoding ASCII
Set-Content -Path (Join-Path $BinRoot "manus-web.cmd") -Value $manusWebCmd -Encoding ASCII

Write-Host "Prompt Matrix fuer Windows ist installiert."
Write-Host "Index: $IndexUrl"
Write-Host "Befehle: prompt-manager.cmd, prompt-manager-gui.cmd, manus-web.cmd unter $BinRoot"
