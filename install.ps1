# Install or upgrade agent-kit on Windows.
#
#   irm https://raw.githubusercontent.com/edvardsanta/agent-kit/main/install.ps1 | iex
#
# Environment:
#   AGENT_KIT_VERSION    tag to install (default: the most recent release, pre-releases included)
#   AGENT_KIT_SOURCE     pip requirement to install instead of the GitHub tag (e.g. a checkout path)
#   AGENT_KIT_INSTALLER  uv, pipx or venv (default: the first of uv, pipx found, else venv)
# runs in its own scope so `iex` leaves the caller's session untouched
& {
    $ErrorActionPreference = 'Stop'

    $Repo = 'edvardsanta/agent-kit'
    $DataDir = Join-Path $env:LOCALAPPDATA 'agent-kit'
    $BinDir = Join-Path $DataDir 'bin'

    function Say($Message) { [Console]::Error.WriteLine("[agent-kit] $Message") }
    # throw, not exit: under `irm | iex` exit would close the user's terminal
    function Fail($Message) { throw "agent-kit install: error: $Message" }
    function Has($Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
    function Run {
        & $args[0] @($args | Select-Object -Skip 1)
        if ($LASTEXITCODE -ne 0) { Fail "$($args[0]) failed with exit code $LASTEXITCODE" }
    }
    # persist for new terminals and apply now, so agent-kit works right after `irm | iex`
    function AddToPath($Dir) {
        $UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        if (($UserPath -split ';') -notcontains $Dir) {
            [Environment]::SetEnvironmentVariable('Path', "$UserPath;$Dir".Trim(';'), 'User')
            Say "added $Dir to your user PATH"
        }
        if (($env:Path -split ';') -notcontains $Dir) { $env:Path = "$Dir;$env:Path" }
    }

    if (-not (Has 'git')) { Fail 'git is required; install Git for Windows and run this again' }

    $Python = $null
    foreach ($Candidate in @(@('py', '-3'), @('python'), @('python3'))) {
        if (-not (Has $Candidate[0])) { continue }
        $Path = & $Candidate[0] @($Candidate | Select-Object -Skip 1) -c `
            'import sys; print(sys.executable if sys.version_info >= (3, 10) else '''')' 2>$null
        if ($LASTEXITCODE -eq 0 -and $Path) { $Python = "$Path".Trim(); break }
    }
    if (-not $Python) { Fail 'Python 3.10 or newer is required (https://www.python.org/downloads/)' }

    if ($env:AGENT_KIT_SOURCE) {
        $Source = $env:AGENT_KIT_SOURCE
    } else {
        $Version = $env:AGENT_KIT_VERSION
        if (-not $Version) {
            try {
                $Releases = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases?per_page=1"
            } catch {
                Fail 'could not look up the latest release; set AGENT_KIT_VERSION'
            }
            $Version = @($Releases)[0].tag_name
            if (-not $Version) { Fail 'no release found; set AGENT_KIT_VERSION' }
        }
        $Source = "git+https://github.com/$Repo@$Version"
    }

    $Installer = $env:AGENT_KIT_INSTALLER
    if (-not $Installer) {
        if (Has 'uv') { $Installer = 'uv' } elseif (Has 'pipx') { $Installer = 'pipx' } else { $Installer = 'venv' }
    }
    if ($Installer -notin @('uv', 'pipx', 'venv')) { Fail 'AGENT_KIT_INSTALLER must be uv, pipx or venv' }

    Say "installing $Source with $Installer"
    switch ($Installer) {
        'uv' {
            Run uv tool install --force --python $Python $Source
            AddToPath ("$(uv tool dir --bin)".Trim())
        }
        'pipx' {
            Run pipx install --force --python $Python $Source
            AddToPath ("$(pipx environment --value PIPX_BIN_DIR)".Trim())
        }
        'venv' {
            $Venv = Join-Path $DataDir 'venv'
            if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
            Run $Python -m venv $Venv
            Run (Join-Path $Venv 'Scripts\python.exe') -m pip install --quiet --disable-pip-version-check $Source
            # small wrappers, so PATH gets agent-kit without the venv's python and pip
            New-Item -ItemType Directory -Force $BinDir | Out-Null
            foreach ($Command in @('agent-kit', 'agent-init')) {
                $Target = Join-Path $Venv "Scripts\$Command.exe"
                Set-Content -Encoding ascii (Join-Path $BinDir "$Command.cmd") "@`"$Target`" %*"
            }
            AddToPath $BinDir
        }
    }

    if (-not (Has 'agent-kit')) { Fail 'installed, but agent-kit is still not on PATH' }
    Say "installed $(agent-kit --version); try: agent-kit doctor"
}
