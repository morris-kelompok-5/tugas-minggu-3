import datetime

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty
from kivy_garden.mapview import MapLayer
from kivymd.uix.screen import MDScreen

from content.service.history_manager import HistoryManager, MONTHS
from content.util.paths import Paths

ORANGE = (1, 0.4, 0.13)
MIN_ALPHA = 0.12


def age_alpha(days):
    if days <= 0:
        return 1.0
    return max(MIN_ALPHA, 0.6 / days)


class HistoryLayer(MapLayer):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items = []
        self._textures = {}

    def set_items(self, entries):
        today = datetime.date.today()
        items = []

        for entry in reversed(entries):
            try:
                day = datetime.date.fromisoformat(entry["date"])
            except (KeyError, ValueError):
                continue

            segments = [s for s in entry.get("segments", []) if len(s) >= 2]
            if not segments:
                continue

            days = (today - day).days
            items.append({
                "segments": segments,
                "alpha": age_alpha(days),
                "width": 4 if days <= 0 else 3,
                "label": f"{day.day} {MONTHS[day.month - 1]} {day.year}",
                "anchor": self._anchor(segments),
            })

        self.items = items
        self.reposition()

    @staticmethod
    def _anchor(segments):
        longest = max(segments, key=len)
        return longest[len(longest) // 2]

    def _texture(self, text):
        tex = self._textures.get(text)
        if tex is None:
            label = CoreLabel(text=text, font_size=sp(12), color=(0.1, 0.1, 0.1, 1))
            label.refresh()
            tex = label.texture
            self._textures[text] = tex
        return tex

    def reposition(self):
        mapview = self.parent
        if mapview is None:
            return

        self.canvas.clear()
        zoom = mapview.zoom

        with self.canvas:
            for item in self.items:
                alpha = item["alpha"]

                Color(*ORANGE, alpha)
                for seg in item["segments"]:
                    pts = []
                    for lat, lon in seg:
                        pts += mapview.get_window_xy_from(lat, lon, zoom)
                    Line(points=pts, width=item["width"], cap="round", joint="round")

                tex = self._texture(item["label"])
                ax, ay = mapview.get_window_xy_from(*item["anchor"], zoom)
                pad = dp(5)
                w, h = tex.size
                x = ax - w / 2
                y = ay + dp(8)

                Color(1, 1, 1, 0.9 * alpha)
                RoundedRectangle(
                    pos=(x - pad, y - pad),
                    size=(w + 2 * pad, h + 2 * pad),
                    radius=[dp(8)],
                )
                Color(1, 1, 1, alpha)
                Rectangle(texture=tex, pos=(x, y), size=tex.size)


class Map(MDScreen):
    empty = BooleanProperty(True)
    _latest_id = None

    def on_enter(self, *args):
        history = HistoryManager.load()
        self.empty = not history

        self.ids.history_layer.set_items(history)

        if history and history[0].get("id") != self._latest_id:
            self._latest_id = history[0].get("id")
            start = history[0]["start"]
            self.ids.map_view.center_on(start["lat"], start["lon"])


Builder.load_file(Paths.file("page", "Map", "page.kv"))