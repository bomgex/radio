[app]
title = Internet Radio
package.name = internetradio
package.domain = org.pyotr
version = 1.0

source.dir = .
source.include_exts = py,json
source.exclude_dirs = .github, .buildozer, bin, __pycache__, .git
# Desktop-only modules (Tkinter, VLC) are not needed in the APK
source.exclude_patterns = radio/gui.py, radio/search_dialog.py, radio/cli.py, radio/player.py

# certifi: CA bundle for HTTPS requests (the bundled Python cannot use the
# Android system certificate store)
requirements = python3,kivy==2.3.1,pyjnius,certifi

# python-for-android "master" (= release 2026.05.09) breaks at the package
# install stage: "pip install -U pip" inside the Python 3.14 build venv fails with
# ImportError: cannot import name 'BuildDependencyInstallError'.
# The fix (kivy/python-for-android#3360) is only on the develop branch.
p4a.branch = develop
p4a.commit = e772ad93f20a
orientation = portrait
fullscreen = 0

android.permissions = INTERNET, WAKE_LOCK
android.api = 34
android.minapi = 24
# p4a develop recommends NDK 28c; its libthorvg recipe expects the r26+ layout
# (lib/clang/*/lib/linux) and fails on r25b with IndexError in glob()
android.ndk = 28c
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
# keep the CPU awake so the stream does not stop when the screen turns off
android.wakelock = True
# many radio streams are plain http; Android blocks cleartext by default.
# This option takes a path to a file whose contents are inserted as attributes
# of the <application> element.
android.extra_manifest_application_arguments = android_manifest_application_args.txt
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
