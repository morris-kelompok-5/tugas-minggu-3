import os
import sys
import threading
import traceback


def _crash_file():
    base = os.environ.get("ANDROID_PRIVATE") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "crash.log")


def _save_crash(text):
    print(text)

    try:
        from content.service import crash_log
        crash_log.append(text)
        return
    except Exception:
        pass

    try:
        with open(_crash_file(), "a", encoding="utf-8") as f:
            f.write(text + "\n\n")
    except Exception:
        pass


def _thread_hook(args):
    text = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    _save_crash("[THREAD]\n" + text)


threading.excepthook = _thread_hook

def _show_crash(text):
    from kivy.app import App
    from kivy.core.window import Window
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    class CrashApp(App):
        def build(self):
            Window.clearcolor = (0.08, 0.08, 0.08, 1)
            label = Label(
                text="JAGJAG gagal start.\nFoto layar ini & kirim.\n\n" + text,
                font_size="12sp",
                size_hint_y=None,
                halign="left",
                valign="top",
                color=(1, 1, 1, 1),
            )
            label.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
            label.bind(texture_size=lambda w, v: setattr(w, "height", v[1]))
            view = ScrollView()
            view.add_widget(label)
            return view

    CrashApp().run()


def _start():
    import content.config.config

    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.utils import platform
    from kivymd.app import MDApp

    from content.page.Manager.page import Manager

    class MainApp(MDApp):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            self.location_permission_granted = False
            self.fine_location_granted = False
            self.notification_permission_granted = False

        def build(self):
            self.theme_cls.theme_style = "Light"
            return Manager()

        def on_start(self):
            if platform != "android":
                Clock.schedule_once(
                    lambda dt: Clock.schedule_once(
                        lambda dt: Window.show(), 0
                    ),
                    0
                )
                return

            Clock.schedule_once(self.ask_permissions, 1)

        def ask_permissions(self, dt=None):
            if platform != "android":
                return

            try:
                from android.permissions import request_permissions
                from jnius import autoclass

                BuildVersion = autoclass("android.os.Build$VERSION")
                sdk_version = BuildVersion.SDK_INT

                permissions = [
                    "android.permission.ACCESS_FINE_LOCATION",
                    "android.permission.ACCESS_COARSE_LOCATION",
                ]

                if sdk_version >= 33:
                    permissions.append("android.permission.POST_NOTIFICATIONS")

                request_permissions(permissions, self.on_permissions_result)

            except Exception as e:
                print(f"[PERMISSION ERROR] {e}")

        def on_permissions_result(self, permissions, grants):
            results = dict(zip(permissions, grants))

            fine = results.get("android.permission.ACCESS_FINE_LOCATION", False)
            coarse = results.get("android.permission.ACCESS_COARSE_LOCATION", False)
            notification = results.get("android.permission.POST_NOTIFICATIONS", True)

            self.fine_location_granted = bool(fine)
            self.location_permission_granted = bool(fine or coarse)
            self.notification_permission_granted = bool(notification)

            print("[PERMISSION] Fine location:", self.fine_location_granted)
            print("[PERMISSION] Coarse location:", bool(coarse))
            print("[PERMISSION] Location granted:", self.location_permission_granted)
            print("[PERMISSION] Notification:", self.notification_permission_granted)

            if not self.location_permission_granted:
                print("[WARNING] Izin lokasi belum diberikan.")

            if not self.fine_location_granted:
                print("[WARNING] GPS presisi belum diberikan.")

        def on_pause(self):
            return True

        def on_resume(self):
            if platform == "android":
                print("[APP] Application resumed.")

        def on_stop(self):
            print("[APP] Application stopped.")

    MainApp().run()


try:
    _start()
except Exception:
    _crash_text = traceback.format_exc()
    _save_crash(_crash_text)
    try:
        _show_crash(_crash_text)
    except Exception:
        _save_crash(_crash_text + "\n\n[Layar error juga gagal]\n" + traceback.format_exc())
        raise