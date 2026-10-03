"""Station search via the public radio-browser.info API (stdlib only)."""
from __future__ import annotations

import json
import random
import socket
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .stations import Station

USER_AGENT = "py-internet-radio/1.0"
FALLBACK_HOSTS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info",
                  "fi1.api.radio-browser.info"]
TIMEOUT = 15


@dataclass
class SearchResult:
    name: str
    url: str
    country: str
    codec: str
    bitrate: int
    tags: str
    votes: int

    @property
    def quality(self) -> str:
        return f"{self.codec} {self.bitrate}k" if self.bitrate else self.codec

    @property
    def genre(self) -> str:
        """First couple of tags, capitalised, for the local station list."""
        return ", ".join(t.strip().title() for t in self.tags.split(",")[:2] if t.strip())

    def to_station(self) -> Station:
        return Station(self.name, self.url, self.genre)


def _api_hosts() -> list[str]:
    """Resolve the current API mirrors (the project asks clients to pick randomly)."""
    try:
        ips = {a[4][0] for a in socket.getaddrinfo("all.api.radio-browser.info", 443)}
        hosts = []
        for ip in ips:
            try:
                hosts.append(socket.gethostbyaddr(ip)[0])
            except OSError:
                pass
        if hosts:
            random.shuffle(hosts)
            return hosts
    except OSError:
        pass
    return list(FALLBACK_HOSTS)


def search_stations(query: str, limit: int = 50) -> list[SearchResult]:
    """Search stations by name, most-voted first.  Raises OSError on network failure."""
    params = urllib.parse.urlencode({
        "name": query.strip(),
        "limit": limit,
        "hidebroken": "true",
        "order": "votes",
        "reverse": "true",
    })
    last_error: Exception | None = None
    for host in _api_hosts():
        url = f"https://{host}/json/stations/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.load(resp)
            break
        except OSError as exc:  # includes URLError / HTTPError / timeouts
            last_error = exc
    else:
        raise OSError(f"radio-browser.info недоступен: {last_error}")

    results = []
    for item in data:
        url = item.get("url_resolved") or item.get("url") or ""
        if not url:
            continue
        results.append(SearchResult(
            name=item.get("name", "").strip() or url,
            url=url,
            country=item.get("country", ""),
            codec=item.get("codec", ""),
            bitrate=int(item.get("bitrate") or 0),
            tags=item.get("tags", ""),
            votes=int(item.get("votes") or 0),
        ))
    return results
