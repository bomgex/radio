"""Loading and saving the station list (stations.json)."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIONS_FILE = ROOT / "stations.json"


@dataclass
class Station:
    name: str
    url: str
    genre: str = ""


def load_stations(path: Path = STATIONS_FILE) -> list[Station]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return [Station(**item) for item in data]


def save_stations(stations: list[Station], path: Path = STATIONS_FILE) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in stations], f, ensure_ascii=False, indent=2)
