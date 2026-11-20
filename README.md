# iprate

`iprate` shows reputation, network, and geolocation details for your public IPv4 address in a Linux terminal. ipify provides the address, and Net.Coffee provides the ratings and history.

## Running from source

You need Python 3.8 or later with HTTPS support and access to trusted certificates. Fullscreen mode requires `curses` and a terminal with `TERM` set correctly. Run these commands from the repository root.

```bash
python3 main.py
python3 main.py --ip
python3 main.py --help
```

`--ip` writes a single IPv4 address to standard output. On error, it writes a message to standard error and returns a nonzero exit status. `--help` and `--version` work offline.

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

## Installation

Build an executable archive with the standard library's `zipapp` module. The temporary build directory contains the entry point and the application modules.

```bash
(
    set -e
    build_dir=$(mktemp -d)
    trap 'rm -rf -- "$build_dir"' EXIT
    mkdir -p "$build_dir/src/tui" "$HOME/.local/bin"
    cp main.py "$build_dir/__main__.py"
    cp src/*.py "$build_dir/src/"
    cp src/tui/*.py "$build_dir/src/tui/"
    python3 -m zipapp "$build_dir" -p '/usr/bin/env python3' -o "$HOME/.local/bin/iprate"
)
"$HOME/.local/bin/iprate" --version
```

If `~/.local/bin` is on your `PATH`, use `iprate --ip` to get your address. The archive uses `python3` from `PATH`. To use a different interpreter, pass the archive path to it.
