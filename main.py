"""Entry point.

python main.py            desktop GUI (Tkinter + VLC)
python main.py --cli      console mode
python main.py --mobile   Kivy UI (the one that runs on Android) on the desktop

On Android (inside the APK) the Kivy UI starts automatically.
"""
import os
import sys


def main() -> None:
    args = sys.argv[1:]
    if "ANDROID_ARGUMENT" in os.environ or "--mobile" in args:
        # Kivy parses sys.argv on import and rejects unknown flags like --mobile
        os.environ.setdefault("KIVY_NO_ARGS", "1")
        from radio.kivy_app import main as run
    elif "--cli" in args:
        from radio.cli import main as run
    else:
        from radio.gui import main as run
    run()


if __name__ == "__main__":
    main()
