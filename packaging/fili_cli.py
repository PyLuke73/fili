"""Punto d'ingresso della versione compilata (PyInstaller) della riga di comando."""
import sys

from fili.cli import main

if __name__ == "__main__":
    sys.exit(main())
