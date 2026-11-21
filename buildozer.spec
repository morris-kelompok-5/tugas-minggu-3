[app]
title = JAGJAG
package.name = jagjag
package.domain = org.isekairid

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,otf,ttf
source.exclude_dirs = .venv,.git,.github,bin,.buildozer,__pycache__,tests,platform-tools

version = 0.1

# Python dikunci ke 3.11.x (hostpython3 dan python3 harus versi yang sama).
# urllib3, idna, charset-normalizer, certifi wajib ada karena dipakai requests
# (dan requests dipakai kivy-garden.mapview saat import).
requirements = hostpython3==3.11.5,python3==3.11.5,kivy==2.3.1,kivymd==2.0.0,materialyoucolor==3.0.4,materialshapes,asynckivy,asyncgui,exceptiongroup,pillow,kivy-garden.mapview,requests,urllib3,idna,charset-normalizer,certifi,pyjnius,android

# foreground + sticky: service dihidupkan ulang OS kalau di-kill
services = tracker:content/service/tracker.py:foreground:sticky:foregroundServiceType=location

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/assets/icon/icon.png
presplash.filename = %(source.dir)s/assets/img/presplash.jpg
android.presplash_color = #FFFFFF

# Versi python-for-android yang dikunci
p4a.branch = v2026.05.09

android.gradle_dependencies = com.google.android.gms:play-services-location:21.3.0
android.enable_androidx = True

# Kalau masih crash setelah semua fix lain, coba turunkan android.api ke 35
android.api = 36
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True

android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,POST_NOTIFICATIONS,WAKE_LOCK,com.android.alarm.permission.SET_ALARM
android.extra_manifest_application_arguments = %(source.dir)s/extra_manifest_application_arguments.xml

android.manifest.launch_mode = singleTask
android.allow_backup = False

# Filter logcat: jalankan "buildozer android logcat" untuk lihat log Python saja
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 0