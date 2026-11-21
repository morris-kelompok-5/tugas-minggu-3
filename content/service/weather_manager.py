import json
import os
import threading
import time
from datetime import datetime

import requests
from kivy.app import App
from kivy.clock import Clock

API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

DEFAULT_ADM4 = "32.73.01.1004"

CACHE_TTL = 600 
TIMEOUT = 15


class WeatherManager:
    _mem = None
    @classmethod
    def fetch(cls, callback, adm4=DEFAULT_ADM4, force=False):
        """callback(result, error). result bisa tetap ada walau error (data cache lama)."""
        mem = cls._mem
        if (not force and mem and mem["adm4"] == adm4
                and time.time() - mem["fetched_at"] < CACHE_TTL):
            Clock.schedule_once(lambda dt: callback(mem, None), 0)
            return

        threading.Thread(
            target=cls._worker, args=(callback, adm4), daemon=True
        ).start()

    @classmethod
    def _worker(cls, callback, adm4):
        result, error = None, None
        try:
            resp = requests.get(
                API_URL,
                params={"adm4": adm4},
                headers={"User-Agent": "JagJag/0.1"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            result = cls.parse(resp.json(), adm4)
            cls._mem = result
            cls._save(result)
        except Exception as e:
            error = str(e)
            cached = cls._load(adm4)
            result = dict(cached, stale=True) if cached else None

        Clock.schedule_once(lambda dt: callback(result, error), 0)

    # ------------------------------------------------------------------
    # Olah data
    # ------------------------------------------------------------------
    @staticmethod
    def _dt(text):
        try:
            return datetime.strptime(str(text)[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    @classmethod
    def parse(cls, data, adm4):
        lokasi = data.get("lokasi") or {}
        first = (data.get("data") or [{}])[0]

        slots = []
        for day in first.get("cuaca", []):
            for s in day:
                slots.append({
                    "dt": str(s.get("local_datetime", "")),
                    "t": s.get("t"),
                    "hu": s.get("hu"),
                    "ws": s.get("ws"),
                    "tcc": s.get("tcc"),
                    "desc": s.get("weather_desc") or "",
                })

        slots = [s for s in slots if cls._dt(s["dt"])]
        slots.sort(key=lambda s: s["dt"])
        if not slots:
            raise ValueError("Data cuaca kosong")

        place = ", ".join(
            x for x in (lokasi.get("desa"), lokasi.get("kecamatan"), lokasi.get("kotkab")) if x
        )

        return {
            "adm4": adm4,
            "fetched_at": time.time(),
            "location": place or adm4,
            "slots": slots,
            "stale": False,
        }

    @classmethod
    def select(cls, slots, count=8):
        now = datetime.now()
        current = 0
        for i, s in enumerate(slots):
            if cls._dt(s["dt"]) <= now:
                current = i
            else:
                break
        return slots[current], slots[current + 1: current + 1 + count]

    @staticmethod
    def icon_for(desc, hour):
        d = (desc or "").lower()
        night = hour < 6 or hour >= 18

        if "petir" in d:
            return "weather-lightning-rainy"
        if "lebat" in d:
            return "weather-pouring"
        if "hujan" in d:
            return "weather-rainy"
        if "kabut" in d or "kabur" in d:
            return "weather-fog"
        if "asap" in d:
            return "weather-hazy"
        if "cerah berawan" in d:
            return "weather-night-partly-cloudy" if night else "weather-partly-cloudy"
        if "berawan" in d:
            return "weather-cloudy"
        if "cerah" in d:
            return "weather-night" if night else "weather-sunny"
        return "weather-cloudy"

    # ------------------------------------------------------------------
    # Cache di disk (supaya tetap tampil saat offline)
    # ------------------------------------------------------------------
    @staticmethod
    def _cache_file():
        try:
            base = App.get_running_app().user_data_dir
        except Exception:
            base = "."
        return os.path.join(base, "weather_cache.json")

    @classmethod
    def _save(cls, result):
        try:
            with open(cls._cache_file(), "w", encoding="utf-8") as f:
                json.dump(result, f)
        except OSError as e:
            print("[weather] gagal simpan cache:", e)

    @classmethod
    def _load(cls, adm4):
        try:
            with open(cls._cache_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if data.get("adm4") == adm4 else None
        except (OSError, ValueError):
            return None