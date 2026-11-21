from datetime import datetime

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogHeadlineText,
    MDDialogContentContainer,
    MDDialogButtonContainer,
)
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import (
    MDTextField,
    MDTextFieldHintText,
    MDTextFieldHelperText,
)

from content.util.paths import Paths
from content.service.profile_manager import Profiles
from content.util.math_body_health import BodyMath


class Profile(MDScreen):
    dialog = None

    def on_enter(self, *args):
        self.load_profile()

    # ---------- tampilan ----------
    def load_profile(self):
        data = Profiles.Read()

        nama = data.get("nama", "")
        tanggal_lahir = data.get("tanggal_lahir", "")
        berat = data.get("berat_badan", 0)
        tinggi = data.get("tinggi_badan", 0)

        self.ids.nama.text = nama or "-"
        self.ids.tanggal_lahir.text = f"Tanggal lahir: {tanggal_lahir or '-'}"
        self.ids.berat.text = f"BB: {berat} kg"
        self.ids.tinggi.text = f"TB: {tinggi} cm"

        health = BodyMath.GetBodyHealth(tanggal_lahir, berat, tinggi)

        umur = health["umur"]
        imt = health["imt"]

        self.ids.umur.text = (
            f"Umur: {umur} tahun"
            if umur is not None else "Umur: Tidak diketahui"
        )
        self.show_result(imt if imt is not None else "-", health["kategori"])

    def show_result(self, imt, kategori):
        self.ids.imt.text = str(imt)
        self.ids.kategori.text = f"Status: {kategori}"

    # ---------- modal edit ----------
    def _make_field(self, hint, text="", helper="", input_filter=None):
        field = MDTextField(
            MDTextFieldHintText(text=hint),
            MDTextFieldHelperText(text=helper, mode="on_error"),
            text=text,
            mode="outlined",
            input_filter=input_filter,
            multiline=False,
        )
        return field

    def open_edit_modal(self):
        data = Profiles.Read()

        berat = data.get("berat_badan") or ""
        tinggi = data.get("tinggi_badan") or ""

        self.f_nama = self._make_field(
            "Nama", data.get("nama", ""), "Nama wajib diisi"
        )
        self.f_tgl = self._make_field(
            "Tanggal lahir (dd/mm/yyyy)",
            data.get("tanggal_lahir", ""),
            "Format harus dd/mm/yyyy",
        )
        self.f_berat = self._make_field(
            "Berat badan (kg)", str(berat), "Isi angka lebih dari 0",
            input_filter="float",
        )
        self.f_tinggi = self._make_field(
            "Tinggi badan (cm)", str(tinggi), "Isi angka lebih dari 0",
            input_filter="float",
        )

        self.dialog = MDDialog(
            MDDialogHeadlineText(text="Edit Profil"),
            MDDialogContentContainer(
                self.f_nama,
                self.f_tgl,
                self.f_berat,
                self.f_tinggi,
                orientation="vertical",
                spacing=dp(12),
                padding=[0, dp(8), 0, 0],
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Batal"),
                    style="text",
                    on_release=lambda *_: self.dialog.dismiss(),
                ),
                MDButton(
                    MDButtonText(text="Simpan"),
                    style="text",
                    on_release=lambda *_: self.save_profile(),
                ),
                spacing=dp(8),
            ),
        )
        self.dialog.open()

    def save_profile(self):
        nama = self.f_nama.text.strip()
        tgl = self.f_tgl.text.strip()
        valid = True

        # nama
        self.f_nama.error = not nama
        valid &= bool(nama)

        # tanggal lahir
        try:
            datetime.strptime(tgl, "%d/%m/%Y")
            self.f_tgl.error = False
        except ValueError:
            self.f_tgl.error = True
            valid = False

        # berat & tinggi
        berat = self._to_float(self.f_berat.text)
        tinggi = self._to_float(self.f_tinggi.text)
        self.f_berat.error = berat is None
        self.f_tinggi.error = tinggi is None
        valid &= berat is not None and tinggi is not None

        if not valid:
            return

        Profiles.Update(
            nama=nama,
            tanggal_lahir=tgl,
            berat_badan=berat,
            tinggi_badan=tinggi,
        )
        self.dialog.dismiss()
        self.load_profile()

    @staticmethod
    def _to_float(value):
        try:
            number = float(value.replace(",", "."))
            return number if number > 0 else None
        except ValueError:
            return None


Builder.load_file(Paths.file("page", "Profile", "page.kv"))