import json
import os


class Paths:
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    CONTENT_DIR = os.path.join(BASE_DIR, "content")
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    DATABASE_DIR = os.path.join(os.environ.get("ANDROID_PRIVATE", BASE_DIR), "data")

    TRACK = "track.jsonl"
    PROFILE = "profiles.json"
    SCHEDULES = "schedules.json"
    HISTORY = "history.json"

    @classmethod
    def database(cls, *parts):
        os.makedirs(cls.DATABASE_DIR, exist_ok=True)
        return os.path.join(cls.DATABASE_DIR, *parts)

    @classmethod
    def read_json(cls, *parts):
        try:
            with open(cls.database(*parts), encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @classmethod
    def write_json(cls, data, *parts):
        path = cls.database(*parts)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    @classmethod
    def asset(cls, *parts):
        path = os.path.join(cls.ASSETS_DIR, *parts)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Asset tidak ditemukan: {path}")
        return path

    @classmethod
    def file(cls, *parts):
        path = os.path.join(cls.CONTENT_DIR, *parts)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File tidak ditemukan: {path}")
        return path