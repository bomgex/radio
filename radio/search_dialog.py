"""Search window: query radio-browser.info, preview a result, add it to the list."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .browser import SearchResult, search_stations
from .stations import Station


class SearchDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk, on_play: Callable[[Station], None],
                 on_add: Callable[[Station], None]) -> None:
        super().__init__(master)
        self.title("Поиск станций (radio-browser.info)")
        self.geometry("720x440")
        self.minsize(560, 320)
        self.transient(master)

        self._on_play = on_play
        self._on_add = on_add
        self._results: list[SearchResult] = []
        self._busy = False

        self._build_ui()
        self.entry.focus_set()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Название:").pack(side="left")
        self.query = tk.StringVar()
        self.entry = ttk.Entry(top, textvariable=self.query)
        self.entry.pack(side="left", fill="x", expand=True, padx=6)
        self.entry.bind("<Return>", lambda _e: self._search())
        self.btn_search = ttk.Button(top, text="Искать", command=self._search)
        self.btn_search.pack(side="left")

        frame = ttk.Frame(self, padding=(8, 0, 8, 0))
        frame.pack(fill="both", expand=True)
        cols = ("name", "country", "quality", "tags")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, title, width in (("name", "Станция", 240), ("country", "Страна", 130),
                                  ("quality", "Качество", 80), ("tags", "Теги", 220)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, stretch=(col in ("name", "tags")))
        self.tree.bind("<Double-1>", lambda _e: self._play())
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="▶ Прослушать", command=self._play).pack(side="left")
        ttk.Button(bottom, text="+ В мой список", command=self._add).pack(side="left", padx=(6, 0))
        self.status = tk.StringVar(value="Введите название и нажмите Enter")
        ttk.Label(bottom, textvariable=self.status, foreground="#555").pack(side="left", padx=12)

    # ---- search -----------------------------------------------------------
    def _search(self) -> None:
        q = self.query.get().strip()
        if not q or self._busy:
            return
        self._busy = True
        self.btn_search.state(["disabled"])
        self.status.set("Ищу…")
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q: str) -> None:
        try:
            results = search_stations(q)
            self.after(0, self._show_results, results)
        except Exception as exc:  # network errors surface in the status line
            self.after(0, self._show_error, str(exc))

    def _show_results(self, results: list[SearchResult]) -> None:
        self._busy = False
        self.btn_search.state(["!disabled"])
        self._results = results
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(results):
            self.tree.insert("", "end", iid=str(i),
                             values=(r.name, r.country, r.quality, r.tags))
        if results:
            self.tree.selection_set("0")
            self.status.set(f"Найдено: {len(results)}")
        else:
            self.status.set("Ничего не найдено")

    def _show_error(self, message: str) -> None:
        self._busy = False
        self.btn_search.state(["!disabled"])
        self.status.set(f"Ошибка: {message}")

    # ---- actions ----------------------------------------------------------
    def _selected(self) -> SearchResult | None:
        sel = self.tree.selection()
        return self._results[int(sel[0])] if sel else None

    def _play(self) -> None:
        r = self._selected()
        if r is not None:
            self._on_play(r.to_station())

    def _add(self) -> None:
        r = self._selected()
        if r is not None:
            self._on_add(r.to_station())
            self.status.set(f"Добавлено: {r.name}")
