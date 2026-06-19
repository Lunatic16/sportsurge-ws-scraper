#!/usr/bin/env python3
"""
sportsurge_links.py
Retrieve all server embed URLs for a Sportsurge watch page.

Usage:
    python sportsurge_links.py <watch_url> [options]

Examples:
    python sportsurge_links.py https://sportsurge.ws/watch/.../363496200
    python sportsurge_links.py https://sportsurge.ws/watch/.../363496200 --format json
    python sportsurge_links.py https://sportsurge.ws/watch/.../363496200 --format csv -v
"""

import sys
import re
import json
import csv
import io
import random
import argparse
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENTS = [
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.3 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
]

TIMEOUT = 15  # seconds

# Embed URL patterns to try in order
IFRAME_PATTERNS = [
    re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE),  # src="..."
    re.compile(r'<iframe[^>]+data-src=["\']([^"\']+)["\']', re.IGNORECASE),  # data-src lazy
    re.compile(r'embedUrl\s*=\s*["\']([^"\']+)["\']'),  # JS var embedUrl = '...'
    re.compile(r'src:\s*["\']([^"\']+embed[^"\']+)["\']'),  # JS object src: '...embed...'
]

# Server button patterns – captures stream ID and full inner label text
SERVER_PATTERN = re.compile(
    r'onclick=["\']window\.changeStream\((\d+)\)["\'][^>]*>(.*?)<',
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ServerEntry:
    label: str
    stream_id: str
    url: str
    is_default: bool = field(default=False)

# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------

class SportsurgeScraper:
    """Fetch and parse a Sportsurge watch page for stream embed URLs."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._setup_logging()
        self.session = self._build_session()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _setup_logging(self) -> None:
        level = logging.DEBUG if self.verbose else logging.WARNING
        logging.basicConfig(
            format="[%(levelname)s] %(message)s",
            level=level,
            stream=sys.stderr,
        )
        self.log = logging.getLogger("sportsurge")

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _make_headers(self, referer: Optional[str] = None) -> dict:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    # ------------------------------------------------------------------
    # Core fetch
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> str:
        """Download the raw HTML of the watch page, following redirects."""
        self.log.debug("GET %s", url)
        resp = self.session.get(
            url,
            headers=self._make_headers(),
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        final_url = resp.url
        if final_url != url:
            self.log.debug("Redirected → %s", final_url)
        self.log.debug("Response: %d bytes, status %d", len(resp.content), resp.status_code)
        return resp.text, final_url

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_servers(self, html: str) -> list[tuple[str, str]]:
        """
        Return (label, stream_id) pairs in document order.
        Captures full inner label text (e.g. 'Server1', 'HD1', 'Backup').
        """
        matches = SERVER_PATTERN.findall(html)
        results = []
        for sid, raw_label in matches:
            label = re.sub(r'<[^>]+>', '', raw_label).strip()  # strip any nested tags
            if label:
                results.append((label, sid))
        self.log.debug("Found %d server buttons", len(results))
        return results

    def parse_base_url(self, html: str) -> Optional[str]:
        """
        Try multiple patterns to find the iframe/embed base URL.
        Returns the base (with trailing stream ID stripped) or None.
        """
        for pattern in IFRAME_PATTERNS:
            m = pattern.search(html)
            if m:
                src = m.group(1)
                self.log.debug("Embed URL found via pattern %r: %s", pattern.pattern[:40], src)
                # Strip trailing numeric segment to get reusable base
                base = re.sub(r'\d+$', '', src)
                return base
        self.log.debug("No embed URL found in HTML")
        return None

    def parse_default_id(self, html: str) -> Optional[str]:
        """Extract the stream ID currently loaded in the iframe src."""
        for pattern in IFRAME_PATTERNS:
            m = pattern.search(html)
            if m:
                src = m.group(1)
                dm = re.search(r'(\d+)$', src)
                return dm.group(1) if dm else None
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_embed_urls(self, watch_url: str) -> list[ServerEntry]:
        """
        Fetch the watch page and return a list of ServerEntry objects.
        Raises RuntimeError if the page cannot be parsed.
        """
        html, final_url = self.fetch(watch_url)

        servers = self.parse_servers(html)
        if not servers:
            # Check if it looks like we got a valid page at all
            if len(html) < 500:
                raise RuntimeError(
                    "Page response is suspiciously small — may be blocked or redirected to an error page."
                )
            raise RuntimeError(
                "No server entries found. The page may be JS-rendered (stream IDs injected "
                "after load) or the URL may be invalid."
            )

        base_url = self.parse_base_url(html)
        if not base_url:
            raise RuntimeError(
                "Could not locate an iframe/embed URL in the page source. "
                "The site may use JS-injected embeds not visible in raw HTML."
            )

        default_id = self.parse_default_id(html)
        self.log.debug("Default stream ID: %s", default_id)

        entries = []
        for label, sid in servers:
            url = f"{base_url}{sid}"
            entries.append(ServerEntry(
                label=label,
                stream_id=sid,
                url=url,
                is_default=(sid == default_id),
            ))

        return entries

    def get_homepage_events(self, html: str) -> list[dict]:
        """Parse available sporting events from the homepage HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            events = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/watch/" not in href:
                    continue

                full_url = urljoin("https://sportsurge.ws", href)

                # Extract teams
                team_rows = a.find_all(class_="team-name-event-row")
                teams = []
                for row in team_rows:
                    img = row.find("img", alt=True)
                    if img:
                        teams.append(img["alt"].strip())
                    else:
                        span = row.find("span")
                        if span:
                            teams.append(span.get_text().strip())
                        else:
                            teams.append(row.get_text().strip())

                # Extract category and status
                list_divs = a.find_all(class_="ListelemeDuzen")
                category = ""
                status = ""
                for div in list_divs:
                    text = div.get_text().strip()
                    if not text:
                        continue
                    if div.find("img"):
                        continue
                    if not category:
                        category = text
                    else:
                        status = text

                # Fallback/clean title
                event_title = " vs ".join(teams) if teams else ""
                chevron_img = a.find("img", alt=True)
                if chevron_img and chevron_img["alt"].startswith("Watch "):
                    alt_val = chevron_img["alt"]
                    if not category and ":" in alt_val:
                        category = alt_val.split(":", 1)[0].replace("Watch", "").strip()
                    if not event_title and ":" in alt_val:
                        event_title = alt_val.split(":", 1)[1].strip()

                if not event_title:
                    parts = href.split("/")
                    if len(parts) >= 3:
                        event_title = parts[-2].replace("-", " ").title()

                events.append({
                    "title": event_title,
                    "category": category or "Unknown Sport",
                    "status": status or "Scheduled",
                    "url": full_url
                })
            return events
        except Exception as e:
            self.log.debug("BeautifulSoup parsing failed or not available, falling back to regex: %s", e)
            return self._parse_homepage_events_regex(html)

    def _parse_homepage_events_regex(self, html: str) -> list[dict]:
        """Regex-based fallback parser for homepage events."""
        a_pattern = re.compile(
            r'<a[^>]+href=[\"\'](https://sportsurge\.ws/watch/[^\'\"]+)[\"\'][^>]*>(.*?)</a>',
            re.DOTALL
        )
        img_alt_pattern = re.compile(r'alt=[\"\']([^\"\']+)[\"\']')

        events = []
        for href, inner in a_pattern.findall(html):
            alts = img_alt_pattern.findall(inner)
            watch_alt = None
            for alt in alts:
                if alt.startswith("Watch "):
                    watch_alt = alt
                    break

            category = "Unknown Sport"
            title = ""
            if watch_alt:
                content = watch_alt[6:].strip()
                if ":" in content:
                    category, title = [part.strip() for part in content.split(":", 1)]
                else:
                    title = content

            if not title:
                teams = [alt for alt in alts if not alt.startswith("Watch") and "chevron" not in alt.lower()]
                if teams:
                    title = " vs ".join(teams)

            if not title:
                parts = href.split("/")
                if len(parts) >= 3:
                    title = parts[-2].replace("-", " ").title()

            text_content = re.sub(r"<[^>]+>", " ", inner)
            text_content = re.sub(r"\s+", " ", text_content).strip()

            status = "Scheduled"
            if "LIVE" in text_content:
                status = "LIVE"
            else:
                time_match = re.search(r"(\d+\s+(?:minute|hour|day)s?\s+from\s+now)", text_content, re.IGNORECASE)
                if time_match:
                    status = time_match.group(1)

            if category == "Unknown Sport":
                for sport in ["MLB", "WNBA", "NBA", "NFL", "NHL", "Boxing", "MMA", "FIFA World Cup", "UFC"]:
                    if sport in text_content:
                        category = sport
                        break

            events.append({
                "title": title,
                "category": category,
                "status": status,
                "url": href
            })
        return events


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _colorize(text: str, code: str) -> str:
    """Wrap text in an ANSI color code if stdout is a TTY."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

def fmt_table(entries: list[ServerEntry]) -> str:
    """Colorized table with columns sized to actual content."""
    COL_DEFAULT = "Default"
    DEFAULT_TICK = "✅"

    # Compute column widths from real data (no hardcoded padding)
    w_label = max(len("Server"), max(len(e.label) for e in entries))
    w_url   = max(len("Stream URL"), max(len(e.url) for e in entries))
    w_def   = max(len(COL_DEFAULT), len(DEFAULT_TICK))

    def cell(text: str, width: int) -> str:
        return f" {text:<{width}} "

    sep = f"|{'-' * (w_label + 2)}|{'-' * (w_url + 2)}|{'-' * (w_def + 2)}|"

    header = (
        _colorize(f"|{cell('Server', w_label)}", "1") +
        _colorize(f"|{cell('Stream URL', w_url)}", "1") +
        _colorize(f"|{cell(COL_DEFAULT, w_def)}|", "1")
    )

    rows = [header, sep]
    for e in entries:
        tick       = DEFAULT_TICK if e.is_default else ""
        label_text = cell(e.label, w_label)
        url_text   = cell(e.url,   w_url)
        def_text   = cell(tick,    w_def)

        if e.is_default:
            label_text = _colorize(label_text, "36")
            url_text   = _colorize(url_text,   "33")
            def_text   = _colorize(def_text,   "32")

        rows.append(f"|{label_text}|{url_text}|{def_text}|")

    return "\n".join(rows)

def fmt_json(entries: list[ServerEntry]) -> str:
    return json.dumps(
        [
            {
                "label": e.label,
                "stream_id": e.stream_id,
                "url": e.url,
                "default": e.is_default,
            }
            for e in entries
        ],
        indent=2,
    )

def fmt_csv(entries: list[ServerEntry]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["label", "stream_id", "url", "default"])
    writer.writeheader()
    for e in entries:
        writer.writerow({
            "label": e.label,
            "stream_id": e.stream_id,
            "url": e.url,
            "default": e.is_default,
        })
    return buf.getvalue().rstrip()

FORMATTERS = {
    "table": fmt_table,
    "json": fmt_json,
    "csv": fmt_csv,
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Retrieve all server embed URLs for a Sportsurge watch page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python sportsurge_links.py\n"
            "  python sportsurge_links.py https://sportsurge.ws/watch/.../363496200\n"
            "  python sportsurge_links.py <url> --format json\n"
            "  python sportsurge_links.py <url> --format csv -v\n"
        ),
    )
    p.add_argument(
        "watch_url",
        nargs="?",
        default=None,
        help="Full Sportsurge /watch/ URL (optional, starts interactive selection if omitted)"
    )
    p.add_argument(
        "--format", "-f",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print debug info (final URL, response size, parsed data) to stderr",
    )
    return p


def select_event_interactively(scraper: SportsurgeScraper) -> str:
    """Fetch homepage, display sporting events, and prompt user to choose one."""
    homepage_url = "https://sportsurge.ws/"
    print(f"Fetching homepage {homepage_url} for active events...", file=sys.stderr)
    try:
        html, _ = scraper.fetch(homepage_url)
    except Exception as e:
        print(f"Error fetching homepage: {e}", file=sys.stderr)
        sys.exit(1)

    events = scraper.get_homepage_events(html)
    if not events:
        print("No active sporting events found on the homepage.", file=sys.stderr)
        sys.exit(1)

    print("\nAvailable Sporting Events:", file=sys.stderr)
    for idx, ev in enumerate(events, 1):
        print(f"  [{idx}] {ev['title']} ({ev['category']}) - {ev['status']}", file=sys.stderr)

    while True:
        try:
            sys.stderr.write(f"\nSelect an event (1-{len(events)}) or press Enter to exit: ")
            sys.stderr.flush()
            choice = sys.stdin.readline().strip()
            if not choice:
                print("Exit.", file=sys.stderr)
                sys.exit(0)

            idx = int(choice)
            if 1 <= idx <= len(events):
                selected = events[idx - 1]
                print(f"Selected: {selected['title']}\n", file=sys.stderr)
                return selected["url"]
            else:
                print(f"Please enter a number between 1 and {len(events)}.", file=sys.stderr)
        except ValueError:
            print("Invalid input. Please enter a valid number.", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):
            print("\nExit.", file=sys.stderr)
            sys.exit(0)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    scraper = SportsurgeScraper(verbose=args.verbose)

    watch_url = args.watch_url
    if not watch_url:
        watch_url = select_event_interactively(scraper)

    try:
        entries = scraper.get_embed_urls(watch_url)
    except requests.HTTPError as e:
        print(f"HTTP error fetching page: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.ConnectionError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print(f"Request timed out after {TIMEOUT}s.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    formatter = FORMATTERS[args.format]
    print(formatter(entries))


if __name__ == "__main__":
    main()
