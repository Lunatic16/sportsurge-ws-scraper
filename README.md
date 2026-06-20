<p align="center">
  <img src="sportsurge.png" alt="Project Screenshot" width="350">
</p>

# Sportsurge Stream Embed Scraper

A resilient, multi-format command-line tool and Python library designed to scrape stream server embed URLs from Sportsurge. It supports direct URL extraction, rotates User-Agents, employs exponential backoff, and features an interactive terminal selector to choose sporting events directly from the Sportsurge homepage.

## Table of Contents
1. [Key Features](#key-features)
2. [Tech Stack](#tech-stack)
3. [Prerequisites](#prerequisites)
4. [Getting Started](#getting-started)
   - [1. Clone the Repository](#1-clone-the-repository)
   - [2. Create a Virtual Environment](#2-create-a-virtual-environment)
   - [3. Install Dependencies](#3-install-dependencies)
   - [4. Verify Installation](#4-verify-installation)
5. [Usage Guide](#usage-guide)
   - [CLI Arguments](#cli-arguments)
   - [Interactive Homepage Selection](#interactive-homepage-selection)
   - [Direct URL Extraction](#direct-url-extraction)
   - [Output Formats](#output-formats)
6. [Library Usage](#library-usage)
   - [Integration Example](#integration-example)
   - [Data Models](#data-models)
7. [Architecture Overview](#architecture-overview)
   - [Directory Structure](#directory-structure)
   - [Application Lifecycle & Data Flow](#application-lifecycle--data-flow)
   - [Scraping and Parsing Logic](#scraping-and-parsing-logic)
   - [Resilience Features](#resilience-features)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)
   - [HTTP Errors (429/503)](#http-errors-429503)
   - [Missing Server Entries / Suspiciously Small Pages](#missing-server-entries--suspiciously-small-pages)
   - [Only One Server Shows Up](#only-one-server-shows-up)
   - [Terminal Formatting / ANSI Colors](#terminal-formatting--ansi-colors)
10. [License](#license)

---

## Key Features

- **Interactive Event Selector**: Run the script without arguments to automatically pull the homepage and select active/upcoming live sports, grouped by category with color-coded `● LIVE` / `⏱ scheduled` badges. Covers both team-sport matches (`/watch/` URLs — MLB, NBA, NHL, FIFA World Cup, WNBA, NCAA, etc.) and single-card fight sports (`/event/` URLs — UFC, Boxing, MMA, WWE).
- **Direct Link Retrieval**: Provide a specific Sportsurge `/watch/` or `/event/` URL to immediately get its stream server embed URL(s).
- **Multiple Output Formats**: Supports a clean, box-drawn, colorized ANSI table (with the default server highlighted), structured JSON payload, or pipe-friendly CSV.
- **Single & Multi-Server Pages**: Most `/watch/` pages expose several alternate servers via stream-switch buttons; many `/event/` fight-card pages only embed a single iframe. The scraper handles both — synthesizing a lone `Server1` entry when no alternate-server buttons exist.
- **Status Messaging**: Fetch progress, success summaries, and errors are printed to `stderr` with consistent `➤` / `✓` / `✗` markers so they're easy to scan and never pollute piped `stdout`.
- **Resilience Engine**: Rotates through four realistic User-Agents, automatically retries on rates and transient server errors, and falls back to regex-based HTML parsers if BeautifulSoup is unavailable.
- **Library Integration**: Designed as a modular Python class (`SportsurgeScraper`) that can be imported directly into other scripts.

---

## Tech Stack

- **Language**: Python 3.10+
- **Core Library**: `requests` (for robust HTTP operations)
- **HTML Parsing**: `beautifulsoup4` (used for parsing structured homepage and stream frames; falls back gracefully to standard `re` library)
- **Standard Libraries**: `argparse`, `re`, `json`, `csv`, `io`, `urllib`, `logging`

---

## Prerequisites

- **Python 3.10** or higher.
- A terminal environment (supporting ANSI color codes for optimal table display).
- An internet connection.

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Lunatic16/sportsurge-ws-scraper.git
cd sportsurge-ws-scraper
```

### 2. Create a Virtual Environment

It is highly recommended to use a virtual environment to manage dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install the required packages. While `beautifulsoup4` is optional (due to built-in regex fallbacks), it is strongly recommended for parsing accuracy:

```bash
pip install requests beautifulsoup4
```

### 4. Verify Installation

Run the help command to check if all arguments are correctly recognized:

```bash
python3 sportsurge_links.py --help
```

---

## Usage Guide

### CLI Arguments

```
usage: sportsurge_links.py [-h] [--format {table,json,csv}] [--verbose] [watch_url]
```

| Argument / Option | Short Flag | Default | Description |
|---|---|---|---|
| `watch_url` | — | `None` | *Optional*. Full Sportsurge watch page URL. Launches interactive menu if omitted. |
| `--format` | `-f` | `table` | Output format. Options: `table`, `json`, `csv`. |
| `--verbose` | `-v` | off | Prints verbose debugging info (redirects, parsed IDs, request byte count) to `stderr`. |

---

### Interactive Homepage Selection

Launch the script without arguments to search the homepage for live sporting events:

```bash
python3 sportsurge_links.py
```

**Interactive CLI Example:**
```
➤ Fetching https://sportsurge.ws/ for active events…

── Available Sporting Events (5) ──

  UFC
    [ 1] UFC Fight Night: Kape vs. Horiguchi          ⏱ 31 minutes from now

  FIFA World Cup
    [ 2] Mexico vs South Korea                        ● LIVE

  MLB
    [ 3] Athletics vs Los Angeles Angels               ⏱ 23 minutes from now
    [ 4] Kansas City Royals vs St. Louis Cardinals     ● LIVE

  WNBA
    [ 5] Indiana Fever vs Atlanta Dream                ● LIVE

Select an event (1-5) or press Enter to exit: 2
✓ Selected: Mexico vs South Korea

➤ Fetching https://sportsurge.../watch/mexico-vs-south-korea/.../52203
✓ Found 3 servers — default: Server1

╭───────────────────────────────────────────────────────────────╮
│                  Sportsurge Stream Servers                    │
╰───────────────────────────────────────────────────────────────╯
┌─────────┬───────────────────────────────────────────┬─────────┐
│ Server  │ Stream URL                                 │ Default │
├─────────┼───────────────────────────────────────────┼─────────┤
│ Server1 │ https://gooz.aapmains.../.../52203         │    ✓    │
│ Server2 │ https://gooz.aapmains.../.../52204         │         │
│ Server3 │ https://gooz.aapmains.../.../52205         │         │
└─────────┴───────────────────────────────────────────┴─────────┘
```

*Events are grouped by category (league/competition) in the order they're first encountered — including single-card fight sports like UFC and Boxing, which Sportsurge links via `/event/` URLs rather than `/watch/`. `● LIVE` badges render in red and `⏱` time badges in yellow when your terminal supports ANSI colors; the table's default-server row is highlighted in cyan/green.*

*Note: many `/event/` fight-card pages (e.g. a single UFC bout) only embed one iframe and have no alternate-server buttons. In that case the table will simply show a single `Server1` row marked as default — that's expected, not an error.*

*Note: The interactive prompt and debug notices are output to `sys.stderr`, preserving clean standard output for filters like `grep` or `jq`.*

---

### Direct URL Extraction

If you already have a Sportsurge `/watch/` or `/event/` URL, supply it directly:

```bash
python3 sportsurge_links.py https://sportsurge.../watch/world-championship-gr-b/.../363496200

# Single-card fight pages (UFC, Boxing, MMA, WWE) work too:
python3 sportsurge_links.py https://sportsurge.../event/boxing/ryan-garner-vs-michael-magnesi-live-streaming-links
```

---

### Output Formats

#### Table Output (default)
The default, human-friendly format — a box-drawn, colorized table with a title banner. The row matching the page's default-loaded stream is highlighted (cyan label, yellow URL, green ✓).

```bash
python3 sportsurge_links.py <url>
# or explicitly
python3 sportsurge_links.py <url> --format table
```
```
╭───────────────────────────────────────────────────────────────╮
│                  Sportsurge Stream Servers                    │
╰───────────────────────────────────────────────────────────────╯
┌─────────┬───────────────────────────────────────────┬─────────┐
│ Server  │ Stream URL                                 │ Default │
├─────────┼───────────────────────────────────────────┼─────────┤
│ Server1 │ https://gooz.aapmains.../.../52203         │    ✓    │
│ Server2 │ https://gooz.aapmains.../.../52204         │         │
└─────────┴───────────────────────────────────────────┴─────────┘
```

Colors are auto-disabled when output isn't a terminal (e.g. piped or redirected), so the box-drawing characters still render cleanly in files or pagers.

#### JSON Output
Perfect for automated pipelines and custom scripting.

```bash
python3 sportsurge_links.py <url> --format json
```
```json
[
  {
    "label": "Server1",
    "stream_id": "52203",
    "url": "https://gooz.aapmains.../.../52203",
    "default": true
  },
  {
    "label": "Server2",
    "stream_id": "52204",
    "url": "https://gooz.aapmains.../.../52204",
    "default": false
  }
]
```

#### CSV Output
Piped CSV output for spreadsheet integration or script inputs.

```bash
python3 sportsurge_links.py <url> --format csv > streams.csv
```
```
label,stream_id,url,default
Server1,52203,https://gooz.aapmains.../.../52203,True
Server2,52204,https://gooz.aapmains.../.../52204,False
```

---

## Library Usage

### Integration Example

You can import `SportsurgeScraper` directly into your own scripts or automation backends.

```python
from sportsurge_links import SportsurgeScraper

# Initialize scraper with verbose debug printing enabled
scraper = SportsurgeScraper(verbose=True)

# Fetch watch page directly and get all stream server entries
watch_url = "https://sportsurge.../watch/world-championship-gr-b/.../363496200"
entries = scraper.get_embed_urls(watch_url)

for entry in entries:
    print(f"Server Name: {entry.label}")
    print(f"Embed URL: {entry.url}")
    print(f"Is Default Player Embed?: {entry.is_default}")
    print("-" * 30)
```

### Data Models

`get_embed_urls` returns a list of `ServerEntry` objects:

```python
@dataclass
class ServerEntry:
    label: str       # Name of the stream supplier (e.g. "Server1", "HD1", "Backup")
    stream_id: str   # The unique server stream stream_id
    url: str         # The full browser-loadable stream iframe URL
    is_default: bool # True if this server is selected by default on load
```

---

## Architecture Overview

### Directory Structure

```
sportsurge-ws-scraper/
├── README.md               # Absurdly thorough documentation
└── sportsurge_links.py     # Main executable, library API, and console tool
```

### Application Lifecycle & Data Flow

```
User CLI Invocation
       │
       ▼
[ Has watch_url? ] ───(Yes)───► [ Fetch Watch Page URL ]
       │                                │
      (No)                              │
       │                                │
       ▼                                │
[ Fetch Homepage ]                      │
       │                                │
       ▼                                │
[ Parse Sporting Events ]               │
       │                                │
       ▼                                │
[ Render Interactive Menu ]             │
       │                                │
       ▼                                │
[ Select Event / Get URL ] ─────────────┘
       │
       ▼
[ Parse Stream Embed URL ]
       │
       ▼
[ Parse Stream Buttons & IDs ]
       │
       ▼
[ Reconstruct ServerEntry Objects ]
       │
       ▼
[ Format & Output (Table/JSON/CSV) ]
```

### Scraping and Parsing Logic

1. **Watch Page Fetching**: Fetches the page using randomized Headers (`User-Agent`) and tracks any HTTP redirects to support domain mirrors.
2. **Interactive Event Parser**: Matches links on the homepage against two URL patterns — `/watch/<competition>/<teams>/<id>` for team-sport matches, and `/event/<sport>/<slug>` for single-card fight sports (UFC, Boxing, MMA, WWE). It identifies the teams/players, the league or sporting category, and the status ("LIVE" or timed duration) by inspecting element attributes and textual classes, with a keyword-matching fallback (and a boilerplate-stripped URL-slug fallback) if those attributes are missing or laid out differently.
3. **Embed Stream Disovery**: Extracts the active stream source URL by trying a sequence of fallback iframe/JS regex patterns:
   - `src="..."` attributes on `<iframe>`
   - `data-src="..."` lazy attributes
   - JS definitions (`embedUrl = '...'`)
   - Object configurations (`src: '...embed...'`)
4. **Base Stripping**: The scraper strips the active stream ID from the source URL to determine the base domain (e.g., `https://gooz.aapmains.net/new-stream-embed/`).
5. **Server Extraction**: Locates all stream button elements matching `onclick="window.changeStream(<id>)"` to map other stream options. Some pages (notably single-fight `/event/` cards) have no such buttons — just one embedded iframe — in which case that iframe is treated as a lone `Server1` entry instead of triggering a parse error.
6. **Reconstruction**: Re-joins the stream base URL with each identified stream ID to generate the full player link for every host.

---

## Resilience Features

- **Backoff Retries**: Employs an HTTPAdapter with a 3-retry limit on server statuses `429` (Too Many Requests) and `5xx` (Server Error), scaling delay times (0.5s, 1s, 2s).
- **User-Agent Rotation**: Rotates through verified user-agents mapping modern Chrome, Safari, and Firefox browser configurations.
- **Regex Parsing Fallback**: Includes a fallback parser for homepage event streams that doesn't depend on external library classes, preventing failure if `bs4` is missing.
- **Robust Exception Handling**: Differentiates between connection issues, HTTP failures, query timeouts, and parse failures, returning appropriate error outputs and clean exit codes.

---

## Testing

Verify that the CLI runs correctly and outputs structured layouts across all formats:

```bash
# Test Table Format output
python3 sportsurge_links.py -f table

# Test JSON Format output
python3 sportsurge_links.py -f json

# Test CSV Format output
python3 sportsurge_links.py -f csv
```

---

## Troubleshooting

### HTTP Errors (429/503)
* **Problem**: The request is throttled or blocked by Cloudflare or anti-bot protections.
* **Solution**: Ensure you are running the scraper with a stable IP, or inspect redirects using verbose mode (`-v`). Wait a few moments for the backoff retry adapter to trigger.

### Missing Server Entries / Suspiciously Small Pages
* **Problem**: The output warns of parsing failures or lists `Page response is suspiciously small`.
* **Solution**: This only triggers when *neither* alternate-server buttons *nor* an embedded iframe can be found at all — Sportsurge may have changed their layout or anti-bot mechanisms. Enable verbose output (`-v`) to check the exact URL and body size received by the script.

### Only One Server Shows Up
* **Problem**: A page (often a single-card `/event/` fight page like UFC or Boxing) only returns one `Server1` row in the table, even though other pages show three or four.
* **Solution**: This is expected, not a bug — some pages embed a single iframe with no alternate-stream buttons at all, so there's nothing else to list.

### Terminal Formatting / ANSI Colors
* **Problem**: Table rows or status lines contain messy escape characters like `\033[36m`.
* **Solution**: Ensure your shell supports ANSI colors. Coloring is applied independently to `stdout` (the table) and `stderr` (status, errors, and the interactive menu), each checked via `isatty()` — so colors are automatically stripped on either stream when it isn't a real terminal, e.g. when piping the table to a file or redirecting `stderr` to a log.

---

## License

This project is licensed under the MIT License. See the repository LICENSE file for details.
