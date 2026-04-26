"""
Nopea TTS-client: lähettää tekstin VoxCPM2-palvelimelle, palvelin generoi ja soittaa.

Vaatii että voxcpm2_server.py on käynnissä (oletus 127.0.0.1:8179).

Käyttö:
  python say.py --pick                          # valitse ääni voices-kansiosta
  python say.py --ref anton.wav "Hei maailma"
  python say.py --voice "A deep male voice" "Hello world"
  python say.py --no-play "Hei"                 # generoi mutta älä soita
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

from voice_picker import resolve_ref

PALVELIN_URL = "http://127.0.0.1:8179"
AIKAKATKAISU = 180  # sek; mallin generointi voi viedä hetken pidemmälle tekstille


def lahetä(req):
    data = json.dumps(req).encode("utf-8")
    pyynto = urllib.request.Request(
        PALVELIN_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(pyynto, timeout=AIKAKATKAISU) as vastaus:
            return json.loads(vastaus.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"Yhteysvirhe: {e}. Onko voxcpm2_server.py käynnissä?"}
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except (ValueError, OSError):
            return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}


def puhu(text, ref_path, args):
    req = {
        "text": text,
        "ref": ref_path,
        "voice": args.voice,
        "play": not args.no_play,
        "output": args.output,
    }
    vastaus = lahetä(req)
    if vastaus.get("ok"):
        print(f"Tallennettu: {vastaus['outfile']}")
        return True
    print(f"Virhe: {vastaus.get('error')}", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="VoxCPM2-client (HTTP)")
    parser.add_argument("text", nargs="?", help="Teksti joka puhutaan")
    parser.add_argument("--ref", default=None, help="Referenssi-wav tiedostonimi")
    parser.add_argument("--pick", action="store_true", help="Valitse ääni voices-kansiosta")
    parser.add_argument("--voice", default=None, help="Äänikuvaus")
    parser.add_argument("-o", "--output", default=None, help="Tallenna tiedostoon")
    parser.add_argument("--no-play", action="store_true", help="Älä soita, vain generoi")
    args = parser.parse_args()

    ref_path = resolve_ref(args.ref, pick=args.pick)

    if args.text:
        sys.exit(0 if puhu(args.text, ref_path, args) else 1)

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
        puhu(text, ref_path, args)


if __name__ == "__main__":
    main()
