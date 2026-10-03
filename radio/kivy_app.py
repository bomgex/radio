"""Kivy UI: used on Android, also runnable on desktop with `python main.py --mobile`."""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.utils import platform

from .browser import SearchResult, search_stations
from .stations import STATIONS_FILE, Station, load_stations, save_stations

if platform == "android":
    from .android_player import AndroidPlayer as Player
else:
    from .player import RadioPlayer as Player

KV = """
#:import dp kivy.metrics.dp

<Row>:
    size_hint_y: None
    height: dp(60)
    spacing: dp(4)
    Button:
        text: root.title
        markup: True
        halign: "left"
        valign: "middle"
        text_size: self.width - dp(16), None
        background_normal: ""
        background_color: (0.22, 0.45, 0.75, 1) if root.active else (0.18, 0.18, 0.22, 1)
        on_release: root.on_tap()
    Button:
        text: root.action
        size_hint_x: None
        width: dp(56)
        background_normal: ""
        background_color: (0.3, 0.3, 0.35, 1)
        on_release: root.on_action()

<MainScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(8)
        spacing: dp(6)
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            Label:
                text: "Internet Radio"
                font_size: "20sp"
                bold: True
                halign: "left"
                text_size: self.size
                valign: "middle"
            Button:
                text: "Search"
                size_hint_x: None
                width: dp(100)
                on_release: app.root.current = "search"
        ScrollView:
            GridLayout:
                id: station_list
                cols: 1
                spacing: dp(4)
                size_hint_y: None
                height: self.minimum_height
        Label:
            id: lbl_station
            text: "Nothing playing"
            bold: True
            font_size: "17sp"
            size_hint_y: None
            height: dp(28)
            text_size: self.width, None
            halign: "left"
            shorten: True
        Label:
            id: lbl_track
            text: ""
            color: 0.75, 0.75, 0.75, 1
            size_hint_y: None
            height: dp(24)
            text_size: self.width, None
            halign: "left"
            shorten: True
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            Button:
                text: "Stop"
                size_hint_x: None
                width: dp(90)
                on_release: root.stop()
            Label:
                text: "Vol."
                size_hint_x: None
                width: dp(56)
            Slider:
                id: volume
                min: 0
                max: 100
                value: 70
                on_value: root.set_volume(self.value)
        Label:
            id: status
            text: "Ready"
            color: 0.6, 0.6, 0.6, 1
            size_hint_y: None
            height: dp(22)
            font_size: "13sp"
            text_size: self.width, None
            halign: "left"
            shorten: True

<SearchScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(8)
        spacing: dp(6)
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(6)
            Button:
                text: "<"
                size_hint_x: None
                width: dp(48)
                on_release: app.root.current = "main"
            TextInput:
                id: query
                hint_text: "Station name"
                multiline: False
                on_text_validate: root.search()
            Button:
                text: "Search"
                size_hint_x: None
                width: dp(90)
                on_release: root.search()
        ScrollView:
            GridLayout:
                id: result_list
                cols: 1
                spacing: dp(4)
                size_hint_y: None
                height: self.minimum_height
        Label:
            id: status
            text: "Tap a station to listen; \"+\" adds it to your list"
            color: 0.6, 0.6, 0.6, 1
            size_hint_y: None
            height: dp(22)
            font_size: "13sp"
            text_size: self.width, None
            halign: "left"
            shorten: True

ScreenManager:
    MainScreen:
        name: "main"
    SearchScreen:
        name: "search"
"""


class Row(BoxLayout):
    """One list entry: a wide tappable button plus a small action button."""

    def __init__(self, title: str, action: str, on_tap, on_action, active=False, **kw):
        self.title = title
        self.action = action
        self.active = active
        self._tap = on_tap
        self._act = on_action
        super().__init__(**kw)

    def on_tap(self):
        self._tap()

    def on_action(self):
        self._act()


