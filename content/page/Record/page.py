import json
import os
import time
from collections import deque

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.graphics import Color, Line
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.uix.modalview import ModalView
from kivy_garden.mapview import MapLayer, MapView  # MapView: supaya @MapView terdaftar di Factory
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from content.util.paths import Paths
from content.service.track_manager import TrackManager
from content.service.history_manager import HistoryManager
from content.service.compass_manager import CompassManager

LIVE_FILE = Paths.TRACK

ORANGE = (1, 0.4, 0.13, 1)


class RecordModal(ModalView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.started = False

    def on_start(self):
        if self.started:
            return

        if not TrackManager.has_permission():
            TrackManager.ask_permission(self._after_permission)
            return

        if not TrackManager.gps_enabled():
            self._warn("GPS mati. Nyalakan lokasi dulu, lalu tekan Start.")
            return

        self._begin()

    def _after_permission(self, granted):
        if granted:
            self.on_start()
        else:
            self._warn("Izin lokasi diperlukan untuk merekam.")

    def _begin(self):
        app = MDApp.get_running_app()
        record = app.root.ids.screen_manager.get_screen("Record")

        if not TrackManager.start():
            self._warn("Gagal menjalankan perekaman.")
            return

        record.start_timer()
        self.started = True
        self.dismiss()

    def _warn(self, text):
        from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
        MDSnackbar(
            MDSnackbarText(text=text),
            y=dp(24),
            pos_hint={"center_x": .5},
            size_hint_x=.9,
        ).open()

    def on_dismiss(self):
        if not self.started:
            app = MDApp.get_running_app()
            app.root.ids.screen_manager.current = "Home"
            app.root.ids.navbar.select("Home")

class TrackLine(MapLayer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.segments = [[]]
        self.lines = []        # satu objek Line per segmen
        self.tail_line = None  # garis pendek menuju marker
        self.tail_pos = None   # (lat, lon) ujung ekor

    def _new_line(self, points=None):
        with self.canvas:
            Color(*ORANGE)
            line = Line(points=points or [], width=3, cap="round", joint="round")
        self.lines.append(line)
        return line

    def add_point(self, lat, lon):
        self.segments[-1].append((lat, lon))

        mapview = self.parent
        if mapview is None:
            return

        if len(self.lines) < len(self.segments):
            self._new_line()

        x, y = mapview.get_window_xy_from(lat, lon, mapview.zoom)
        self.lines[-1].points += [x, y]

    def break_line(self):
        if self.segments[-1]:
            self.segments.append([])
        self.clear_tail()

    def set_tail(self, lat, lon):
        mapview = self.parent
        seg = self.segments[-1]
        if mapview is None or not seg:
            return

        self.tail_pos = (lat, lon)

        if self.tail_line is None:
            with self.canvas:
                Color(*ORANGE)
                self.tail_line = Line(width=3, cap="round", joint="round")

        zoom = mapview.zoom
        ax, ay = mapview.get_window_xy_from(seg[-1][0], seg[-1][1], zoom)
        bx, by = mapview.get_window_xy_from(lat, lon, zoom)
        self.tail_line.points = [ax, ay, bx, by]

    def clear_tail(self):
        self.tail_pos = None
        if self.tail_line is not None:
            self.tail_line.points = []

    def clear(self):
        self.segments = [[]]
        self.lines = []
        self.tail_line = None
        self.tail_pos = None
        self.canvas.clear()

    def reposition(self):
        # Dipanggil MapView saat geser/zoom: hitung ulang semua titik.
        mapview = self.parent
        if mapview is None:
            return

        self.canvas.clear()
        self.lines = []
        self.tail_line = None
        zoom = mapview.zoom

        for seg in self.segments:
            if not seg:
                continue
            pts = []
            for lat, lon in seg:
                pts += mapview.get_window_xy_from(lat, lon, zoom)
            self._new_line(pts)

        if self.tail_pos:
            self.set_tail(*self.tail_pos)


class Record(MDScreen):
    _clock = None
    _compass_clock = None
    _anim = None
    _target = None

    recording = BooleanProperty(False)
    paused = BooleanProperty(False)
    follow_heading = BooleanProperty(False)

    started_at = 0
    marker_pos = None
    cur_sid = None
    centered = False
    pause_start = 0
    paused_total = 0
    last_ts = None
    _offset = 0

    def on_kv_post(self, base_widget):
        self.map_view = self.ids.map_view
        self.human_position = self.ids.human_position
        self.status = self.ids.status
        self.queue = deque()

        try:
            cache = os.path.join(MDApp.get_running_app().user_data_dir, "map_cache")
            os.makedirs(cache, exist_ok=True)
            self.map_view.map_source.cache_dir = cache
        except Exception as e:
            print("[record] cache_dir gagal diatur:", e)

        self.map_view.bind(zoom=self.update_marker_scale)
        self.update_marker_scale(self.map_view, self.map_view.zoom)

    def on_enter(self):
        self._start_compass()
        if self.recording:
            self._schedule()
            self.tick(0)  # kejar titik yang masuk saat layar tidak aktif
        else:
            Factory.RecordModal().open()

    def on_leave(self):
        self._stop_compass()
        self.cancel_timers()
        self._flush()

    # ------------------------------------------------------------------
    # Kompas & rotasi peta
    # ------------------------------------------------------------------
    def _start_compass(self):
        CompassManager.start()
        if self._compass_clock is None:
            self._compass_clock = Clock.schedule_interval(self._update_compass, 1 / 20)

    def _stop_compass(self):
        if self._compass_clock:
            self._compass_clock.cancel()
            self._compass_clock = None
        CompassManager.stop()

    def _update_compass(self, dt):
        h = CompassManager.heading()
        if h is None:
            return
        self.ids.compass.angle = h
        if self.follow_heading:
            self.map_view.bearing = h        # peta diputar berlawanan arah jarum jam
            self.human_position.rot = -h     # marker tetap tegak di layar

    def toggle_follow(self):
        self.follow_heading = not self.follow_heading
        if self.follow_heading:
            if self.marker_pos:
                self.map_view.center_on(*self.marker_pos)
        else:
            self.map_view.bearing = 0
            self.human_position.rot = 0

    # ------------------------------------------------------------------
    # Baca data dari tracker
    # ------------------------------------------------------------------
    def read_new_points(self):
        path = Paths.database(LIVE_FILE)
        if not os.path.exists(path):
            return []

        try:
            with open(path, "rb") as f:
                f.seek(self._offset)
                chunk = f.read()
        except OSError:
            return []

        end = chunk.rfind(b"\n")
        if end < 0:
            return []
        self._offset += end + 1

        hasil = []
        for baris in chunk[:end].split(b"\n"):
            try:
                p = json.loads(baris)
            except ValueError:
                continue
            if "ev" in p:
                self.handle_event(p)
                continue
            try:
                lat = float(p["lat"])
                lon = float(p["lon"])
                ts = float(p.get("ts", 0))
                sid = p.get("seg", 0)
            except (ValueError, KeyError, TypeError):
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            if ts < self.started_at - 1:
                continue
            hasil.append((lat, lon, ts, sid))
        return hasil

    def handle_event(self, p):
        try:
            ts = float(p.get("ts", time.time()))
        except (ValueError, TypeError):
            return
        ev = p.get("ev")
        if ev == "pause" and not self.paused:
            self.paused = True
            self.pause_start = ts
        elif ev == "resume" and self.paused:
            self.paused_total += max(0, ts - self.pause_start)
            self.paused = False

    # ------------------------------------------------------------------
    # Titik baru -> antrean -> animasi marker (hanya jalan saat ada titik)
    # ------------------------------------------------------------------
    def process_new_points(self):
        points = self.read_new_points()
        if not points:
            return

        self.queue.extend(points)

        # Antrean menumpuk (mis. habis layar mati): gambar langsung tanpa animasi.
        if len(self.queue) > 4:
            self._stop_anim()
            while len(self.queue) > 4:
                lat, lon, ts, sid = self.queue.popleft()
                self._commit(lat, lon, sid)
                self.last_ts = ts
            self.move_marker(*self.marker_pos)
            self.ids.track_line.clear_tail()

        if self._anim is None:
            self._next()

    def _commit(self, lat, lon, sid):
        """Kunci titik ke garis utama."""
        line = self.ids.track_line
        if sid != self.cur_sid:
            self.cur_sid = sid
            line.break_line()
        line.add_point(lat, lon)
        self.marker_pos = (lat, lon)

    def _next(self):
        if not self.queue:
            self._anim = None
            return

        lat, lon, ts, sid = self.queue.popleft()

        # Titik pertama / segmen baru: loncat langsung, tanpa animasi.
        if sid != self.cur_sid or self.marker_pos is None:
            self._commit(lat, lon, sid)
            self.last_ts = ts
            self.move_marker(lat, lon)
            if not self.centered or self.follow_heading:
                self.centered = True
                self.map_view.center_on(lat, lon)
            self._next()
            return

        # Durasi = selisih waktu asli antar titik, jadi laju marker = laju asli.
        gap = 1.0 if self.last_ts is None else ts - self.last_ts
        gap = max(0.3, min(6.0, gap)) / (1 + len(self.queue))
        self.last_ts = ts

        self._target = (lat, lon, sid)
        anim = Animation(lat=lat, lon=lon, duration=gap, t="linear")
        anim.bind(on_progress=self._on_anim_progress,
                  on_complete=self._on_anim_done)
        self._anim = anim
        anim.start(self.human_position)

    def _on_anim_progress(self, anim, widget, progress):
        if self.follow_heading:
            self.map_view.center_on(widget.lat, widget.lon)  # peta tetap berpusat di marker
        layer = getattr(widget, "_layer", None)
        if layer:
            layer.reposition()
        self.ids.track_line.set_tail(widget.lat, widget.lon)

    def _on_anim_done(self, anim, widget):
        self._anim = None
        if self._target:
            lat, lon, sid = self._target
            self._target = None
            self._commit(lat, lon, sid)
            self.ids.track_line.clear_tail()
        self._next()

    def _stop_anim(self, commit=True):
        if self._anim is None:
            return
        self._anim.cancel(self.human_position)
        self._anim = None
        target, self._target = self._target, None
        if target and commit:
            self._commit(*target)

    def _flush(self):
        """Selesaikan semua titik yang tertunda tanpa animasi."""
        self._stop_anim()
        while self.queue:
            lat, lon, ts, sid = self.queue.popleft()
            self._commit(lat, lon, sid)
            self.last_ts = ts
        if self.marker_pos:
            self.move_marker(*self.marker_pos)
        self.ids.track_line.clear_tail()

    def move_marker(self, lat, lon):
        self.human_position.lat = lat
        self.human_position.lon = lon

        layer = getattr(self.human_position, "_layer", None)
        if layer:
            layer.reposition()

    def tick(self, dt):
        self.process_new_points()

        now = time.time()
        diam = self.paused_total + (now - self.pause_start if self.paused else 0)
        detik = int(max(0, now - self.started_at - diam))
        jam, sisa = divmod(detik, 3600)
        menit, detik = divmod(sisa, 60)

        if self.marker_pos:
            posisi = f"{self.marker_pos[0]:.5f}, {self.marker_pos[1]:.5f}"
        else:
            posisi = "Menunggu GPS..."

        waktu = f"{jam:02d}:{menit:02d}:{detik:02d}"
        if self.paused:
            waktu += "  (jeda otomatis)"

        arah = CompassManager.label(CompassManager.heading())
        self.status.text = f"{waktu}\n{posisi}" + (f"\n{arah}" if arah else "")

    def update_marker_scale(self, map_view, zoom):
        size = max(8, min(48, 24 * (2 ** (zoom - 14))))
        self.human_position.size = (size, size)

    # ------------------------------------------------------------------
    # Kontrol rekaman
    # ------------------------------------------------------------------
    def start_timer(self):
        self.cancel_timers()
        self._stop_anim(commit=False)

        self.recording = True
        self.started_at = time.time()
        self.queue = deque()
        self.marker_pos = None
        self.cur_sid = None
        self.last_ts = None
        self.centered = False
        self.paused = False
        self.pause_start = 0
        self.paused_total = 0
        self.ids.track_line.clear()

        try:
            path = Paths.database(LIVE_FILE)
            open(path, "ab").close()
            self._offset = os.path.getsize(path)
        except OSError as e:
            print("[record] gagal siapkan file track:", e)
            self._offset = 0

        self._schedule()

    def _schedule(self):
        self.cancel_timers()
        self._clock = Clock.schedule_interval(self.tick, 1)

    def cancel_timers(self):
        if self._clock:
            self._clock.cancel()
            self._clock = None

    def save_history(self):
        now = time.time()
        paused = self.paused_total
        if self.paused:
            paused += max(0, now - self.pause_start)

        return HistoryManager.add(
            started_at=self.started_at,
            ended_at=now,
            paused_s=paused,
            segments=self.ids.track_line.segments,
        )

    def stop_tracking(self):
        TrackManager.stop()
        self.cancel_timers()

        self.process_new_points()
        self._flush()

        saved = self.save_history()

        self.recording = False
        self.marker_pos = None
        self.status.text = (
            "Perekaman disimpan ke riwayat" if saved
            else "Perekaman dihentikan (jalur terlalu pendek, tidak disimpan)"
        )

        app = MDApp.get_running_app()
        app.root.ids.screen_manager.current = "Home"
        app.root.ids.navbar.select("Home")


Builder.load_file(Paths.file("page", "Record", "page.kv"))