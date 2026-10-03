"""Tkinter GUI for the radio player."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .player import RadioPlayer
from .search_dialog import SearchDialog
from .stations import Station, load_stations, save_stations

POLL_MS = 1000


class RadioApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Internet Radio")
        self.geometry("560x420")
        self.minsize(460, 340)

        self.player = RadioPlayer()
        # VLC fires events from its own thread; hop back to the Tk thread.
        self.player.set_error_callback(lambda: self.after(0, self._on_stream_error))
        self.stations: list[Station] = load_stations()
        self.current: Station | None = None

        self._build_ui()
        self._refresh_list()
        self.after(POLL_MS, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- UI ---------------------------------------------------------------
    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        # Station list
        frame = ttk.Frame(self, padding=8)
        frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(frame, columns=("name", "genre"), show="headings",
                                 selectmode="browse")
        self.tree.heading("name", text="Station")
        self.tree.heading("genre", text="Genre")
        self.tree.column("name", width=320)
        self.tree.column("genre", width=120)
        self.tree.bind("<Double-1>", lambda _e: self._play_selected())
        self.tree.bind("<Return>", lambda _e: self._play_selected())

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Now playing
        info = ttk.Frame(self, padding=(8, 0, 8, 4))
        info.pack(fill="x")
        self.lbl_station = ttk.Label(info, text="Nothing playing",
                                     font=("Segoe UI", 11, "bold"))
        self.lbl_station.pack(anchor="w")
        self.lbl_track = ttk.Label(info, text="", foreground="#555")
        self.lbl_track.pack(anchor="w")

        # Controls
        ctl = ttk.Frame(self, padding=8)
        ctl.pack(fill="x")
        ttk.Button(ctl, text="▶ Play", command=self._play_selected).pack(side="left")
        ttk.Button(ctl, text="■ Stop", command=self._stop).pack(side="left", padx=(6, 0))
        ttk.Button(ctl, text="+ Add", command=self._add_station).pack(side="left", padx=(18, 0))
        ttk.Button(ctl, text="− Remove", command=self._remove_station).pack(side="left", padx=(6, 0))
        ttk.Button(ctl, text="🔍 Search", command=self._open_search).pack(side="left", padx=(6, 0))

        ttk.Label(ctl, text="Volume").pack(side="left", padx=(18, 4))
        self.volume = tk.IntVar(value=70)
        self.player.volume = 70
        ttk.Scale(ctl, from_=0, to=100, variable=self.volume,
                  command=lambda v: setattr(self.player, "volume", float(v))
                  ).pack(side="left", fill="x", expand=True)

        # Status bar
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w", relief="sunken",
                  padding=(6, 2)).pack(fill="x", side="bottom")

    def _refresh_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, st in enumerate(self.stations):
            self.tree.insert("", "end", iid=str(i), values=(st.name, st.genre))
        if self.stations:
            self.tree.selection_set("0")
            self.tree.focus("0")

    def _selected_station(self) -> Station | None:
        sel = self.tree.selection()
        return self.stations[int(sel[0])] if sel else None

    # ---- actions ----------------------------------------------------------
    def _play_selected(self) -> None:
        st = self._selected_station()
        if st is not None:
            self._play_station(st)

    def _play_station(self, st: Station) -> None:
        self.current = st
        self.player.play(st.url)
        self.lbl_station.config(text=st.name)
        self.lbl_track.config(text="")
        self.status.set(f"Connecting: {st.url}")

    def _stop(self) -> None:
        self.player.stop()
        self.current = None
        self.lbl_station.config(text="Nothing playing")
        self.lbl_track.config(text="")
        self.status.set("Stopped")

    def _add_station(self) -> None:
        name = simpledialog.askstring("New station", "Name:", parent=self)
        if not name:
            return
        url = simpledialog.askstring("New station", "Stream URL:", parent=self)
        if not url:
            return
        genre = simpledialog.askstring("New station", "Genre (optional):", parent=self) or ""
        self.stations.append(Station(name.strip(), url.strip(), genre.strip()))
        save_stations(self.stations)
        self._refresh_list()
        last = str(len(self.stations) - 1)
        self.tree.selection_set(last)
        self.tree.see(last)

    def _open_search(self) -> None:
        if getattr(self, "_search_win", None) is not None and self._search_win.winfo_exists():
            self._search_win.lift()
            return
        self._search_win = SearchDialog(self, on_play=self._play_station,
                                        on_add=self._add_found_station)

    def _add_found_station(self, st: Station) -> None:
        if any(s.url == st.url for s in self.stations):
            return
        self.stations.append(st)
        save_stations(self.stations)
        self._refresh_list()
        last = str(len(self.stations) - 1)
        self.tree.selection_set(last)
        self.tree.see(last)

    def _remove_station(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        st = self.stations[idx]
        if not messagebox.askyesno("Remove", f"Remove station \"{st.name}\"?", parent=self):
            return
        if self.current is st:
            self._stop()
        del self.stations[idx]
        save_stations(self.stations)
        self._refresh_list()

    def _on_stream_error(self) -> None:
        name = self.current.name if self.current else "stream"
        self.status.set(f"Error: could not play {name}")
        self.lbl_station.config(text="Stream error")

    # ---- polling ----------------------------------------------------------
    def _poll(self) -> None:
        if self.current is not None:
            state = self.player.state()
            track = self.player.now_playing()
            if track:
                self.lbl_track.config(text=track)
            if state in ("Opening", "Buffering"):
                self.status.set("Buffering…")
            elif state == "Playing":
                self.status.set(f"Playing: {self.current.name}")
        self.after(POLL_MS, self._poll)

    def _on_close(self) -> None:
        self.player.release()
        self.destroy()


def main() -> None:
    RadioApp().mainloop()