class MainScreen(Screen):
    def refresh(self):
        app = App.get_running_app()
        if "station_list" not in self.ids:      # called before the kv tree exists
            return
        box = self.ids.station_list
        box.clear_widgets()
        for st in app.stations:
            title = f"{st.name}\n[size=13sp][color=#aaaaaa]{st.genre}[/color][/size]"
            box.add_widget(Row(title, "x",
                               on_tap=lambda s=st: app.play(s),
                               on_action=lambda s=st: app.remove_station(s),
                               active=(app.current is not None
                                       and st.url == app.current.url)))

    def stop(self):
        App.get_running_app().stop_playback()

    def set_volume(self, value):
        App.get_running_app().player.volume = value


class SearchScreen(Screen):
    results: list[SearchResult] = []
    _busy = False

    def search(self):
        q = self.ids.query.text.strip()
        if not q or self._busy:
            return
        self._busy = True
        self.ids.status.text = "Searching…"
        threading.Thread(target=self._worker, args=(q,), daemon=True).start()

    def _worker(self, q: str):
        try:
            self._show(search_stations(q))
        except Exception as exc:
            self._error(str(exc))

    @mainthread
    def _show(self, results: list[SearchResult]):
        self._busy = False
        self.results = results
        app = App.get_running_app()
        box = self.ids.result_list
        box.clear_widgets()
        for r in results:
            title = (f"{r.name}\n[size=13sp][color=#aaaaaa]"
                     f"{r.country} · {r.quality}[/color][/size]")
            box.add_widget(Row(title, "+",
                               on_tap=lambda r=r: app.play(r.to_station()),
                               on_action=lambda r=r: self._add(r)))
        self.ids.status.text = f"Found: {len(results)}" if results else "Nothing found"

    @mainthread
    def _error(self, message: str):
        self._busy = False
        self.ids.status.text = f"Error: {message}"

    def _add(self, r: SearchResult):
        added = App.get_running_app().add_station(r.to_station())
        self.ids.status.text = f"Added: {r.name}" if added else "Already in the list"


class RadioKivyApp(App):
    title = "Internet Radio"

    def build(self):
        self.stations_path = self._user_stations_path()
        self.stations: list[Station] = load_stations(self.stations_path)
        self.current: Station | None = None
        self.player = Player()
        self.player.volume = 70
        root = Builder.load_string(KV)
        Clock.schedule_once(lambda _dt: root.get_screen("main").refresh(), 0)
        Clock.schedule_interval(self._poll, 1.0)
        return root

    def _user_stations_path(self) -> Path:
        """Writable copy of stations.json (the APK contents are read-only)."""
        path = Path(self.user_data_dir) / "stations.json"
        if not path.exists() and STATIONS_FILE.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(STATIONS_FILE, path)
        return path

    # ---- shared actions ---------------------------------------------------
    @property
    def main(self) -> MainScreen:
        return self.root.get_screen("main")

    def play(self, st: Station):
        self.current = st
        self.player.play(st.url)
        self.main.ids.lbl_station.text = st.name
        self.main.ids.lbl_track.text = ""
        self.main.ids.status.text = "Connecting…"
        self.main.refresh()

    def stop_playback(self):
        self.player.stop()
        self.current = None
        self.main.ids.lbl_station.text = "Nothing playing"
        self.main.ids.lbl_track.text = ""
        self.main.ids.status.text = "Stopped"
        self.main.refresh()

    def add_station(self, st: Station) -> bool:
        if any(s.url == st.url for s in self.stations):
            return False
        self.stations.append(st)
        save_stations(self.stations, self.stations_path)
        self.main.refresh()
        return True

    def remove_station(self, st: Station):
        if st is self.current:
            self.stop_playback()
        self.stations = [s for s in self.stations if s is not st]
        save_stations(self.stations, self.stations_path)
        self.main.refresh()

    def _poll(self, _dt):
        if self.current is None:
            return
        state = self.player.state()
        track = self.player.now_playing()
        if track:
            self.main.ids.lbl_track.text = track
        if state in ("Opening", "Buffering"):
            self.main.ids.status.text = "Buffering…"
        elif state == "Playing":
            self.main.ids.status.text = f"Playing: {self.current.name}"
        elif state == "Reconnecting":
            self.main.ids.status.text = "Stream lost, reconnecting…"

    def on_pause(self):
        return True          # keep playing when the app goes to background

    def on_stop(self):
        self.player.release()


def main() -> None:
    RadioKivyApp().run()
