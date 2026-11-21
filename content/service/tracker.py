import json
import math
import os
import sys
import threading
import time

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from content.util.math_location import distance_m, is_valid_coord
from content.util.paths import Paths

LIVE_FILE = Paths.TRACK

MAX_ACCURACY = 25.0
MAX_AGE = 10.0
MIN_MOVE = 5.0
PAUSE_MOVE = 6.0
MAX_SPEED = 15.0
PROCESS_NOISE = 3.0
GAP_BREAK = 15.0
PAUSE_AFTER = 8.0

# Watchdog: restart registrasi GPS kalau tidak ada fix valid.
WATCHDOG_STALE = 30.0        # setelah sudah pernah dapat fix
WATCHDOG_FIRST_FIX = 90.0    # menunggu fix pertama (cold start bisa lama)

GPS_INTERVAL_MS = 1500
USE_WAKELOCK = False


class Pipeline:

    def __init__(self):
        self.lat = None
        self.lon = None
        self.var = -1.0
        self.t = 0.0
        self.saved = None
        self.rejects = 0
        self.sid = 0
        self.last_fix = 0.0
        self.paused = False
        self.last_move = 0.0
        self.move_ref = None
        self.live_path = Paths.database(LIVE_FILE)

        os.makedirs(os.path.dirname(self.live_path), exist_ok=True)

    def feed(self, lat, lon, acc, t):
        if not is_valid_coord(lat, lon):
            return False

        now = time.time()
        age = now - t

        if age > MAX_AGE or age < -5:
            return False

        if not acc or acc <= 0:
            acc = 10.0

        if acc > MAX_ACCURACY:
            return False

        # Fix valid sudah diterima meskipun nantinya tidak perlu
        # disimpan karena pergerakannya terlalu kecil.
        if self.var < 0:
            self._new_segment(lat, lon, acc, t)
            return True

        dt = max(0.0, t - self.t)

        if dt > GAP_BREAK:
            self._new_segment(lat, lon, acc, t)
            return True

        d_raw = distance_m(self.lat, self.lon, lat, lon)

        if d_raw / max(dt, 1.0) > MAX_SPEED:
            self.rejects += 1

            if self.rejects < 3:
                return True

            self._new_segment(lat, lon, acc, t)
            return True

        self.rejects = 0

        self.var += dt * PROCESS_NOISE ** 2
        k = self.var / (self.var + acc * acc)

        self.lat += k * (lat - self.lat)
        self.lon += k * (lon - self.lon)

        self.var = (1 - k) * self.var
        self.t = t

        self._update_pause(acc, t)

        if self.saved is not None:
            d = distance_m(
                self.saved[0],
                self.saved[1],
                self.lat,
                self.lon
            )

            if d < max(MIN_MOVE, acc * 0.5):
                return True

        self._save(self.lat, self.lon, acc, t)
        return True

    def _update_pause(self, acc, t):
        if self.move_ref is None:
            self.move_ref = (self.lat, self.lon)
            self.last_move = t
            return

        d = distance_m(
            self.move_ref[0],
            self.move_ref[1],
            self.lat,
            self.lon
        )

        if d >= max(PAUSE_MOVE, acc * 0.5):
            self.move_ref = (self.lat, self.lon)
            self.last_move = t

            if self.paused:
                self.paused = False
                self._append({"ev": "resume", "ts": t})

        elif not self.paused and t - self.last_move >= PAUSE_AFTER:
            self.paused = True
            self._append({"ev": "pause", "ts": self.last_move})

    def _new_segment(self, lat, lon, acc, t):
        self.lat = lat
        self.lon = lon
        self.var = acc * acc
        self.t = t

        self.rejects = 0
        self.move_ref = (lat, lon)
        self.last_move = t

        if self.paused:
            self.paused = False
            self._append({"ev": "resume", "ts": t})

        self.sid = int(t)
        self._save(lat, lon, acc, t)

    def _append(self, data):
        line = json.dumps(data) + "\n"

        with open(self.live_path, "ab") as f:
            f.write(line.encode("utf-8"))

    def _save(self, lat, lon, acc, t):
        self.saved = (lat, lon)

        self._append({
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "acc": acc,
            "ts": t,
            "seg": self.sid,
        })


