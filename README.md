# Интернет-радио на Python

Простой плеер интернет-радио: графический интерфейс на Tkinter, воспроизведение через libVLC.

## Требования

* Python 3.10+
* Установленный [VLC media player](https://www.videolan.org/) (используется его библиотека `libvlc`)
* `pip install -r requirements.txt`

## Запуск

```bash
python main.py            # графический интерфейс (Tkinter)
python main.py --cli      # консольный режим
python main.py --mobile   # мобильный интерфейс (Kivy) на компьютере, для отладки
```

## Возможности

* Список станций в `stations.json` (редактируется вручную или кнопками «Добавить»/«Удалить»)
* Двойной клик или Enter по станции — играть
* Регулировка громкости
* Показ названия текущего трека, если станция передаёт ICY-метаданные
* Поиск станций по каталогу [radio-browser.info](https://www.radio-browser.info): кнопка «Поиск»,
  найденную станцию можно сразу прослушать или добавить в свой список

## Консольный режим

```
7            играть станцию № 7 из списка
l            показать список
s            стоп
v 50         громкость 50
f jazz       искать «jazz» в radio-browser.info
p 3          слушать результат поиска № 3
a 3          добавить результат № 3 в stations.json
q            выход
```

## Android

Мобильная версия написана на Kivy ([radio/kivy_app.py](radio/kivy_app.py)) и играет звук
через системный `android.media.MediaPlayer` ([radio/android_player.py](radio/android_player.py)).
Интерфейс тот же: список станций, поиск по radio-browser.info, громкость, удаление станций.
Воспроизведение продолжается при выключенном экране.

Ограничение: системный плеер Android не отдаёт название текущего трека (ICY-метаданные),
поэтому на телефоне эта строка не показывается.

### Сборка APK

Buildozer работает только в Linux, поэтому есть два пути.

**1. GitHub Actions (проще всего).** Залейте проект в репозиторий на GitHub, workflow
[.github/workflows/build-android.yml](.github/workflows/build-android.yml) соберёт APK при каждом
пуше. Готовый файл лежит во вкладке Actions → запуск → Artifacts → `internet-radio-apk`.

**2. Локально в WSL2 (Ubuntu).**

```bash
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip     autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5     cmake libffi-dev libssl-dev build-essential
pip3 install --user buildozer cython==0.29.36
cd /mnt/d/prj_internet_radio
buildozer android debug
```

Первая сборка качает Android SDK/NDK (несколько гигабайт) и занимает 20–40 минут,
следующие сборки идут быстрее. APK появится в папке `bin/`.

### Установка на телефон

Скопируйте APK на телефон и откройте его, разрешив установку из неизвестных источников.
Либо через adb: `adb install bin/internetradio-1.0-arm64-v8a_armeabi-v7a-debug.apk`.
Параметры сборки (имя пакета, версия, разрешения) — в [buildozer.spec](buildozer.spec).

## Где брать URL станций

Проще всего через встроенный поиск. Если добавляете вручную, нужна прямая ссылка
на аудиопоток (mp3/aac/m3u8), например с https://somafm.com.

## Структура

```
main.py             точка входа
stations.json       список станций
radio/player.py     обёртка над VLC
radio/gui.py        Tkinter-интерфейс
radio/cli.py        консольный режим
radio/stations.py   загрузка/сохранение списка
radio/browser.py    запросы к API radio-browser.info
radio/search_dialog.py  окно поиска (Tkinter)
radio/kivy_app.py   мобильный интерфейс (Kivy)
radio/android_player.py  плеер через Android MediaPlayer
buildozer.spec      настройки сборки APK
```

Для мобильного интерфейса на компьютере нужен Kivy: `pip install "kivy[base]"`.
