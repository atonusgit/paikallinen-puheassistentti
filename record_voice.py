"""
Nauhoita oma aanesi VoxCPM2:n referenssiksi.
Kayttaa macOS:n sisaanrakennettua mikrofonia.

Kaytto:
  python record_voice.py                  # oletus 8 sekuntia
  python record_voice.py --seconds 10     # 10 sekuntia
"""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(SCRIPT_DIR, "voices")


def main():
    parser = argparse.ArgumentParser(description="Nauhoita referenssi-aani")
    parser.add_argument("--seconds", type=int, default=8, help="Nauhoituksen kesto sekunneissa")
    args = parser.parse_args()

    os.makedirs(VOICES_DIR, exist_ok=True)

    # Kysy nimi aanelle
    name = input("Anna aanelle nimi (esim. anton): ").strip().lower()
    if not name:
        print("Nimi vaaditaan.")
        sys.exit(1)
    name = name.replace(" ", "_")
    output = os.path.join(VOICES_DIR, f"{name}.wav")

    print(f"\nNauhoitetaan {args.seconds} sekuntia -> {output}")
    print("Puhu selkeasti ja tasaisesti, esim:")
    print('  "Hei, nimeni on [nimi]. Testan tekoalyn puhesynteesia omalla aanellani."')
    print()
    input("Paina Enter kun olet valmis... ")
    print(f"NAUHOITUS KAYNNISSA ({args.seconds}s)...")

    # macOS: kayta sox (rec) tai ffmpeg
    try:
        subprocess.run(
            ["rec", "-r", "16000", "-c", "1", "-b", "16", output,
             "trim", "0", str(args.seconds)],
            check=True,
        )
    except FileNotFoundError:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0",
                 "-ac", "1", "-ar", "16000", "-t", str(args.seconds),
                 output],
                check=True,
            )
        except FileNotFoundError:
            print("\nTarvitset joko sox tai ffmpeg:")
            print("  brew install sox")
            print("  tai")
            print("  brew install ffmpeg")
            sys.exit(1)

    print(f"\nTallennettu: {output}")
    print(f"\nKayta:")
    print(f"  python say.py --ref {name}.wav")
    print(f"  python voice_assistant.py --ref {name}.wav --model gemma4 --lang fi")


if __name__ == "__main__":
    main()
