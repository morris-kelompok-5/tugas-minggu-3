import atexit
import subprocess
import sys

from kivy.clock import Clock
from kivy.utils import platform

from content.util.paths import Paths

PERMS = (
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
)


class TrackManager:
    _proc = None

    @staticmethod
    def _service():
        from android import mActivity
        from jnius import autoclass

        name = mActivity.getPackageName() + ".ServiceTracker"
        return mActivity, autoclass(name)

    # ---------------- izin & GPS ----------------
    @staticmethod
    def has_permission():
        if platform != "android":
            return True
        try:
            from android.permissions import check_permission
            return any(check_permission(p) for p in PERMS)
        except Exception as e:
            print("[TrackManager] cek izin gagal:", repr(e))
            return False

    @staticmethod
    def ask_permission(callback):
        """callback(granted: bool), dipanggil di thread Kivy."""
        if platform != "android":
            callback(True)
            return

        from android.permissions import request_permissions

        def _done(perms, grants):
            granted = TrackManager.has_permission()
            Clock.schedule_once(lambda dt: callback(granted), 0)

        request_permissions(list(PERMS), _done)

    @staticmethod
    def gps_enabled():
        if platform != "android":
            return True
        try:
            from android import mActivity
            from jnius import autoclass, cast

            Context = autoclass("android.content.Context")
            LM = autoclass("android.location.LocationManager")
            lm = cast(
                "android.location.LocationManager",
                mActivity.getSystemService(Context.LOCATION_SERVICE),
            )
            return bool(lm.isProviderEnabled(LM.GPS_PROVIDER))
        except Exception as e:
            print("[TrackManager] cek GPS gagal:", repr(e))
            return True  # jangan blokir kalau pengecekannya sendiri gagal

    # ---------------- start / stop ----------------
    @staticmethod
    def start():
        if platform != "android":
            if TrackManager._proc and TrackManager._proc.poll() is None:
                return True
            try:
                TrackManager._proc = subprocess.Popen(
                    [sys.executable, Paths.file("service", "tracker.py"), "--watch-parent"],
                    stdin=subprocess.PIPE,
                )
                atexit.register(TrackManager.stop)
                print("[TrackManager] desktop: tracker tes dijalankan")
                return True
            except Exception as e:
                print("[TrackManager] gagal start tracker tes:", repr(e))
                return False

        if not TrackManager.has_permission():
            print("[TrackManager] izin lokasi belum ada, service tidak dijalankan")
            return False

        try:
            activity, service = TrackManager._service()
            service.start(activity, "")
            print("[TrackManager] service dinyalakan")
            return True
        except Exception as e:
            print("[TrackManager] gagal start:", repr(e))
            return False

    @staticmethod
    def stop():
        if platform != "android":
            proc = TrackManager._proc
            if proc and proc.poll() is None:
                proc.terminate()
            TrackManager._proc = None
            return

        try:
            activity, service = TrackManager._service()
            service.stop(activity)
            print("[TrackManager] service dihentikan")
        except Exception as e:
            print("[TrackManager] gagal stop:", repr(e))