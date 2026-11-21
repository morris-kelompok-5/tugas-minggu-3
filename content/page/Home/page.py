from datetime import datetime, date

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.modalview import ModalView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.relativelayout import MDRelativeLayout  # noqa: F401 (dipakai di .kv)
from kivymd.uix.label import MDLabel, MDIcon  # noqa: F401
from kivymd.uix.textfield import MDTextField, MDTextFieldTrailingIcon  # noqa: F401
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton  # noqa: F401
from kivymd.uix.scrollview import MDScrollView  # noqa: F401
from kivymd.uix.divider import MDDivider  # noqa: F401
from kivymd.uix.pickers import MDModalDatePicker

from content.util.paths import Paths
from content.service.profile_manager import Profiles
from content.service.weather_manager import WeatherManager


def _num(value, suffix=""):
    try:
        return f"{round(float(value))}{suffix}"
    except (TypeError, ValueError):
        return "-"


class WeatherSlotCard(MDBoxLayout):
    stamp = StringProperty()
    icon = StringProperty("weather-cloudy")
    temp = StringProperty()
    desc = StringProperty()


class WeatherStat(MDBoxLayout):
    icon = StringProperty()
    value = StringProperty()
    caption = StringProperty()

class ModalCreateProfile(ModalView):

    auto_dismiss = False
    _date_picker = None
    _date_touch = None

    def date_touch_down(self, field, touch):
        self._date_touch = touch.uid if field.collide_point(*touch.pos) else None

    def date_touch_up(self, field, touch):
        if self._date_touch == touch.uid and field.collide_point(*touch.pos):
            self._date_touch = None
            self.open_date_picker()

    def open_date_picker(self):
        field = self.ids.tanggal

        if self._date_picker and self._date_picker.parent:
            return

        try:
            d = datetime.strptime(field.text, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            d = date(2000, 1, 1)

        picker = MDModalDatePicker(
            year=d.year,
            month=d.month,
            day=d.day,
            max_date=date.today(),
        )
        picker.bind(
            on_ok=self._on_date_ok,
            on_cancel=lambda inst, *a: inst.dismiss(),
        )
        self._date_picker = picker
        picker.open()

    def _on_date_ok(self, picker, *args):
        selected = picker.get_date()
        if selected:
            self.ids.tanggal.text = selected[0].strftime("%d/%m/%Y")
            self.ids.tanggal.error = False
        picker.dismiss()

    def save(self):
        nama = self.ids.nama.text.strip()
        tanggal = self.ids.tanggal.text.strip()
        berat = self.ids.berat.text.strip()
        tinggi = self.ids.tinggi.text.strip()

        nama_ok = bool(nama)

        try:
            datetime.strptime(tanggal, "%d/%m/%Y")
            tanggal_ok = True
        except (ValueError, TypeError):
            tanggal_ok = False

        try:
            berat_value = float(berat)
            berat_ok = berat_value > 0
        except (ValueError, TypeError):
            berat_value = 0
            berat_ok = False

        try:
            tinggi_value = float(tinggi)
            tinggi_ok = tinggi_value > 0
        except (ValueError, TypeError):
            tinggi_value = 0
            tinggi_ok = False

        self.ids.nama.error = not nama_ok
        self.ids.tanggal.error = not tanggal_ok
        self.ids.berat.error = not berat_ok
        self.ids.tinggi.error = not tinggi_ok

        if not all((nama_ok, tanggal_ok, berat_ok, tinggi_ok)):
            return

        try:
            Profiles.CreateData(
                nama,
                tanggal,
                berat_value,
                tinggi_value
            )
        except Exception as e:
            print(f"[ERROR] Gagal menyimpan profil: {e}")
            return

        self.dismiss()


class Home(MDScreen):

    weather_location = StringProperty("Memuat lokasi...")
    weather_temp = StringProperty("--°")
    weather_desc = StringProperty("Memuat cuaca...")
    weather_icon = StringProperty("weather-cloudy")
    weather_hu = StringProperty("-")
    weather_ws = StringProperty("-")
    weather_tcc = StringProperty("-")
    weather_status = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.profile_modal = None
        self.profile_event = None
        self._weather_loading = False

    def on_enter(self, *args):
        self.refresh_weather()

        if Profiles.Exists():
            return

        if self.profile_modal and self.profile_modal.parent:
            return

        if self.profile_event:
            self.profile_event.cancel()

        self.profile_event = Clock.schedule_once(
            self.show_profile_modal,
            0.2
        )

    def show_profile_modal(self, dt):

        self.profile_event = None

        if Profiles.Exists():
            return

        if self.profile_modal and self.profile_modal.parent:
            return

        self.profile_modal = ModalCreateProfile()
        self.profile_modal.open()

    # ------------------------------------------------------------------
    # Cuaca
    # ------------------------------------------------------------------
    def refresh_weather(self, force=False):
        if self._weather_loading:
            return
        self._weather_loading = True
        self.weather_status = "Memuat cuaca..."
        WeatherManager.fetch(self._on_weather, force=force)

    def _on_weather(self, result, error):
        self._weather_loading = False

        if not result:
            self.weather_status = "Gagal memuat cuaca. Periksa koneksi internet."
            return

        now_slot, upcoming = WeatherManager.select(result["slots"])
        now_dt = WeatherManager._dt(now_slot["dt"])

        self.weather_location = result["location"]
        self.weather_temp = _num(now_slot["t"], "°")
        self.weather_desc = now_slot["desc"] or "-"
        self.weather_icon = WeatherManager.icon_for(now_slot["desc"], now_dt.hour)
        self.weather_hu = _num(now_slot["hu"], "%")
        self.weather_ws = _num(now_slot["ws"], " km/j")
        self.weather_tcc = _num(now_slot["tcc"], "%")

        if result.get("stale"):
            self.weather_status = "Data tersimpan (offline) · Sumber: BMKG"
        else:
            jam = datetime.fromtimestamp(result["fetched_at"]).strftime("%H:%M")
            self.weather_status = f"Diperbarui {jam} · Sumber: BMKG"

        row = self.ids.forecast_row
        row.clear_widgets()

        today = datetime.now().date()
        for slot in upcoming:
            dt = WeatherManager._dt(slot["dt"])
            stamp = dt.strftime("%H:%M")
            if dt.date() != today:
                stamp = "Bsk " + stamp

            row.add_widget(WeatherSlotCard(
                stamp=stamp,
                icon=WeatherManager.icon_for(slot["desc"], dt.hour),
                temp=_num(slot["t"], "°"),
                desc=slot["desc"] or "-",
            ))


Builder.load_file(
    Paths.file("page", "Home", "page.kv")
)