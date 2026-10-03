"""Console mode: python main.py --cli"""
from __future__ import annotations

import time

from .browser import search_stations
from .player import RadioPlayer
from .stations import load_stations, save_stations


def main() -> None:
    stations = load_stations()
    if not stations:
        print("The station list is empty (stations.json).")
        return

    player = RadioPlayer()
    player.volume = 70
    current = None
    last_track = ""

    def show_list() -> None:
        for i, st in enumerate(stations, 1):
            mark = ">" if st is current else " "
            print(f"{mark} {i:2d}. {st.name:<28} {st.genre}")

    found = []
    print("Commands: number - play, l - list, s - stop, v <0-100> - volume, q - quit")
    print("Search:   f <name> - search, p <n> - play result, a <n> - add result to the list")
    show_list()
    try:
        while True:
            track = player.now_playing()
            if track and track != last_track:
                last_track = track
                print(f"   Now playing: {track}")

            cmd = input("> ").strip().lower()
            if not cmd:
                continue
            if cmd == "q":
                break
            elif cmd == "l":
                show_list()
            elif cmd == "s":
                player.stop()
                current = None
                print("Stopped")
            elif cmd.startswith("f "):
                try:
                    found = search_stations(cmd[2:])
                except OSError as exc:
                    print(f"Search error: {exc}")
                    continue
                if not found:
                    print("Nothing found")
                for i, r in enumerate(found, 1):
                    print(f"  {i:2d}. {r.name[:34]:<34} {r.country[:18]:<18} {r.quality}")
            elif cmd.startswith(("p ", "a ")) and cmd[2:].strip().isdigit():
                n = int(cmd[2:])
                if not 1 <= n <= len(found):
                    print("No such number in the search results")
                    continue
                st = found[n - 1].to_station()
                if cmd[0] == "p":
                    current = st
                    last_track = ""
                    player.play(st.url)
                    print(f"Playing: {st.name}")
                    time.sleep(1.5)
                elif any(s.url == st.url for s in stations):
                    print("Already in the list")
                else:
                    stations.append(st)
                    save_stations(stations)
                    print(f"Added: {st.name}")
            elif cmd.startswith("v"):
                try:
                    player.volume = int(cmd[1:].strip())
                    print(f"Volume: {player.volume}")
                except ValueError:
                    print("Example: v 50")
            elif cmd.isdigit() and 1 <= int(cmd) <= len(stations):
                current = stations[int(cmd) - 1]
                last_track = ""
                player.play(current.url)
                print(f"Playing: {current.name}")
                time.sleep(1.5)
            else:
                print("Unknown command")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        player.release()
