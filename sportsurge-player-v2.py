#!/usr/bin/env python3
"""
Combined script: finds stream URLs from a Sportsurge watch page and plays the selected stream
using the command line media player mpv.

It leverages:
- sportsurge_links.SportsurgeScraper to fetch embed URLs and parse server entries.
- logic from enhanced_embed.py to locate a player and launch it with the appropriate referrer flag.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Optional

import requests

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.rule import Rule
from rich import box
from rich.live import Live
from rich.spinner import Spinner
from rich.columns import Columns
from rich.padding import Padding

from sportsurge_links import SportsurgeScraper, ServerEntry

console = Console()

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------

BANNER = """\
 ╔═══════════════════════════════════════╗
 ║  ⚽  S P O R T S U R G E  ·  P L A Y  ║
 ╚═══════════════════════════════════════╝"""

def print_banner() -> None:
    console.print(f"\n[bold cyan]{BANNER}[/bold cyan]\n")

# ---------------------------------------------------------------------------
# Styled status helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    console.print(f"[bold blue]ℹ[/bold blue]  {msg}")

def ok(msg: str) -> None:
    console.print(f"[bold green]✔[/bold green]  {msg}")

def warn(msg: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow]  {msg}")

def err(msg: str) -> None:
    console.print(f"[bold red]✖[/bold red]  {msg}", file=sys.stderr)

def die(msg: str, code: int = 1) -> None:
    err(msg)
    sys.exit(code)

# ---------------------------------------------------------------------------
# Player handling
# ---------------------------------------------------------------------------

DEFAULT_PLAYER = "mpv"
REF_FLAG_MP    = "--referrer"
REF_FLAG_OTHER = "--http-referrer"

def which(cmd: str) -> bool:
    return any(Path(p).joinpath(cmd).is_file() for p in os.getenv("PATH", "").split(os.pathsep))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HOSTS = [
    "pl.kamfir4.space",
    "grok.hereisman.net",
    "pl.kamfir3.space",
    "grok3.hereisman.net",
]
PATTERNS = [
    "playlist/%s/usicard5/caxi",
    "playlist/%s/youbest7/caxi",
]

def fetch_text(url: str, referrer: str) -> Optional[str]:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Referer": referrer},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        err(f"Request failed for {url}: {e}")
        return None

def head_success(url: str, referrer: str) -> bool:
    try:
        resp = requests.head(
            url,
            headers={"User-Agent": USER_AGENT, "Referer": referrer},
            timeout=3,
            allow_redirects=True,
        )
        return str(resp.status_code).startswith("2")
    except Exception:
        return False

def resolve_hls(embed_url: str) -> str:
    stream_id = embed_url.rstrip("/").split("/")[-1]

    with console.status("[cyan]Fetching embed page…[/cyan]", spinner="dots"):
        embed_page = fetch_text(embed_url, embed_url)
    if not embed_page:
        raise RuntimeError(f"Failed to fetch embed page {embed_url}")

    load_match = re.search(r"https://[^'\"\s]+load-playlist", embed_page)
    if not load_match:
        raise RuntimeError(f"No load-playlist URL found for {embed_url}")
    load_url = load_match.group(0)

    with console.status("[cyan]Retrieving master playlist…[/cyan]", spinner="dots"):
        master = fetch_text(load_url, embed_url) or ""

    # Strategy 1: direct .space HLS URL
    direct_match = re.search(r"https://[^'\"]+\.space/[^'\"]+", master)
    if direct_match:
        candidate = direct_match.group(0)
        if head_success(candidate, embed_url):
            return candidate
        candidate_m3u8 = candidate if candidate.endswith(".m3u8") else candidate + ".m3u8"
        if head_success(candidate_m3u8, embed_url):
            return candidate_m3u8

    # Strategy 2: known host/pattern combos
    with console.status("[cyan]Probing known CDN endpoints…[/cyan]", spinner="dots"):
        for host in HOSTS:
            for pat in PATTERNS:
                candidate = f"https://{host}/{pat.replace('%s', stream_id)}"
                if head_success(candidate, embed_url):
                    return candidate
                candidate_m3u8 = candidate if candidate.endswith(".m3u8") else candidate + ".m3u8"
                if head_success(candidate_m3u8, embed_url):
                    return candidate_m3u8

    # Strategy 3: after #EXT-X-STREAM-INF
    lines = master.splitlines()
    for i, line in enumerate(lines):
        if "#EXT-X-STREAM-INF" in line and i + 1 < len(lines):
            return lines[i + 1].strip()

    raise RuntimeError(f"Could not determine HLS URL for {embed_url}")

def launch_player(player: str, ref_flag: str, referrer: str, stream: str) -> None:
    cmd = [player, f"{ref_flag}={referrer}", stream]
    console.print(Rule("[bold green]Launching player[/bold green]"))
    console.print(
        Panel(
            f"[bold]{player}[/bold]\n"
            f"[dim]{stream}[/dim]",
            title="[green]▶  Now Playing[/green]",
            border_style="green",
            padding=(0, 1),
        )
    )
    try:
        subprocess.run(cmd, check=True)
        ok("Playback finished.")
    except subprocess.CalledProcessError as e:
        err(f"Player exited with code {e.returncode}")

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def print_menu(entries: List[ServerEntry]) -> None:
    table = Table(
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold magenta",
        padding=(0, 1),
        title="[bold]Available Streams[/bold]",
        title_style="bold cyan",
    )
    table.add_column("#",       style="bold white",  justify="right",  no_wrap=True)
    table.add_column("Label",   style="bold yellow",                   no_wrap=True)
    table.add_column("Default", justify="center",    no_wrap=True)
    table.add_column("URL",     style="dim cyan",                      no_wrap=False)

    for idx, e in enumerate(entries, 1):
        default_mark = "[bold green]✔[/bold green]" if e.is_default else ""
        table.add_row(str(idx), e.label, default_mark, e.url)

    console.print(table)

def select_entry(entries: List[ServerEntry]) -> ServerEntry:
    if not entries:
        die("No streams found.")
    if len(entries) == 1:
        info(f"Single stream available: [bold yellow]{entries[0].label}[/bold yellow]")
        return entries[0]

    print_menu(entries)

    default_entry = next((e for e in entries if e.is_default), entries[0])

    while True:
        choice = Prompt.ask(
            f"\n[bold cyan]Select stream[/bold cyan] [dim](1–{len(entries)}, or Enter for default)[/dim]",
            default="",
            show_default=False,
            console=console,
        )
        if not choice:
            ok(f"Using default: [bold yellow]{default_entry.label}[/bold yellow]")
            return default_entry
        try:
            idx = int(choice)
            if 1 <= idx <= len(entries):
                ok(f"Selected: [bold yellow]{entries[idx - 1].label}[/bold yellow]")
                return entries[idx - 1]
            warn(f"Enter a number between 1 and {len(entries)}.")
        except ValueError:
            warn("Invalid input — please enter a number.")

# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Find and play a Sportsurge stream.")
    parser.add_argument("watch_url", nargs="?", help="Full Sportsurge /watch/ URL")
    args = parser.parse_args()

    print_banner()

    scraper = SportsurgeScraper(verbose=False)
    watch_url = args.watch_url
    if not watch_url:
        from sportsurge_links import select_event_interactively
        watch_url = select_event_interactively(scraper)

    info(f"Watch URL: [dim]{watch_url}[/dim]")

    with console.status("[cyan]Fetching stream list…[/cyan]", spinner="dots"):
        try:
            entries = scraper.get_embed_urls(watch_url)
        except Exception as e:
            die(f"Failed to retrieve streams: {e}")

    ok(f"Found [bold]{len(entries)}[/bold] stream(s).")
    console.print()

    selected = select_entry(entries)
    console.print()

    # Resolve HLS
    info("Resolving HLS stream URL…")
    try:
        stream_url = resolve_hls(selected.url)
    except Exception as e:
        die(f"Failed to resolve HLS URL: {e}")

    ok(f"Stream resolved: [dim]{stream_url}[/dim]")
    console.print()

    # Determine player
    player = os.getenv("PLAYER", DEFAULT_PLAYER)
    if not which(player):
        die(f"Player '{player}' not found in PATH.")
    ref_flag = REF_FLAG_MP if player == "mpv" else REF_FLAG_OTHER

    launch_player(player, ref_flag, selected.url, stream_url)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        sys.exit(0)
