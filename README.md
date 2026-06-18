# sportsurge-ws-links

Scrape all stream server embed URLs from a [Sportsurge](https://sportsurge.ws) watch page and print them as a table, JSON, or CSV.

## Requirements

Python 3.10+ and one third-party package:

```
pip install requests
```

## Usage

```
python sportsurge_links.py <watch_url> [--format {table,json,csv}] [--verbose]
```

### Arguments

| Argument | Short | Default | Description |
|---|---|---|---|
| `watch_url` | — | required | Full Sportsurge `/watch/` URL |
| `--format` | `-f` | `table` | Output format: `table`, `json`, or `csv` |
| `--verbose` | `-v` | off | Print debug info to stderr (redirects, byte count, parsed IDs) |

## Examples

**Default table output**
```
python sportsurge_links.py https://sportsurge.ws/watch/world-championship-gr-b/qatar-canada/363496200
```
```
| Server  | Stream URL                                       | Default |
|---------|--------------------------------------------------|---------|
| Server1 | https://gooz.aapmains.net/new-stream-embed/52203 | ✅       |
| Server2 | https://gooz.aapmains.net/new-stream-embed/52204 |         |
| Server3 | https://gooz.aapmains.net/new-stream-embed/52205 |         |
```

The default server (the one pre-loaded in the iframe) is highlighted in colour when the terminal supports ANSI codes.

**JSON output**
```
python sportsurge_links.py <url> --format json
```
```json
[
  {
    "label": "Server1",
    "stream_id": "52203",
    "url": "https://gooz.aapmains.net/new-stream-embed/52203",
    "default": true
  },
  ...
]
```

**CSV output (pipe-friendly)**
```
python sportsurge_links.py <url> --format csv > streams.csv
```
```
label,stream_id,url,default
Server1,52203,https://gooz.aapmains.net/new-stream-embed/52203,True
Server2,52204,https://gooz.aapmains.net/new-stream-embed/52204,False
```

**Verbose / debug mode**
```
python sportsurge_links.py <url> -v
```
Debug lines go to **stderr** so they never pollute piped output.

## Library usage

`SportsurgeScraper` can be imported directly instead of called from the CLI:

```python
from sportsurge_links import SportsurgeScraper

scraper = SportsurgeScraper(verbose=True)
entries = scraper.get_embed_urls("https://sportsurge.ws/watch/.../363496200")

for e in entries:
    print(e.label, e.url, "← default" if e.is_default else "")
```

`get_embed_urls` returns a list of `ServerEntry` dataclass instances:

```python
@dataclass
class ServerEntry:
    label: str       # e.g. "Server1", "HD1", "Backup"
    stream_id: str   # numeric ID used in the embed URL
    url: str         # full embed URL
    is_default: bool # True if this server is pre-loaded on the page
```

## How it works

1. Fetches the watch page with a randomised `User-Agent` and a `Referer` header, following any redirects.
2. Parses `onclick="window.changeStream(<id>)"` buttons to discover all available servers and their labels.
3. Locates the active embed URL via a priority-ordered list of patterns (`src=`, `data-src=`, JS `embedUrl`, JS `src:` object key) and strips the trailing stream ID to derive a reusable base URL.
4. Reconstructs each server's full embed URL as `<base><stream_id>`.

## Resilience features

- **Retry with backoff** — 3 automatic retries on 429 / 5xx responses (0.5 s, 1 s, 2 s).
- **Randomised User-Agent** — rotates across four realistic Chrome/Firefox/Safari strings.
- **Redirect tracking** — final URL is logged in verbose mode, making domain hops visible.
- **Multiple embed patterns** — falls back through four different HTML/JS patterns before giving up.
- **Descriptive errors** — HTTP errors, connection failures, timeouts, and parse failures each produce a distinct message with a non-zero exit code.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | HTTP error, connection error, timeout, or parse failure |
