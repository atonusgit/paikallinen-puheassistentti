"""
VoxCPM2 testiskripti - Text-to-Speech
Tukee: CUDA, MPS (Apple Silicon), CPU
"""

import sys
import time
import torch
import soundfile as sf
from voxcpm import VoxCPM

def get_device():
    """Valitse paras saatavilla oleva laite."""
    if torch.cuda.is_available():
        print(f"Kaytossa: CUDA ({torch.cuda.get_device_name(0)})")
        return "cuda"
    elif torch.backends.mps.is_available():
        print("Kaytossa: MPS (Apple Metal GPU)")
        return "mps"
    else:
        print("Kaytossa: CPU (hidas)")
        return "cpu"


def main():
    device = get_device()
    print(f"\nLadataan VoxCPM2-mallia ({device})...")

    start = time.time()
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=True)
    print(f"Malli ladattu ({time.time() - start:.1f}s)")

    # --- Testi 1: Perus TTS (englanti) ---
    print("\n--- Testi 1: Englanti ---")
    start = time.time()
    wav = model.generate(
        text="Hello! This is a test of the VoxCPM2 text to speech model.",
        cfg_value=2.0,
        inference_timesteps=10,
    )
    sf.write("output_english.wav", wav, model.tts_model.sample_rate)
    print(f"Tallennettu: output_english.wav ({time.time() - start:.1f}s)")

    # --- Testi 2: Suomi ---
    print("\n--- Testi 2: Suomi ---")
    start = time.time()
    wav = model.generate(
        text="Hei! Tama on testi. VoxCPM2 tukee kolmeakymmentä kieltä mukaan lukien suomea.",
        cfg_value=2.0,
        inference_timesteps=10,
    )
    sf.write("output_suomi.wav", wav, model.tts_model.sample_rate)
    print(f"Tallennettu: output_suomi.wav ({time.time() - start:.1f}s)")

    # --- Testi 3: Voice Design ---
    print("\n--- Testi 3: Voice Design (aanisuunnittelu) ---")
    start = time.time()
    wav = model.generate(
        text="(A deep, warm male voice)Welcome to the future of speech synthesis.",
        cfg_value=2.0,
        inference_timesteps=10,
    )
    sf.write("output_voice_design.wav", wav, model.tts_model.sample_rate)
    print(f"Tallennettu: output_voice_design.wav ({time.time() - start:.1f}s)")

    print("\n=== Kaikki testit valmis! ===")
    print(f"Naytteenottotaajuus: {model.tts_model.sample_rate} Hz")


if __name__ == "__main__":
    main()
