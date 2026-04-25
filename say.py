"""
Nopea TTS: kirjoita teksti, VoxCPM2 puhuu sen.
Ei LLM:ää, ei keskustelua — pelkkä puhesynteesi.

Malli ladataan taustalla samalla kun käyttäjä kirjoittaa tekstiä.

Käyttö:
  python say.py --pick                        # valitse aani listalta
  python say.py --ref anton.wav "Hei maailma"
  python say.py --voice "A deep male voice" "Hello world"
"""

import argparse
import json
import os
import platform
import readline
import socket
import subprocess
import sys
import threading

os.environ["TQDM_DISABLE"] = "1"

import soundfile as sf
from voxcpm import VoxCPM
from voice_picker import resolve_ref

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
SOCKET_PATH = os.path.join(SCRIPT_DIR, ".sayd.sock")
SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
CLEAR_LINE = "\033[2K\r"


def play_audio(filepath):
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["afplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif system == "Linux":
        subprocess.run(["aplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def load_model():
    tts = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    return tts


def say_palvelimella(text, args, ref_path):
    """Lähetä pyyntö sayd-palvelimelle. Palauttaa True jos onnistui."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCKET_PATH)
            req = {
                "text": text,
                "ref": ref_path,
                "voice": args.voice,
                "output": args.output,
            }
            s.sendall((json.dumps(req) + "\n").encode("utf-8"))
            data = bytearray()
            while b"\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data.extend(chunk)
        rivi, _, _ = bytes(data).partition(b"\n")
        resp = json.loads(rivi.decode("utf-8").strip())
        if resp.get("ok"):
            print(f"Tallennettu: {resp['outfile']}")
            return True
        print(f"Palvelinvirhe: {resp.get('error')}", file=sys.stderr)
        return False
    except (OSError, json.JSONDecodeError) as e:
        print(f"Pistokevirhe: {e}", file=sys.stderr)
        return False


def run_with_server(args, ref_path):
    """Interaktiivinen tai yksittäinen ajo palvelimen kautta."""
    if args.text:
        ok = say_palvelimella(args.text, args, ref_path)
        sys.exit(0 if ok else 1)
    while True:
        try:
            text = input("Mitä sanon? ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nMoi!")
            return
        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            print("Moi!")
            return
        say_palvelimella(text, args, ref_path)


def main():
    parser = argparse.ArgumentParser(description="VoxCPM2 puhu teksti")
    parser.add_argument("text", nargs="?", help="Teksti joka puhutaan")
    parser.add_argument("--ref", default=None, help="Referenssi-wav tiedostonimi")
    parser.add_argument("--pick", action="store_true", help="Valitse ääni voices-kansiosta")
    parser.add_argument("--voice", default=None, help="Äänikuvaus")
    parser.add_argument("-o", "--output", default=None, help="Tallenna tiedostoon")
    args = parser.parse_args()

    # Valitse aani
    ref_path = resolve_ref(args.ref, pick=args.pick)

    # Jos sayd-palvelin on käynnissä, käytä sitä
    if os.path.exists(SOCKET_PATH):
        return run_with_server(args, ref_path)

    # Käynnistä mallin lataus heti taustalle
    model_result = [None]
    model_ready = threading.Event()

    def bg_load():
        model_result[0] = load_model()
        model_ready.set()

    loader = threading.Thread(target=bg_load, daemon=True)
    loader.start()

    # Näytä latausspinner kunnes malli valmis tai käyttäjä kirjoittaa
    def show_loading():
        i = 0
        while not model_ready.is_set():
            print(f"{CLEAR_LINE}{SPINNER[i % len(SPINNER)]} Ladataan VoxCPM2...", end="", flush=True)
            model_ready.wait(timeout=0.15)
            i += 1
        print(f"{CLEAR_LINE}", end="", flush=True)

    # Jos teksti annettiin argumenttina, odota malli ja sano
    first_text = args.text

    if first_text:
        show_loading()
        loader.join()

    one_shot = bool(first_text)

    while True:
        if first_text:
            text = first_text
            first_text = None
        else:
            if not model_ready.is_set():
                spinner_thread = threading.Thread(target=show_loading, daemon=True)
                spinner_thread.start()
                spinner_thread.join()
            try:
                text = input("Mitä sanon? ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nMoi!")
                break
            if not text:
                continue
            if text.lower() in ("quit", "exit", "q"):
                print("Moi!")
                break

        loader.join()
        tts = model_result[0]
        sample_rate = tts.tts_model.sample_rate

        kwargs = dict(text=text, cfg_value=2.0, inference_timesteps=10)
        if ref_path:
            kwargs["reference_wav_path"] = ref_path
        elif args.voice:
            kwargs["text"] = f"({args.voice}){text}"

        print(f"{CLEAR_LINE}{SPINNER[0]} Generoidaan...", end="", flush=True)
        wav = tts.generate(**kwargs)
        print(f"{CLEAR_LINE}OK", flush=True)

        if args.output:
            outfile = args.output
        else:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            voice_name = os.path.splitext(os.path.basename(ref_path))[0] if ref_path else "say"
            i = 1
            while True:
                outfile = os.path.join(OUTPUT_DIR, f"{voice_name}_{i:03d}.wav")
                if not os.path.exists(outfile):
                    break
                i += 1
        sf.write(outfile, wav, sample_rate)
        print(f"Tallennettu: {outfile}")
        play_audio(outfile)

        if one_shot:
            break


if __name__ == "__main__":
    main()
