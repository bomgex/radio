# Internet Radio in Python

A simple internet radio player: a Tkinter desktop GUI, a console mode and a Kivy
Android app. Desktop playback goes through libVLC, Android playback through the
system `MediaPlayer`.

## Requirements (desktop)

* Python 3.10+
* [VLC media player](https://www.videolan.org/) installed (its `libvlc` library is used)
* `pip install -r requirements.txt`

## Running

```bash
python main.py            # desktop GUI (Tkinter)
python main.py --cli      # console mode
python main.py --mobile   # the Kivy UI (the one that runs on Android) on the desktop
```

The mobile UI on the desktop needs Kivy: `pip install "kivy[base]"`.

## Features

* Station list in `stations.json` (edit by hand or with the Add / Remove buttons)
* Double-click or Enter on a station to play it
* Volume control
* Current track title when the station sends ICY metadata
* Automatic reconnection when a stream drops (growing delay: 2, 4, 8, 15, 30 s)
* Station search in the [radio-browser.info](https://www.radio-browser.info) catalog:
  the Search button; a found station can be previewed or added to your list

## Console mode

```
7            play station no. 7 from the list
l            show the list
s            stop
v 50         volume 50
f jazz       search "jazz" on radio-browser.info
p 3          play search result no. 3
a 3          add search result no. 3 to stations.json
q            quit
```

## Android

The mobile version is written in Kivy ([radio/kivy_app.py](radio/kivy_app.py)) and plays
audio through the system `android.media.MediaPlayer`
([radio/android_player.py](radio/android_player.py)). Same features: station list,
radio-browser.info search, volume, removing stations. Playback continues with the screen off.

Limitation: the Android system player does not expose ICY stream titles, so the
current-track line is not shown on the phone.

### Building the APK

Buildozer runs only on Linux, so there are two options.

**1. GitHub Actions (easiest).** Push the project to a GitHub repository; the workflow in
[.github/workflows/build-android.yml](.github/workflows/build-android.yml) builds the APK on
every push. The file is available under Actions → the run → Artifacts → `internet-radio-apk`.

**2. Locally in WSL2 (Ubuntu).**

```bash
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libssl-dev build-essential
pip3 install --user buildozer cython==0.29.36
cd /mnt/d/prj_internet_radio
buildozer android debug
```

The first build downloads the Android SDK/NDK (several gigabytes) and takes 20–40 minutes;
later builds are faster. The APK appears in the `bin/` folder.

### Installing on the phone

Copy the APK to the phone and open it, allowing installation from unknown sources.
Or via adb: `adb install bin/internetradio-1.0-arm64-v8a_armeabi-v7a-debug.apk`.
Build settings (package name, version, permissions) live in [buildozer.spec](buildozer.spec).

## Where to get stream URLs

The built-in search is the easiest way. When adding by hand you need a direct link to an
audio stream (mp3/aac/m3u8), for example from https://somafm.com.

## Layout

```
main.py                  entry point
stations.json            station list
radio/player.py          VLC wrapper (desktop)
radio/gui.py             Tkinter UI
radio/search_dialog.py   search window (Tkinter)
radio/cli.py             console mode
radio/stations.py        loading / saving the list
radio/browser.py         radio-browser.info API client
radio/kivy_app.py        mobile UI (Kivy)
radio/android_player.py  player via Android MediaPlayer
buildozer.spec           APK build settings
```
