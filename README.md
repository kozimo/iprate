# iprate

`iprate` shows reputation, network, and geolocation details for your public IPv4 address in a terminal. ipify provides the address, and Net.Coffee provides the ratings and history.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run this command on Linux or macOS.

```bash
uv tool install "iprate @ https://github.com/kozimo/iprate/releases/latest/download/iprate.tar.gz"
```

On Windows x86-64, use PowerShell and request CPython 3.13, for which a `windows-curses` wheel is available. uv installs `windows-curses` automatically on Windows and downloads Python if needed.

```powershell
uv tool install --python 3.13 "iprate @ https://github.com/kozimo/iprate/releases/latest/download/iprate.tar.gz"
```

Run `iprate` for the fullscreen interface or `iprate --ip` for the address alone. If your shell cannot find `iprate`, run `uv tool update-shell` and open a new terminal. If you previously installed a zipapp, check `command -v iprate` or `Get-Command iprate` and remove the old archive if it takes precedence.

## Updates

Compare the output of `iprate --version` with the tag of the [latest stable release](https://github.com/kozimo/iprate/releases/latest) to check for a new version. To upgrade, run the following command.

```bash
uv tool upgrade iprate
```

uv checks the same GitHub URL for upgrades. If the version and dependencies are already current, it reports `Nothing to upgrade`. It may still download and build the archive to check its version, and it can upgrade dependencies independently.

## Running from source

You need Python 3.8 or later with HTTPS support and access to trusted certificates. Fullscreen mode requires a terminal and `curses`. On Linux and macOS, use a Python build with `curses` and a terminal with `TERM` set correctly. On Windows, install `windows-curses` in the environment if you run directly from source. Run these commands from the repository root (`python` in place of `python3` on Windows).

```bash
python3 main.py
python3 main.py --ip
python3 main.py --help
```

`--ip` writes a single IPv4 address to standard output. On error, it writes a message to standard error and returns a nonzero exit status. `--help` and `--version` work offline.

Each HTTPS request has a 10-second deadline. Replies are limited to 64 bytes from ipify and 2 MiB from Net.Coffee.

## Fullscreen mode

The address, status, and refresh timer appear at the top. The Overview tab groups reputation, network, and classification details. On every tab, panels fill the terminal width and share the same height within each row. In History, Datacenter Neighbors spans a full-width row below the other panels. As the terminal narrows, panels move to the next row. Table columns share the available panel width, long values wrap and align to the right, and long lists scroll.

Each reputation field uses the same color for its label and value. Red indicates high risk, orange indicates a warning, and green indicates a favorable rating or the absence of a specific risk signal. Reference data and unknown ratings use the terminal's default text color. A `Trust Score` below 50 is red, a score from 50 to just under 70 is orange, and a score of 70 or higher is green. Terminals with a basic color palette show warnings in yellow. [Net.Coffee guidance on Trust Score](https://ip.net.coffee/gpt/identity.html)

| Keys | Action |
| --- | --- |
| `Tab`, `Shift+Tab` | Switch to the next or previous tab |
| `↑`, `↓`, `Home`, `End` | Scroll or jump to the beginning or end of the list |
| `+`, `-` | Increase or decrease the refresh frequency |
| `r` | Refresh data |
| `q`, `Ctrl+C` | Quit |

The first refresh starts immediately. The default refresh interval is one hour. `UPDATING` means a request is in progress, `ONLINE` means the last refresh succeeded, and `IP CHANGED` means the address changed. `RATE LIMITED` delays manual refreshes until the limit expires. After an error, `STALE` marks the last successful result. If the current IPv4 address has changed, the interface shows which address the saved data belongs to. In the Reddit status field, `FLAGGED` reflects Net.Coffee's assessment.

## Releasing

Run `uv build --no-sources` to build the source archive and wheel locally. For a stable release, set `__version__` in `src/__init__.py` to a version greater than the latest published one and tag the commit as `vX.Y.Z`. The [package workflow](.github/workflows/package.yml) builds `iprate.tar.gz` once and checks installation from that archive on Linux (Python 3.8 and 3.13), Windows x86-64 (3.13), and macOS arm64 (3.13).

After the tag's workflow passes, download its `iprate-release` artifact. Check `iprate --ip` and the fullscreen interface in a real terminal on each target system. Attach the checked `iprate.tar.gz` to a draft GitHub Release for the tag. Publish it as the latest stable release so the installation and upgrade URL points to the new archive.
