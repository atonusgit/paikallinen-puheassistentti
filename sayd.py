"""
VoxCPM2-palvelin (daemon).

Lataa mallin kerran, kuuntelee Unix-pistokkeessa ./.sayd.sock ja
generoi+soittaa wav-tiedostot saapuvien JSON-pyyntöjen mukaan.

Pyynnön muoto (yksi rivi, päättyy '\\n'):
  {"text": "...", "ref": "anton.wav"|null, "voice": "..."|null, "output": "polku"|null}

Vastauksen muoto:
  {"ok": true,  "outfile": "polku"}
  {"ok": false, "error": "viesti"}
"""

import json
import os
import platform
import signal
import socket
import subprocess
import sys
import threading

os.environ["TQDM_DISABLE"] = "1"

import soundfile as sf
from voxcpm import VoxCPM
from voice_picker import resolve_ref

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOCKET_PATH = os.path.join(SCRIPT_DIR, ".sayd.sock")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

_generate_lock = threading.Lock()


def play_audio(filepath):
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["afplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif system == "Linux":
        subprocess.run(["aplay", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def valitse_outfile(ref_path, output):
    if output:
        return output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    voice_name = os.path.splitext(os.path.basename(ref_path))[0] if ref_path else "say"
    i = 1
    while True:
        outfile = os.path.join(OUTPUT_DIR, f"{voice_name}_{i:03d}.wav")
        if not os.path.exists(outfile):
            return outfile
        i += 1


def generoi(tts, req):
    text = req.get("text") or ""
    if not text.strip():
        raise ValueError("Tyhjä teksti")

    ref_arg = req.get("ref")
    voice = req.get("voice")
    output = req.get("output")

    ref_path = resolve_ref(ref_arg, pick=False) if ref_arg else None
    sample_rate = tts.tts_model.sample_rate

    kwargs = dict(text=text, cfg_value=2.0, inference_timesteps=10)
    if ref_path:
        kwargs["reference_wav_path"] = ref_path
    elif voice:
        kwargs["text"] = f"({voice}){text}"

    wav = tts.generate(**kwargs)
    outfile = valitse_outfile(ref_path, output)
    sf.write(outfile, wav, sample_rate)
    play_audio(outfile)
    return outfile


def lue_rivi(client):
    data = bytearray()
    while b"\n" not in data:
        chunk = client.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
    rivi, _, _ = bytes(data).partition(b"\n")
    return rivi.decode("utf-8").strip()


def kasittele(client, tts):
    try:
        rivi = lue_rivi(client)
        if not rivi:
            return
        req = json.loads(rivi)
        with _generate_lock:
            outfile = generoi(tts, req)
        vastaus = {"ok": True, "outfile": outfile}
    except Exception as e:
        vastaus = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        client.sendall((json.dumps(vastaus) + "\n").encode("utf-8"))
    except OSError:
        pass
    finally:
        client.close()


def siivoa_pistoke():
    try:
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
    except OSError:
        pass


def main():
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    print("Ladataan VoxCPM2...", flush=True)
    tts = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    print(f"Valmis. Kuunnellaan {SOCKET_PATH}", flush=True)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)
    sock.listen(8)

    def sammuta(*_):
        try:
            sock.close()
        except OSError:
            pass
        siivoa_pistoke()
        sys.exit(0)

    signal.signal(signal.SIGTERM, sammuta)
    signal.signal(signal.SIGINT, sammuta)

    try:
        while True:
            try:
                client, _ = sock.accept()
            except OSError:
                break
            threading.Thread(target=kasittele, args=(client, tts), daemon=True).start()
    finally:
        siivoa_pistoke()


if __name__ == "__main__":
    main()
