# iprate

`iprate` is an independent terminal client that displays selected information from the Net.Coffee IP Lookup page without a browser. It lets you monitor your public IPv4 address and its reputation, including from an SSH session on a remote server. [Net.Coffee IP Lookup](https://ip.net.coffee/ip/)

## Data sources

ipify provides the public IPv4 address. [ipify API](https://www.ipify.org/)

In fullscreen mode, `iprate` sends that address to Net.Coffee, which provides the reputation scores, network and geolocation details, and history. [Net.Coffee IP Lookup](https://ip.net.coffee/ip/)

## Installation

Both installation methods use `uv`. `iprate` requires Python 3.8 or newer.

On Windows x86-64, use a CPython version with a matching `windows-curses` wheel. `uv` installs this dependency automatically. If your Python version lacks a matching wheel, add `--python 3.13` to the install command. [Available `windows-curses` wheels](https://pypi.org/project/windows-curses/#files)

### Install uv

On Linux or macOS, run the official installer in a terminal.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows, run the official installer from PowerShell.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new terminal and run `uv --version` to verify the installation. For Homebrew, WinGet, and other methods, see the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### Install from GitHub Releases

```bash
uv tool install "iprate @ https://github.com/kozimo/iprate/releases/latest/download/iprate.tar.gz"
```

Run `iprate` for the fullscreen interface or `iprate --ip` for the address alone. If your shell cannot find `iprate`, run `uv tool update-shell` and open a new terminal. If you previously installed a zipapp, check `command -v iprate` or `Get-Command iprate` and remove the old archive if it takes precedence.

### Build and install from a clone

With Git and `uv` installed, clone the repository and build a wheel. The same commands work in Bash and PowerShell.

```bash
git clone https://github.com/kozimo/iprate.git
cd iprate
uv build --wheel --no-sources
```

Pass the path printed by `uv build` to `uv tool install`. The example below uses the wheel for version `0.1.0`.

```bash
uv tool install ./dist/iprate-0.1.0-py3-none-any.whl
iprate --version
```

## Updates

If you installed from GitHub Releases, run this command to upgrade.

```bash
uv tool upgrade iprate
```

`uv` checks the same GitHub URL for upgrades. If the version and dependencies are already current, it reports `Nothing to upgrade`. It may still download and build the archive to check its version, and it can upgrade dependencies independently.

If you installed a local wheel, pull the changes, rebuild the wheel, and run the local install command with `--reinstall` and the new wheel path.

## Usage

### Command-line mode

| Command | Action |
| --- | --- |
| `iprate` | Open the fullscreen interface |
| `iprate --ip` | Print the public IPv4 address on one line and exit |
| `iprate --help` | Show available options |
| `iprate --version` | Show the installed version |

### TUI

`iprate` fetches data on startup and every hour by default. After a failed refresh, `STALE` marks the last successful result.

Red indicates high risk, orange or yellow indicates a warning, and green indicates a favorable result.

| Keys | Action |
| --- | --- |
| `Tab`, `Shift+Tab` | Switch tabs |
| `↑`, `↓`, `Home`, `End` | Scroll or jump to either end |
| `+`, `-` | Adjust the refresh frequency |
| `r` | Request a refresh |
| `q`, `Ctrl+C` | Quit |
