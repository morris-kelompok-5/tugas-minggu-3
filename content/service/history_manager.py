import math
import time

from content.util.math_location import path_length
from content.util.paths import Paths

DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


class HistoryManager:
    MAX_ITEMS = 100

    @staticmethod
    def load():
        data = Paths.read_json(Paths.HISTORY)
        if not isinstance(data, list):
            return []
        return [h for h in data if isinstance(h, dict)]

    @staticmethod
    def _valid_point(lat, lon):
        return (
            isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180
        )

    @staticmethod
    def _clean_segments(segments):
        clean = []
        for seg in segments or []:
            pts = [
                [round(lat, 6), round(lon, 6)]
                for lat, lon in seg
                if HistoryManager._valid_point(lat, lon)
            ]
            if pts:
                clean.append(pts)
        return clean

    @staticmethod
    def add(started_at, ended_at, paused_s, segments):
        clean = HistoryManager._clean_segments(segments)

        if sum(len(seg) for seg in clean) < 2:
            return None

        distance = path_length(clean)

        start = clean[0][0]
        end = clean[-1][-1]

        lt = time.localtime(started_at)
        day = DAYS[lt.tm_wday]
        date_text = f"{lt.tm_mday} {MONTHS[lt.tm_mon - 1]} {lt.tm_year}"
        start_time = time.strftime("%H:%M:%S", lt)

        elapsed = max(0, int(ended_at - started_at))
        paused = min(max(0, int(paused_s or 0)), elapsed)
        active = elapsed - paused

        history = HistoryManager.load()

        # ID unik: pakai milidetik, dan naikkan jika masih bentrok
        entry_id = int(started_at * 1000)
        used_ids = {h.get("id") for h in history}
        while entry_id in used_ids:
            entry_id += 1

        entry = {
            "id": entry_id,
            "name": f"Rute {day}, {date_text} {start_time[:5]}",
            "day": day,
            "date": time.strftime("%Y-%m-%d", lt),
            "start_time": start_time,
            "end_time": time.strftime("%H:%M:%S", time.localtime(ended_at)),
            "started_at": started_at,
            "ended_at": ended_at,
            "elapsed_s": elapsed,
            "duration_s": active,
            "distance_m": round(distance, 1),
            "start": {"lat": start[0], "lon": start[1]},
            "destination": {"lat": end[0], "lon": end[1]},
            "segments": clean,
        }

        history.insert(0, entry)
        Paths.write_json(history[:HistoryManager.MAX_ITEMS], Paths.HISTORY)
        return entry

    @staticmethod
    def delete(entry_id):
        history = HistoryManager.load()
        remaining = [h for h in history if h.get("id") != entry_id]
        if len(remaining) == len(history):
            return False
        Paths.write_json(remaining, Paths.HISTORY)
        return True