import math
from kivy.utils import platform

_heading = None   # derajat, 0 = utara, searah jarum jam
_manager = None
_listener = None
_sensor = None

if platform == "android":
    from jnius import autoclass, cast, PythonJavaClass, java_method

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android/hardware/SensorEventListener"]
        __javacontext__ = "app"

        @java_method("(Landroid/hardware/SensorEvent;)V")
        def onSensorChanged(self, event):
            global _heading
            v = list(event.values)
            if len(v) < 3:
                return
            x, y, z = v[0], v[1], v[2]
            w = v[3] if len(v) > 3 else math.sqrt(max(0.0, 1 - x*x - y*y - z*z))

            # elemen matriks rotasi dari quaternion -> azimuth (ponsel datar)
            r1 = 2 * (x * y - z * w)
            r4 = 1 - 2 * (x * x + z * z)
            az = math.degrees(math.atan2(r1, r4)) % 360

            if _heading is None:
                _heading = az
            else:
                # low-pass filter melingkar (hindari lompatan 359 -> 0)
                d = (az - _heading + 540) % 360 - 180
                _heading = (_heading + 0.15 * d) % 360

        @java_method("(Landroid/hardware/Sensor;I)V")
        def onAccuracyChanged(self, sensor, accuracy):
            pass


class CompassManager:
    @staticmethod
    def start():
        global _manager, _listener, _sensor
        if platform != "android" or _listener is not None:
            return
        try:
            Context = autoclass("android.content.Context")
            Sensor = autoclass("android.hardware.Sensor")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            _manager = cast("android.hardware.SensorManager",
                            activity.getSystemService(Context.SENSOR_SERVICE))
            _sensor = _manager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
            if _sensor is None:
                print("[compass] sensor tidak tersedia")
                return
            _listener = _Listener()
            _manager.registerListener(_listener, _sensor, 60000)  # ~60 ms
        except Exception as e:
            print("[compass] gagal start:", e)
            _listener = None

    @staticmethod
    def stop():
        global _listener, _heading
        try:
            if _manager and _listener:
                _manager.unregisterListener(_listener)
        except Exception as e:
            print("[compass] gagal stop:", e)
        _listener = None
        _heading = None

    @staticmethod
    def heading():
        return _heading

    @staticmethod
    def label(h):
        if h is None:
            return ""
        arah = ["U", "TL", "T", "TG", "S", "BD", "B", "BL"]
        return f"{arah[int((h + 22.5) // 45) % 8]} {int(h)}°"