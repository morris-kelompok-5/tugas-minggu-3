from kivy.lang import Builder
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.modalview import ModalView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.relativelayout import MDRelativeLayout  # noqa: F401 (dipakai di .kv)
from kivymd.uix.gridlayout import MDGridLayout  # noqa: F401
from kivymd.uix.label import MDLabel, MDIcon  # noqa: F401
from kivymd.uix.textfield import MDTextField  # noqa: F401
from kivymd.uix.button import MDButton, MDButtonText, MDButtonIcon  # noqa: F401
from kivymd.uix.button import MDIconButton  # noqa: F401
from kivymd.uix.scrollview import MDScrollView  # noqa: F401

from content.util.paths import Paths
from content.service.alarm_manager import AlarmManager


class TimeChip(MDBoxLayout):
    text = StringProperty()


class ScheduleCard(MDBoxLayout):
    title = StringProperty()
    times = ListProperty()
    index = NumericProperty(0)
    screen = ObjectProperty()

    def on_kv_post(self, base_widget):
        for value in self.times:
            self.ids.chips.add_widget(TimeChip(text=value))


class AddScheduleModal(ModalView):
    screen = ObjectProperty()

    def on_kv_post(self, base_widget):
        self.ids.time_input.text = ", ".join(self.screen.DEFAULT_TIMES[3])

    def update_times(self, value):
        if value.isdigit():
            count = int(value)

            if count in self.screen.DEFAULT_TIMES:
                self.ids.time_input.text = ", ".join(
                    self.screen.DEFAULT_TIMES[count]
                )

    def submit(self):
        self.screen.add_schedule(
            self.ids.name_input.text,
            self.ids.frequency_input.text,
            self.ids.time_input.text,
            self,
            self.ids.error_label
        )


class Time(MDScreen):

    DEFAULT_TIMES = {
        1: ["08:00"],
        2: ["08:00", "18:00"],
        3: ["07:00", "12:00", "19:00"],
        4: ["07:00", "11:00", "15:00", "19:00"],
        5: ["06:00", "10:00", "13:00", "16:00", "20:00"]
    }

    empty = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.schedules = []
        self.load_schedules()

    def on_enter(self, *args):
        self.load_schedules()
        self.refresh_schedules()

    def load_schedules(self):
        data = Paths.read_json(Paths.SCHEDULES)

        self.schedules = data if isinstance(data, list) else []

    def save_schedules(self):
        Paths.write_json(self.schedules, Paths.SCHEDULES)

    def refresh_schedules(self):
        container = self.ids.schedule_list
        container.clear_widgets()

        self.empty = not self.schedules

        for index, schedule in enumerate(self.schedules):
            container.add_widget(
                ScheduleCard(
                    title=schedule["name"],
                    times=schedule["times"],
                    index=index,
                    screen=self
                )
            )

    def open_add_modal(self):
        AddScheduleModal(screen=self).open()

    def add_schedule(self, name, frequency, times, modal, error_label=None):
        def fail(message):
            if error_label is not None:
                error_label.text = message

        name = name.strip()

        if not name:
            return fail("Nama jadwal tidak boleh kosong.")

        if not frequency.isdigit():
            return fail("Frekuensi harus berupa angka.")

        count = int(frequency)

        if count not in self.DEFAULT_TIMES:
            return fail("Frekuensi harus antara 1 sampai 5.")

        raw_list = [
            value.strip()
            for value in times.split(",")
        ]

        if len(raw_list) != count:
            return fail(f"Jumlah jam harus {count}, pisahkan dengan koma.")

        time_list = []
        for value in raw_list:
            try:
                hour, minute = map(int, value.split(":"))

                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    return fail(f"Jam '{value}' tidak valid.")

            except ValueError:
                return fail(f"Format jam '{value}' salah (gunakan HH:MM).")

            time_list.append(f"{hour:02d}:{minute:02d}")  # "7:0" -> "07:00"

        if len(set(time_list)) != len(time_list):
            return fail("Ada jam yang sama, setiap jam harus berbeda.")

        self.schedules.append({
            "name": name,
            "times": time_list
        })

        self.save_schedules()
        AlarmManager.schedule(name, time_list)
        self.refresh_schedules()
        modal.dismiss()

    def delete_schedule(self, index):
        if 0 <= index < len(self.schedules):
            schedule = self.schedules.pop(index)
            AlarmManager.cancel(schedule["name"], schedule["times"])
            self.save_schedules()
            self.refresh_schedules()


Builder.load_file(Paths.file("page", "Time", "page.kv"))