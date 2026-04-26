# Paikallinen puheassistentti

Puheassistentti, joka yhdistää paikallisen LLM:n (Ollama) ja VoxCPM2-puhesynteesimallin. Vastaukset puhutaan reaaliajassa lause kerrallaan — kaikki pyörii omalla koneella.

## Vaatimukset

- macOS (Apple Silicon)
- [Homebrew](https://brew.sh)
- [Ollama](https://ollama.com)

## Asennus

```bash
git clone git@github.com:atonusgit/paikallinen-puheassistentti.git
cd paikallinen-puheassistentti

brew install ollama sox python@3.12
ollama serve &
ollama pull gemma4

python3.12 -m venv .venv
source .venv/bin/activate
pip3 install voxcpm soundfile requests numpy
```

## Nauhoita oma ääni (kerran)

```bash
source .venv/bin/activate && python record_voice.py
```

## Käyttö

Äänen nauhoituksen jälkeen voit joko keskustella assistentin kanssa tai puhua yksittäisiä lauseita.

### Käynnistä vuoropuhelu

```bash
source .venv/bin/activate && python voice_assistant.py --pick --model gemma4 --lang fi
```

### Sano mitä kirjoitan

`say.py` on ohut HTTP-client; se vaatii että `voxcpm2_server.py` on käynnissä taustalla (lataa mallin kerran muistiin).

```bash
# Terminaali 1 — palvelin (pidä auki)
source .venv/bin/activate && python3 voxcpm2_server.py

# Terminaali 2 — client
source .venv/bin/activate && python3 say.py --pick
python3 say.py --ref anton.wav "Hei maailma"
python3 say.py --no-play -o /polku/foo.wav "Vain tiedostoon"
```

Palvelin kuuntelee `127.0.0.1:8179`. Konttisovellukset (esim. `mactonus`-cron-skriptit) voivat kutsua sitä `host.docker.internal:8179` -aliaksen kautta.

## Sammutus

```bash
pkill ollama && deactivate
```

## Poisto

```bash
rm -rf .venv ~/.cache/huggingface/hub/models--openbmb--VoxCPM2 ~/.ollama
brew uninstall ollama sox
```
