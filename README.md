# Paikallinen puheassistentti

Puheassistentti, joka yhdistää paikallisen LLM:n (Ollama) ja VoxCPM2-puhesynteesimallin. Vastaukset puhutaan reaaliajassa lause kerrallaan — kaikki pyörii omalla koneella.

## Vaatimukset

- macOS (Apple Silicon)
- [Homebrew](https://brew.sh)
- [Ollama](https://ollama.com)

## Asennus

```bash
brew install ollama sox python@3.12
ollama pull gemma4

python3.12 -m venv ~/voxcpm2-env
source ~/voxcpm2-env/bin/activate
pip install voxcpm soundfile requests numpy
```

## Nauhoita oma ääni (kerran)

```bash
source ~/voxcpm2-env/bin/activate && python record_voice.py
```

## Käynnistys

```bash
source ~/voxcpm2-env/bin/activate && python voice_assistant.py --pick --model gemma4 --lang fi
```

## Sano jotain nopeasti

```bash
source ~/voxcpm2-env/bin/activate && python say.py --pick
```

## Sammutus

```bash
pkill ollama && deactivate
```

## Poisto

```bash
rm -rf ~/voxcpm2-env ~/.cache/huggingface/hub/models--openbmb--VoxCPM2 ~/.ollama
brew uninstall ollama sox
```
