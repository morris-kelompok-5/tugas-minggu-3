from collections import deque

from kivy.clock import Clock
from kivy.utils import platform


class AlarmManager:
    GAP = 0.8

    _queue = deque()
    _event = None

    @staticmethod
    def label(name, hhmm):
        return f"Waktunya makan: {name} ({hhmm})"

    @classmethod
    def schedule(cls, name, times):
        return cls._enqueue([("set", name, t) for t in times])

    @classmethod
    def cancel(cls, name, times):
        return cls._enqueue([("dismiss", name, t) for t in times])

    @classmethod
    def _enqueue(cls, jobs):
        if platform != "android":
            print("[alarm] bukan Android, dilewati:", jobs)
            return False

        cls._queue.extend(jobs)
        if cls._event is None:
            cls._event = Clock.schedule_interval(cls._pump, cls.GAP)
            cls._pump(0)
        return True

    @classmethod
    def _pump(cls, dt):
        if not cls._queue:
            if cls._event:
                cls._event.cancel()
                cls._event = None
            return

        action, name, hhmm = cls._queue.popleft()
        try:
            if action == "set":
                cls._set(name, hhmm)
            else:
                cls._dismiss(name, hhmm)
        except Exception as e:
            print(f"[alarm] gagal {action} {name} {hhmm}:", e)

    @classmethod
    def _set(cls, name, hhmm):
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        AlarmClock = autoclass("android.provider.AlarmClock")
        ArrayList = autoclass("java.util.ArrayList")
        Integer = autoclass("java.lang.Integer")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity

        hour, minute = map(int, hhmm.split(":"))
        days = ArrayList()
        for d in range(1, 8):
            days.add(Integer(d))

        intent = Intent(AlarmClock.ACTION_SET_ALARM)
        intent.putExtra(AlarmClock.EXTRA_HOUR, hour)
        intent.putExtra(AlarmClock.EXTRA_MINUTES, minute)
        intent.putExtra(AlarmClock.EXTRA_MESSAGE, cls.label(name, hhmm))
        intent.putExtra(AlarmClock.EXTRA_SKIP_UI, True)
        intent.putIntegerArrayListExtra(AlarmClock.EXTRA_DAYS, days)
        activity.startActivity(intent)

    @classmethod
    def _dismiss(cls, name, hhmm):
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        AlarmClock = autoclass("android.provider.AlarmClock")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity

        intent = Intent(AlarmClock.ACTION_DISMISS_ALARM)
        intent.putExtra(AlarmClock.EXTRA_ALARM_SEARCH_MODE,
                        AlarmClock.ALARM_SEARCH_MODE_LABEL)
        intent.putExtra(AlarmClock.EXTRA_MESSAGE, cls.label(name, hhmm))
        activity.startActivity(intent)