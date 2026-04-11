"""Yhteinen apumoduuli aanivalintaan voices-kansiosta."""

import glob
import os
import sys
import tty
import termios

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(SCRIPT_DIR, "voices")


def _read_key():
    """Lue yksi nappainpainallus (tukee nuolinappaimia)."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return None
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            return "quit"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _render(names, selected):
    """Piirra valintamenu."""
    # Siirry ylös ja tyhjenna edelliset rivit
    sys.stdout.write(f"\x1b[{len(names) + 1}A")
    sys.stdout.write("\x1b[2KValitse aani:\n")
    for i, name in enumerate(names):
        if i == selected:
            sys.stdout.write(f"\x1b[2K  \x1b[7m > {name}\x1b[0m\n")
        else:
            sys.stdout.write(f"\x1b[2K    {name}\n")
    sys.stdout.flush()


def pick_voice():
    """Listaa voices-kansion wav-tiedostot ja anna kayttajan valita
    nuolinappaimilla. Palauttaa absoluuttisen polun tai None."""
    os.makedirs(VOICES_DIR, exist_ok=True)
    wavs = sorted(glob.glob(os.path.join(VOICES_DIR, "*.wav")))

    if not wavs:
        print("Ei aanitiedostoja. Nauhoita ensin: python record_voice.py")
        return None

    if len(wavs) == 1:
        name = os.path.basename(wavs[0])
        print(f"Aani: {name}")
        return wavs[0]

    names = [os.path.basename(w) for w in wavs]
    selected = 0

    # Piirra ensimmainen kerta
    print("Valitse aani:")
    for i, name in enumerate(names):
        if i == selected:
            print(f"  \x1b[7m > {name}\x1b[0m")
        else:
            print(f"    {name}")

    while True:
        key = _read_key()
        if key == "up":
            selected = (selected - 1) % len(wavs)
            _render(names, selected)
        elif key == "down":
            selected = (selected + 1) % len(wavs)
            _render(names, selected)
        elif key == "enter":
            # Tyhjenna invertointi ja tulosta valinta
            _render(names, selected)
            print(f"\nValittu: {names[selected]}")
            return wavs[selected]
        elif key == "quit":
            print()
            return None


def resolve_ref(ref_arg, pick=False):
    """Resolvoi referenssi-aanen polku."""
    if ref_arg:
        if os.path.isabs(ref_arg):
            return ref_arg
        return os.path.join(VOICES_DIR, ref_arg)

    if pick:
        return pick_voice()

    return None
