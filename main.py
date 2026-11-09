#!/usr/bin/env python3
"""Entry point.

python3 main.py          -> graphical window (pygame), F11 for fullscreen
python3 main.py --text   -> terminal version, no dependencies
"""
import sys


def main():
    if "--text" in sys.argv:
        from engine.game import main as text_main
        text_main()
    else:
        from ui.app import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