def run_android():
    from jnius import autoclass, PythonJavaClass, java_method

    PythonService = autoclass("org.kivy.android.PythonService")
    Context = autoclass("android.content.Context")
    PowerManager = autoclass("android.os.PowerManager")
    Looper = autoclass("android.os.Looper")
    LocationManager = autoclass("android.location.LocationManager")

    service = PythonService.mService

    if service is None:
        print("[tracker] PythonService tidak tersedia")
        return

    # Looper ditangkap SEKALI di thread utama service, lalu dipakai ulang
    # oleh semua registrasi. Thread watchdog tidak punya Looper sendiri,
    # jadi Looper.myLooper() di sana mengembalikan None dan restart gagal.
    try:
        if Looper.myLooper() is None:
            Looper.prepare()
        looper = Looper.myLooper()
    except Exception as e:
        print("[tracker] gagal menyiapkan Looper:", e)
        return

    pipe = Pipeline()

    stop = threading.Event()
    need_restart = threading.Event()

    registration_lock = threading.RLock()

    state = {
        "backend": None,
        "registered_at": 0.0,
        "last_error": None,
        "fused_broken": False,   # True -> pakai LocationManager saja
    }

    wake = None

    if USE_WAKELOCK:
        try:
            pm = service.getSystemService(Context.POWER_SERVICE)
            wake = pm.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "jagjag:tracker"
            )
            wake.acquire()
            print("[tracker] wakelock aktif")
        except Exception as e:
            print("[tracker] wakelock gagal:", e)

    lm = service.getSystemService(Context.LOCATION_SERVICE)

    # Listener ini mengimplementasikan dua interface:
    # 1. Android LocationManager
    # 2. Google Play Services Fused Location
    class Listener(PythonJavaClass):

        __javainterfaces__ = [
            "android/location/LocationListener",
            "com/google/android/gms/location/LocationListener",
        ]

        __javacontext__ = "app"

        @java_method("(Landroid/location/Location;)V")
        def onLocationChanged(self, loc):
            try:
                acc = loc.getAccuracy() if loc.hasAccuracy() else None

                valid = pipe.feed(
                    loc.getLatitude(),
                    loc.getLongitude(),
                    acc,
                    loc.getTime() / 1000.0,
                )

                if valid:
                    pipe.last_fix = time.time()

            except Exception as e:
                print("[tracker] gagal proses lokasi:", e)

        @java_method("(Ljava/lang/String;)V")
        def onProviderEnabled(self, provider):
            print("[tracker] provider aktif:", provider)
            need_restart.set()

        @java_method("(Ljava/lang/String;)V")
        def onProviderDisabled(self, provider):
            print("[tracker] provider nonaktif:", provider)

        @java_method("(Ljava/lang/String;ILandroid/os/Bundle;)V")
        def onStatusChanged(self, provider, status, extras):
            pass

    listener = Listener()

    class FusedSuccess(PythonJavaClass):

        __javainterfaces__ = [
            "com/google/android/gms/tasks/OnSuccessListener"
        ]

        __javacontext__ = "app"

        @java_method("(Ljava/lang/Object;)V")
        def onSuccess(self, result):
            print("[tracker] Fused Location berhasil terdaftar")

    class FusedFailure(PythonJavaClass):

        __javainterfaces__ = [
            "com/google/android/gms/tasks/OnFailureListener"
        ]

        __javacontext__ = "app"

        @java_method("(Ljava/lang/Exception;)V")
        def onFailure(self, error):
            print("[tracker] Fused Location gagal:", error)

            state["last_error"] = str(error)
            # Jangan coba Fused lagi, restart berikutnya pindah
            # ke LocationManager GPS.
            state["fused_broken"] = True
            need_restart.set()

    # Simpan referensi agar callback Java tidak di-GC.
    fused_success = FusedSuccess()
    fused_failure = FusedFailure()

    def make_fused():
        try:
            Availability = autoclass(
                "com.google.android.gms.common.GoogleApiAvailability"
            )

            result = Availability.getInstance().isGooglePlayServicesAvailable(
                service
            )

            if result != 0:
                print("[tracker] Google Play Services tidak tersedia:", result)
                return None

            LocationServices = autoclass(
                "com.google.android.gms.location.LocationServices"
            )

            Builder = autoclass(
                "com.google.android.gms.location.LocationRequest$Builder"
            )

            # PRIORITY_HIGH_ACCURACY = 100
            request = (
                Builder(100, GPS_INTERVAL_MS)
                .setMinUpdateIntervalMillis(GPS_INTERVAL_MS // 2)
                .build()
            )

            client = LocationServices.getFusedLocationProviderClient(service)

            return client, request

        except Exception as e:
            print("[tracker] Fused Location tidak tersedia:", e)
            return None

    fused = make_fused()

    def register_location_manager():
        try:
            with registration_lock:
                if stop.is_set():
                    return False

                try:
                    lm.removeUpdates(listener)
                except Exception:
                    pass

                lm.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    GPS_INTERVAL_MS,
                    0.0,
                    listener,
                    looper
                )

                state["backend"] = "location_manager"
                state["registered_at"] = time.time()

                print("[tracker] menggunakan LocationManager GPS")
                return True

        except Exception as e:
            print("[tracker] LocationManager gagal:", e)
            state["last_error"] = str(e)
            return False

    def unregister():
        with registration_lock:
            if fused:
                try:
                    fused[0].removeLocationUpdates(listener)
                except Exception as e:
                    print("[tracker] hapus Fused gagal:", e)

            try:
                lm.removeUpdates(listener)
            except Exception as e:
                print("[tracker] hapus LocationManager gagal:", e)

            state["backend"] = None

    def register():
        if stop.is_set():
            return False

        if fused and not state["fused_broken"]:
            try:
                with registration_lock:
                    if stop.is_set():
                        return False

                    fused[0].requestLocationUpdates(
                        fused[1],
                        listener,
                        looper
                    ).addOnSuccessListener(fused_success).addOnFailureListener(
                        fused_failure
                    )

                    state["backend"] = "fused"
                    state["registered_at"] = time.time()
                    state["last_error"] = None

                    print("[tracker] meminta registrasi Fused Location")
                    return True

            except Exception as e:
                print("[tracker] registrasi Fused gagal:", e)
                state["last_error"] = str(e)
                state["fused_broken"] = True

        return register_location_manager()

    def watchdog():
        while not stop.wait(5):
            if need_restart.is_set():
                need_restart.clear()

                print("[tracker] watchdog: permintaan restart")
                unregister()
                register()
                continue

            registered_at = state["registered_at"]

            if registered_at <= 0:
                continue

            now = time.time()
            last_fix = pipe.last_fix

            if last_fix >= registered_at:
                # Sudah pernah dapat fix sejak registrasi terakhir.
                ref, limit = last_fix, WATCHDOG_STALE
            else:
                # Belum ada fix sejak registrasi: beri waktu lebih lama.
                ref, limit = registered_at, WATCHDOG_FIRST_FIX

            if now - ref > limit:
                print(
                    "[tracker] watchdog: GPS tidak menerima fix valid "
                    f"selama {int(now - ref)} detik"
                )

                unregister()
                register()

    try:
        if not register():
            print(
                "[tracker] registrasi GPS gagal. "
                "Periksa izin lokasi dan pengaturan lokasi perangkat."
            )
            return

        threading.Thread(
            target=watchdog,
            daemon=True,
            name="GPS-Watchdog"
        ).start()

        print("[tracker] service GPS berjalan")
        Looper.loop()

    except Exception as e:
        print("[tracker] Android runner error:", e)

    finally:
        stop.set()
        need_restart.set()

        unregister()

        if wake is not None:
            try:
                if wake.isHeld():
                    wake.release()
            except Exception:
                pass

        print("[tracker] service GPS dihentikan")


