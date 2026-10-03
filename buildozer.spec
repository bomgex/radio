[app]
title = Интернет-радио
package.name = internetradio
package.domain = org.pyotr
version = 1.0

source.dir = .
source.include_exts = py,json
source.exclude_dirs = .github, .buildozer, bin, __pycache__, .git
# Desktop-only modules (Tkinter, VLC) are not needed in the APK
source.exclude_patterns = radio/gui.py, radio/search_dialog.py, radio/cli.py, radio/player.py

requirements = python3,kivy==2.3.1,pyjnius
orientation = portrait
fullscreen = 0

android.permissions = INTERNET, WAKE_LOCK
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
# keep the CPU awake so the stream does not stop when the screen turns off
android.wakelock = True
# many radio streams are plain http; Android blocks cleartext by default
android.extra_manifest_application_arguments = android:usesCleartextTraffic="true"
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
