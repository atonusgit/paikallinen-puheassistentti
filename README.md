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
ollama pull gemma4

python3.12 -m venv .venv
source .venv/bin/activate
pip install voxcpm soundfile requests numpy
```

## Nauhoita oma ääni (kerran)

```bash
source .venv/bin/activate && python record_voice.py
```

## Käynnistys

```bash
source .venv/bin/activate && python voice_assistant.py --pick --model gemma4 --lang fi
```

## Sano jotain nopeasti

```bash
source .venv/bin/activate && python say.py --pick
```

## Sammutus

```bash
pkill ollama && deactivate
```

## Poisto

```bash
rm -rf .venv ~/.cache/huggingface/hub/models--openbmb--VoxCPM2 ~/.ollama
brew uninstall ollama sox
```
