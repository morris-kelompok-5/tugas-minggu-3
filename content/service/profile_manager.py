import os
from datetime import date, datetime

from content.util.paths import Paths


class Profiles:
    FILE = Paths.PROFILE

    MIN_UMUR = 5 
    MAX_UMUR = 120
    MIN_UKURAN = 10      

    FORMAT_TANGGAL = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %m %Y")

    DEFAULT = {
        "nama": "",
        "tanggal_lahir": "",
        "berat_badan": 0,
        "tinggi_badan": 0,
    }

    _cache = None

    @classmethod
    def Exists(cls):
        return os.path.exists(Paths.database(cls.FILE))

    @classmethod
    def Read(cls):
        if cls._cache is None:
            data = Paths.read_json(cls.FILE)
            cls._cache = {**cls.DEFAULT, **(data if isinstance(data, dict) else {})}
        return dict(cls._cache)

    # ------------------------------------------------------------------
    # Validasi
    # ------------------------------------------------------------------
    @classmethod
    def ParseTanggal(cls, teks):
        teks = str(teks or "").strip()
        for fmt in cls.FORMAT_TANGGAL:
            try:
                return datetime.strptime(teks, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def HitungUmur(lahir):
        today = date.today()
        return today.year - lahir.year - ((today.month, today.day) < (lahir.month, lahir.day))

    @classmethod
    def Validate(cls, data):
        if not str(data.get("nama", "")).strip():
            return "Nama tidak boleh kosong."

        lahir = cls.ParseTanggal(data.get("tanggal_lahir"))
        if lahir is None:
            return "Tanggal lahir tidak valid."

        umur = cls.HitungUmur(lahir)
        if umur < cls.MIN_UMUR:
            return f"Umur minimal {cls.MIN_UMUR} tahun."
        if umur > cls.MAX_UMUR:
            return "Tanggal lahir tidak masuk akal."

        for label, key in (("Berat badan", "berat_badan"),
                           ("Tinggi badan", "tinggi_badan")):
            try:
                nilai = float(data.get(key))
            except (TypeError, ValueError):
                return f"{label} harus berupa angka."
            if not nilai >= cls.MIN_UKURAN:
                return f"{label} tidak boleh kurang dari {cls.MIN_UKURAN}."

        return None

    # ------------------------------------------------------------------
    # Simpan
    # ------------------------------------------------------------------
    @classmethod
    def Update(cls, _validasi=True, **perubahan):
        data = cls.Read()
        baru = {k: v for k, v in perubahan.items() if k in cls.DEFAULT}

        if isinstance(baru.get("nama"), str):
            baru["nama"] = baru["nama"].strip()

        if all(data[k] == v for k, v in baru.items()):
            return data

        data.update(baru)

        if _validasi:
            error = cls.Validate(data)
            if error:
                raise ValueError(error)

        Paths.write_json(data, cls.FILE)
        cls._cache = data
        return dict(data)

    @classmethod
    def CreateData(cls, nama="", tanggal_lahir="", berat_badan=0, tinggi_badan=0):
        if Paths.read_json(cls.FILE):
            return cls.Read()
        kosong = not (nama or tanggal_lahir or berat_badan or tinggi_badan)

        return cls.Update(
            _validasi=not kosong,
            nama=nama,
            tanggal_lahir=tanggal_lahir,
            berat_badan=berat_badan,
            tinggi_badan=tinggi_badan,
        )