def watch_parent():
    try:
        sys.stdin.buffer.read()
    except Exception:
        pass

    os._exit(0)


def run_desktop():
    import random

    if "--watch-parent" in sys.argv:
        threading.Thread(
            target=watch_parent,
            daemon=True
        ).start()

    print("[tracker] bukan Android, simulasi jalan kaki")

    pipe = Pipeline()

    lat, lon = -6.9175, 107.6191
    step = 0

    while True:
        step += 1
        lat += 0.000012
        lon += 0.000015 * math.sin(step / 8.0)

        if step % 60 == 30:
            print("[tracker] simulasi: berdiri diam 15 detik")

            for _ in range(15):
                pipe.feed(
                    lat + random.gauss(0, 0.000008),
                    lon + random.gauss(0, 0.000008),
                    8.0,
                    time.time()
                )

                time.sleep(1)

        if step % 60 == 0:
            print("[tracker] simulasi: sinyal hilang 20 detik + pindah jauh")

            time.sleep(20)
            lat += 0.05

        pipe.feed(
            lat + random.gauss(0, 0.000008),
            lon + random.gauss(0, 0.000008),
            8.0,
            time.time()
        )

        time.sleep(1)


if __name__ == "__main__":
    try:
        import jnius
    except ImportError:
        run_desktop()
    else:
        run_android()