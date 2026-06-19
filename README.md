# Sportsurge Stream Embed Scraper (`sportsurge-ws-scraper`)

A resilient, multi-format command-line tool and Python library designed to scrape stream server embed URLs from [Sportsurge](https://sportsurge.ws). It supports direct URL extraction, rotates User-Agents, employs exponential backoff, and features an interactive terminal selector to choose sporting events directly from the Sportsurge homepage.

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
   - [Terminal Formatting / ANSI Colors](#terminal-formatting--ansi-colors)
10. [License](#license)

---

## Key Features

- **Interactive Event Selector**: Run the script without arguments to automatically pull the homepage and select active/upcoming live sports.
- **Direct Link Retrieval**: Provide a specific `/watch/` URL to immediately get its stream server embed URLs.
- **Multiple Output Formats**: Supports clean, human-readable colorized ANSI tables, structured JSON payload, or pipe-friendly CSV.
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
Fetching homepage https://sportsurge.ws/ for active events...

Available Sporting Events:
  [1] Mexico vs South Korea (FIFA World Cup) - LIVE
  [2] Athletics vs Los Angeles Angels (MLB) - 23 minutes from now
  [3] Kansas City Royals vs St. Louis Cardinals (MLB) - LIVE
  [4] Indiana Fever vs Atlanta Dream (WNBA) - LIVE

Select an event (1-4) or press Enter to exit: 1
Selected: Mexico vs South Korea

| Server  | Stream URL                                       | Default |
|---------|--------------------------------------------------|---------|
| Server1 | https://gooz.aapmains.net/new-stream-embed/52203 | ✅      |
| Server2 | https://gooz.aapmains.net/new-stream-embed/52204 |         |
| Server3 | https://gooz.aapmains.net/new-stream-embed/52205 |         |
```

*Note: The interactive prompt and debug notices are output to `sys.stderr`, preserving clean standard output for filters like `grep` or `jq`.*

---

### Direct URL Extraction

If you already have a Sportsurge `/watch/` URL, supply it directly:

```bash
python3 sportsurge_links.py https://sportsurge.ws/watch/world-championship-gr-b/qatar-canada/363496200
```

---

### Output Formats

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
    "url": "https://gooz.aapmains.net/new-stream-embed/52203",
    "default": true
  },
  {
    "label": "Server2",
    "stream_id": "52204",
    "url": "https://gooz.aapmains.net/new-stream-embed/52204",
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
Server1,52203,https://gooz.aapmains.net/new-stream-embed/52203,True
Server2,52204,https://gooz.aapmains.net/new-stream-embed/52204,False
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
watch_url = "https://sportsurge.ws/watch/world-championship-gr-b/qatar-canada/363496200"
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
2. **Interactive Event Parser**: Matches links (`/watch/`) on the homepage. It identifies the teams/players, the league or sporting category, and the status ("LIVE" or timed duration) by inspecting element attributes and textual classes.
3. **Embed Stream Disovery**: Extracts the active stream source URL by trying a sequence of fallback iframe/JS regex patterns:
   - `src="..."` attributes on `<iframe>`
   - `data-src="..."` lazy attributes
   - JS definitions (`embedUrl = '...'`)
   - Object configurations (`src: '...embed...'`)
4. **Base Stripping**: The scraper strips the active stream ID from the source URL to determine the base domain (e.g., `https://gooz.aapmains.net/new-stream-embed/`).
5. **Server Extraction**: Locates all stream button elements matching `onclick="window.changeStream(<id>)"` to map other stream options.
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
* **Solution**: Sportsurge may have changed their layout or anti-bot mechanisms. Enable verbose output (`-v`) to check the exact URL and body size received by the script.

### Terminal Formatting / ANSI Colors
* **Problem**: Table rows contain messy escape characters like `\033[36m`.
* **Solution**: Ensure your shell supports ANSI colors. If piping to files, colors are automatically stripped by `sys.stdout.isatty()`.

---

## License

This project is licensed under the MIT License. See the repository LICENSE file for details.
