"""
Voice Assistant: Ollama LLM + VoxCPM2 TTS (fully pipelined)

Kolmivaiheinen putki jossa kaikki tapahtuu rinnakkain:
  1. LLM-säie:   striimataan tokeneita, pilkotaan lauseisiin -> tts_queue
  2. TTS-säie:   generoidaan puhetta lauseista          -> play_queue
  3. Play-säie:  toistetaan valmiita äänipätkiä

Kaikki kolme vaihetta pyörivät samanaikaisesti.

Käyttö:
  python voice_assistant.py --model gemma4 --lang fi
  python voice_assistant.py --model gemma4 --ref oma_aani.wav --lang fi
  python voice_assistant.py --model gemma4 --voice "A calm female voice"
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import queue

# Hiljennetaan tqdm-palkit ennen importteja
os.environ["TQDM_DISABLE"] = "1"

import numpy as np
import requests
import soundfile as sf
from voxcpm import VoxCPM
from voice_picker import resolve_ref

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(SCRIPT_DIR, "voices")
OLLAMA_URL = "http://localhost:11434"
SENTENCE_ENDINGS = re.compile(r'(?<=[.!?;:–—])\s+|(?<=\n)')
SENTINEL = None  # poison pill

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
CLEAR_LINE = "\033[2K\r"


def status_print(msg, done=False):
    """Tulosta statusviesti joka pyyhkiytyy pois kun done=True."""
    if done:
        print(f"{CLEAR_LINE}{msg}")
    else:
        print(f"{CLEAR_LINE}{msg}", end="", flush=True)


def check_ollama():
    status_print("Yhdistetään Ollamaan...")
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=60)
        r.raise_for_status()
        status_print("Ollama OK", done=True)
        return [m["name"] for m in r.json().get("models", [])]
    except requests.ConnectionError:
        pass
    except requests.ReadTimeout:
        pass

    # Käynnistä Ollama taustalle (hiljennä GIN-lokit)
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        status_print("VIRHE: Ollamaa ei löydy. Asenna: brew install ollama", done=True)
        sys.exit(1)

    # Odota että Ollama vastaa
    for i in range(60):
        time.sleep(2)
        spin = SPINNER[i % len(SPINNER)]
        status_print(f"{spin} Käynnistetään Ollamaa...")
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=30)
            r.raise_for_status()
            status_print("Ollama OK", done=True)
            return [m["name"] for m in r.json().get("models", [])]
        except (requests.ConnectionError, requests.ReadTimeout):
            continue

    status_print("VIRHE: Ollama ei vastaa. Kokeile: pkill -9 ollama && ollama serve", done=True)
    sys.exit(1)


def stream_ollama(model, messages):
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
        timeout=120,
    )
    r.raise_for_status()
    for line in r.iter_lines():
        if line:
            data = json.loads(line)
            if not data.get("done", False):
                yield data["message"]["content"]


def split_sentences(text):
    parts = SENTENCE_ENDINGS.split(text)
    return [p.strip() for p in parts if p.strip()]


def play_audio(filepath):
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["afplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif system == "Linux":
        subprocess.run(["aplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --------------- Pipeline stages ---------------

def llm_stage(model, messages, tts_queue, print_lock, llm_done_event):
    """Vaihe 1: LLM striimaa tokeneita, kokonaiset lauseet -> tts_queue."""
    buffer = ""
    full_reply = ""
    first_token = True

    for token in stream_ollama(model, messages):
        with print_lock:
            if first_token:
                print(f"{CLEAR_LINE}AI> {token}", end="", flush=True)
                first_token = False
            else:
                print(token, end="", flush=True)
        buffer += token
        full_reply += token

        sentences = split_sentences(buffer)
        if len(sentences) > 1:
            for s in sentences[:-1]:
                tts_queue.put(s)
            buffer = sentences[-1]

    # Teksti valmis — rivinvaihto ja signaali TTS-statukselle
    with print_lock:
        print()
    llm_done_event.set()

    if buffer.strip():
        tts_queue.put(buffer.strip())

    tts_queue.put(SENTINEL)
    return full_reply


def tts_stage(tts, tts_queue, play_queue, ref_wav, sample_rate, print_lock, llm_done_event):
    """Vaihe 2: Generoi puhetta lauseista -> play_queue."""
    chunk_idx = 0
    total_sentences = 0
    while True:
        sentence = tts_queue.get()
        if sentence is SENTINEL:
            play_queue.put(SENTINEL)
            if llm_done_event.is_set():
                with print_lock:
                    status_print("", done=True)
            break

        total_sentences += 1
        # Näytä TTS-status vasta kun AI-teksti on tulostettu loppuun
        if llm_done_event.is_set():
            with print_lock:
                spin = SPINNER[chunk_idx % len(SPINNER)]
                status_print(f"{spin} Puhetta generoidaan... [{chunk_idx + 1}/{total_sentences}]")

        try:
            kwargs = dict(text=sentence, cfg_value=2.0, inference_timesteps=10)
            if ref_wav:
                kwargs["reference_wav_path"] = ref_wav

            wav = tts.generate(**kwargs)
            outfile = os.path.join(tempfile.gettempdir(), f"tts_chunk_{chunk_idx:03d}.wav")
            sf.write(outfile, wav, sample_rate)
            play_queue.put(outfile)
            chunk_idx += 1
        except Exception as e:
            with print_lock:
                print(f"\n  [TTS virhe: {e}]", file=sys.stderr)
            chunk_idx += 1


def play_stage(play_queue, no_play, print_lock):
    """Vaihe 3: Toista äänipätkiä peräkkäin."""
    files_played = []
    while True:
        filepath = play_queue.get()
        if filepath is SENTINEL:
            break

        files_played.append(filepath)
        if not no_play:
            play_audio(filepath)

    return files_played


def main():
    parser = argparse.ArgumentParser(description="Voice Assistant: Ollama + VoxCPM2 (pipelined)")
    parser.add_argument("--model", default="llama3.2", help="Ollama-malli")
    parser.add_argument("--voice", default=None, help="Äänikuvaus, esim. 'A warm female voice'")
    parser.add_argument("--ref", default=None, help="Referenssi-wav äänen kloonaukseen")
    parser.add_argument("--pick", action="store_true", help="Valitse ääni voices-kansiosta")
    parser.add_argument("--lang", default="en", help="Vastauksen kieli: en, fi, jne.")
    parser.add_argument("--no-play", action="store_true", help="Älä toista ääntä automaattisesti")
    args = parser.parse_args()

    models = check_ollama()
    print(f"  Mallit: {', '.join(models)}")

    if not any(args.model in m for m in models):
        status_print(f"Ladataan mallia '{args.model}'...")
        subprocess.run(["ollama", "pull", args.model], check=True)
        status_print(f"Malli '{args.model}' ladattu", done=True)

    status_print("Ladataan VoxCPM2...")
    tts = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    sample_rate = tts.tts_model.sample_rate
    status_print(f"VoxCPM2 valmis ({sample_rate} Hz)", done=True)

    lang_instruction = {
        "fi": "Vastaa aina suomeksi. Pidä vastaukset lyhyinä ja selkeinä.",
        "en": "Keep your answers concise and clear.",
    }.get(args.lang, f"Reply in {args.lang}. Keep answers concise.")

    messages = [
        {"role": "system", "content": f"You are a helpful voice assistant. {lang_instruction}"}
    ]

    ref_wav = resolve_ref(args.ref, pick=args.pick)

    if ref_wav:
        print(f"  Referenssiääni: {ref_wav}")
    elif args.voice:
        print(f"  Luodaan referenssiääni: {args.voice}...")
        ref_audio = tts.generate(
            text=f"({args.voice})This is a warm up sentence to establish my voice.",
            cfg_value=2.0,
            inference_timesteps=10,
        )
        ref_wav = os.path.join(VOICES_DIR, "voice_reference.wav")
        sf.write(ref_wav, ref_audio, sample_rate)
        print(f"  Referenssi tallennettu: {ref_wav}")

    print("=" * 50)
    print("  Voice Assistant — PIPELINED")
    print(f"  LLM: {args.model} | Kieli: {args.lang}")
    print(f"  Ääni: {'lukittu referenssiin' if ref_wav else 'lukitaan 1. vuorolla'}")
    print()
    print("  LLM -> TTS -> Play (kaikki rinnakkain)")
    print("  Kirjoita 'quit' lopettaaksesi")
    print("=" * 50)

    turn = 0
    while True:
        try:
            user_input = input("\nSinä> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNäkemiin!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Nakemiin!")
            break

        messages.append({"role": "user", "content": user_input})

        tts_queue = queue.Queue()
        play_queue = queue.Queue()
        print_lock = threading.Lock()
        llm_done_event = threading.Event()

        t0 = time.time()
        status_print(f"{SPINNER[0]} AI miettii...")

        # Käynnistä kaikki 3 vaihetta rinnakkain
        llm_result = [None]
        play_result = [None]

        def run_llm():
            llm_result[0] = llm_stage(args.model, messages, tts_queue, print_lock, llm_done_event)

        def run_tts():
            tts_stage(tts, tts_queue, play_queue, ref_wav, sample_rate, print_lock, llm_done_event)

        def run_play():
            play_result[0] = play_stage(play_queue, args.no_play, print_lock)

        t_llm = threading.Thread(target=run_llm, daemon=True)
        t_tts = threading.Thread(target=run_tts, daemon=True)
        t_play = threading.Thread(target=run_play, daemon=True)

        t_llm.start()
        t_tts.start()
        t_play.start()

        t_llm.join()
        t_tts.join()
        t_play.join()

        elapsed = time.time() - t0
        files = play_result[0] or []
        print(f"  [{elapsed:.1f}s | {len(files)} äänipätkää]")

        if llm_result[0]:
            messages.append({"role": "assistant", "content": llm_result[0]})

        # Lukitse aani 1. vuorolla
        if turn == 0 and not ref_wav and files:
            ref_wav = os.path.join(VOICES_DIR, "voice_reference.wav")
            import shutil
            shutil.copy2(files[0], ref_wav)
            print(f"  Ääni lukittu: {ref_wav}")

        turn += 1


if __name__ == "__main__":
    main()
