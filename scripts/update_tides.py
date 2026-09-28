#!/usr/bin/env python3
"""Récupère les prédictions de marées de Météo Maurice (MMS) et met à jour data/tides.json.

- Lit la page publique des marées de Maurice.
- Extrait chaque tableau mensuel (jour, 2 pleines mers, 2 basses mers).
- Fusionne avec les données déjà présentes (les nouveaux mois remplacent les anciens,
  les mois passés sont conservés 12 mois).
- Écrit toujours `checked_at` : le commit mensuel garde le dépôt actif, sinon GitHub
  désactive les tâches planifiées après 60 jours sans activité.

Aucune dépendance externe : bibliothèque standard Python uniquement.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SOURCE_URL = "https://metservice.intnet.mu/sun-moon-and-tides-tides-mauritius.php"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tides.json"
KEEP_MONTHS = 12

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
HEIGHT_RE = re.compile(r"^-?\d{1,3}$")
DASHES = {"-", "–", "—", "--"}


class TextCollector(HTMLParser):
    """Collecte le texte visible, en ignorant scripts et styles."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def tokenize(html: str) -> list[str]:
    p = TextCollector()
    p.feed(html)
    text = " ".join(p.parts).replace("\xa0", " ")
    return text.split()


def norm_time(tok: str) -> str:
    h, m = tok.split(":")
    return f"{int(h):02d}:{m}"


def parse_pair(t: str, h: str):
    """Retourne (heure, hauteur) ou (None, None) ; lève ValueError si le motif ne colle pas."""
    if t in DASHES and h in DASHES:
        return None, None
    if TIME_RE.match(t) and HEIGHT_RE.match(h):
        return norm_time(t), int(h)
    raise ValueError


def parse(html: str) -> dict[str, list]:
    tokens = tokenize(html)
    months: dict[str, list] = {}
    current = None
    i = 0
    while i < len(tokens):
        tok = tokens[i].strip(",.*")
        low = tok.lower()
        # En-tête de mois : « September 2026 »
        if low in MONTHS and i + 1 < len(tokens) and re.fullmatch(r"\d{4}", tokens[i + 1].strip("*")):
            current = f"{tokens[i + 1].strip('*')}-{MONTHS[low]:02d}"
            months.setdefault(current, [])
            i += 2
            continue
        # Ligne : jour suivi de 4 paires (heure, hauteur)
        if current and re.fullmatch(r"\d{1,2}", tok) and 1 <= int(tok) <= 31 and i + 8 < len(tokens):
            vals = [x.strip("*") for x in tokens[i + 1:i + 9]]
            try:
                pairs = [parse_pair(vals[k], vals[k + 1]) for k in range(0, 8, 2)]
            except ValueError:
                i += 1
                continue
            day = int(tok)
            rows = months[current]
            if (not rows and day == 1) or (rows and day == rows[-1][0] + 1):
                row = [day]
                for t, h in pairs:
                    row += [t, h]
                rows.append(row)
                i += 9
                continue
        i += 1
    # Garder uniquement les mois cohérents (commencent au 1er, au moins 28 jours)
    return {k: v for k, v in months.items() if len(v) >= 28 and v[0][0] == 1}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; MareesMauriceBot/1.0; +https://github.com)",
        "Accept-Language": "en,fr;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else None
    html = Path(source).read_text(encoding="utf-8") if source else fetch(SOURCE_URL)
    new_months = parse(html)

    data = {"source": SOURCE_URL, "months": {}}
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    now = datetime.now(timezone.utc)
    data["checked_at"] = now.isoformat(timespec="seconds")

    if not new_months:
        print("Aucun tableau de marées reconnu sur la page : données existantes conservées.", file=sys.stderr)
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 1  # l'échec reste visible dans GitHub Actions

    changed = any(data["months"].get(k) != v for k, v in new_months.items())
    data["months"].update(new_months)

    # Élaguer les mois trop anciens
    cutoff = (now.year * 12 + now.month - 1) - KEEP_MONTHS
    data["months"] = {k: v for k, v in sorted(data["months"].items())
                      if int(k[:4]) * 12 + int(k[5:7]) - 1 >= cutoff}
    if changed or "updated_at" not in data:
        data["updated_at"] = data["checked_at"]

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Mois lus : {', '.join(new_months)} — {'nouvelles données' if changed else 'aucun changement'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
