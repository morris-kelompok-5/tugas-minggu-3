from datetime import datetime, date


class BodyMath:

    @classmethod
    def GetAge(cls, tanggal_lahir):
        try:
            lahir = datetime.strptime(
                tanggal_lahir, "%d/%m/%Y"
            ).date()

            sekarang = date.today()

            return (
                sekarang.year - lahir.year
                - ((sekarang.month, sekarang.day) <
                   (lahir.month, lahir.day))
            )

        except (ValueError, TypeError):
            return None

    @classmethod
    def GetBMI(cls, berat, tinggi):
        try:
            berat = float(berat)
            tinggi = float(tinggi) / 100

            if berat <= 0 or tinggi <= 0:
                return None

            return round(berat / (tinggi ** 2), 2)

        except (ValueError, TypeError):
            return None

    @classmethod
    def GetBodyCategory(cls, imt, umur):
        if imt is None or umur is None:
            return "Tidak diketahui"

        if umur < 18:
            return "Memerlukan penilaian anak"

        if imt < 17:
            return "Sangat perlu MBG"
        elif imt < 18.5:
            return "Perlu MBG"
        elif imt <= 25:
            return "MBG Tercapai"
        elif imt <= 27:
            return "Kebanyakan MBG"

        return "Sangat Kebanyakan MBG"

    @classmethod
    def GetBodyHealth(cls, tanggal_lahir, berat, tinggi):
        umur = cls.GetAge(tanggal_lahir)
        imt = cls.GetBMI(berat, tinggi)
        kategori = cls.GetBodyCategory(imt, umur)

        return {
            "umur": umur,
            "imt": imt,
            "kategori": kategori
        }