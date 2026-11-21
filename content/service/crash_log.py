import os
import re
import time

MAX_CHARS = 200000
MAX_SHARE_CHARS = 100000


def file_path():
    base = os.environ.get("ANDROID_PRIVATE") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(base, "crash.log")


def read():
    try:
        with open(file_path(), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def append(text):
    entry = "===== {} =====\n{}\n\n".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), str(text).rstrip()
    )
    data = (read() + entry)[-MAX_CHARS:]

    if not data.startswith("===== "):
        cut = data.find("\n===== ")
        data = data[cut + 1:] if cut != -1 else entry

    try:
        with open(file_path(), "w", encoding="utf-8") as f:
            f.write(data)
    except Exception:
        pass


def read_entries():
    parts = re.split(r"(?m)^(?=[=]{5} )", read())
    return [p.strip("\n") for p in parts if p.strip()]


def clear():
    try:
        os.remove(file_path())
    except Exception:
        pass


def copy_text(text):
    try:
        from kivy.core.clipboard import Clipboard

        Clipboard.copy(text)
        return True
    except Exception:
        return False


def share_text(text):
    try:
        from kivy.utils import platform

        if platform != "android":
            return False

        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        String = autoclass("java.lang.String")

        intent = Intent()
        intent.setAction(Intent.ACTION_SEND)
        intent.putExtra(Intent.EXTRA_SUBJECT, String("Crash log JAGJAG"))
        intent.putExtra(Intent.EXTRA_TEXT, String(text[-MAX_SHARE_CHARS:]))
        intent.setType("text/plain")

        chooser = Intent.createChooser(intent, String("Kirim crash log"))
        PythonActivity.mActivity.startActivity(chooser)
        return True
    except Exception as e:
        print("[crash_log] share gagal:", e)
        return False