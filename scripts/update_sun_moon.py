#!/usr/bin/env python3
"""Récupère le lever et le coucher du soleil et de la lune, et les phases de la Lune,
publiés par Météo Maurice (MMS), et met à jour data/sun_moon.json.

- Lit les trois pages publiques (île Maurice) et en extrait les tableaux mensuels.
- Vérifie la cohérence des valeurs avant de les accepter : une page mal lue ne remplace
  jamais des données correctes, et l'échec reste visible dans GitHub Actions.
- Fusionne avec les données déjà présentes (les nouveaux mois remplacent les anciens,
  les mois passés sont conservés 12 mois).

Aucune dépendance externe : bibliothèque standard Python uniquement.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from update_tides import MONTHS, fetch, tokenize

SOURCES = {
    "sun": "https://metservice.intnet.mu/sun-moon-and-tides-sunrise-sunset-mauritius.php",
    "moon": "https://metservice.intnet.mu/sun-moon-and-tides-moonrise-moonset-mauritius.php",
    "phases": "https://metservice.intnet.mu/sun-moon-and-tides-moon-phase.php",
}
LABELS = {"sun": "Soleil", "moon": "Lune", "phases": "Phases de la Lune"}
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sun_moon.json"
KEEP_MONTHS = 12
MAURITIUS = timezone(timedelta(hours=4))

MONTH_NAMES = {**MONTHS, **{name[:3]: num for name, num in MONTHS.items()}, "sept": 9}
MONTH_RE = re.compile(r"([A-Za-z]+)\.?,?\s*(\d{4})?")
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:h.]\s*([0-5]\d)(?!\d)")
DAY_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\.?", re.I)
PHASES = {"NM": "NM", "NEWMOON": "NM", "FQ": "FQ", "FIRSTQUARTER": "FQ",
          "FM": "FM", "FULLMOON": "FM", "LQ": "LQ", "LASTQUARTER": "LQ", "THIRDQUARTER": "LQ"}
CYCLE = ["NM", "FQ", "FM", "LQ"]
RISE, SET = 0, 1


# ---------- Lecture des tableaux HTML ----------

class TableParser(HTMLParser):
    """Lit chaque tableau de la page : ses lignes de cellules (texte, colspan, rowspan) et
    le dernier « Mois Année » rencontré avant lui (titre éventuellement placé hors du tableau)."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[tuple[str | None, list[list[tuple[str, int, int]]]]] = []
        self._open: list[dict] = []  # tableaux en cours (ils peuvent être imbriqués)
        self._skip = 0
        self._title: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "table":
            self._open.append({"title": self._title, "rows": [], "cell": None})
        elif self._open:
            t = self._open[-1]
            if tag == "tr":
                t["rows"].append([])
                t["cell"] = None
            elif tag in ("td", "th"):
                if not t["rows"]:
                    t["rows"].append([])
                a = dict(attrs)
                t["cell"] = [[], span(a.get("colspan")), span(a.get("rowspan"))]
                t["rows"][-1].append(t["cell"])
            elif tag == "br" and t["cell"] is not None:
                t["cell"][0].append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "table" and self._open:
            t = self._open.pop()
            rows = [[(clean("".join(c[0])), c[1], c[2]) for c in r] for r in t["rows"]]
            self.tables.append((t["title"], rows))
        elif tag in ("td", "th") and self._open:
            self._open[-1]["cell"] = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._open and self._open[-1]["cell"] is not None:
            self._open[-1]["cell"][0].append(data)
        elif key := titled_month(clean(data)):  # titre, légende du tableau…
            if self._open:
                self._open[-1]["title"] = key
            else:
                self._title = key


def span(value) -> int:
    try:
        return min(max(int(value), 1), 50)
    except (TypeError, ValueError):
        return 1


def clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def read_tables(html: str):
    p = TableParser()
    p.feed(html)
    p.close()
    return p.tables


def grid(rows) -> list[list[str]]:
    """Développe colspan et rowspan : chaque ligne devient une liste de textes alignés par colonne."""
    out, carry = [], {}  # carry : colonne → [texte, lignes restantes]
    for row in rows:
        line: list[str] = []

        def take_carry():
            while len(line) in carry:
                c = len(line)
                line.append(carry[c][0])
                carry[c][1] -= 1
                if not carry[c][1]:
                    del carry[c]

        for text, colspan, rowspan in row:
            take_carry()
            for _ in range(colspan):
                if rowspan > 1:
                    carry[len(line)] = [text, rowspan - 1]
                line.append(text)
        take_carry()
        while carry and len(line) < max(carry):
            line.append("")
            take_carry()
        out.append(line)
    return out


# ---------- Reconnaissance des valeurs ----------

def month_key(text: str, today: date) -> str | None:
    """« October 2026 », « Oct. 2026 » ou « October » → « 2026-10 » (année la plus proche si absente)."""
    m = MONTH_RE.fullmatch(text.strip())
    if not m or m.group(1).lower() not in MONTH_NAMES:
        return None
    mo = MONTH_NAMES[m.group(1).lower()]
    if m.group(2):
        y = int(m.group(2))
    else:
        y = min((today.year - 1, today.year, today.year + 1),
                key=lambda yy: abs(yy * 12 + mo - today.year * 12 - today.month))
    return f"{y}-{mo:02d}"


def titled_month(text: str) -> str | None:
    """« October 2026 » (année obligatoire) → « 2026-10 »."""
    m = MONTH_RE.fullmatch(text)
    if m and m.group(2) and m.group(1).lower() in MONTH_NAMES:
        return f"{m.group(2)}-{MONTH_NAMES[m.group(1).lower()]:02d}"
    return None


def as_day(text: str) -> int | None:
    m = DAY_RE.fullmatch(text.strip())
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 31 else None


def as_time(text: str) -> str | None:
    m = TIME_RE.search(text)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def is_blank(text: str) -> bool:
    """Cellule sans chiffre : vide ou « pas d'évènement ce jour-là » (tirets, « No rise »…)."""
    return not re.search(r"\d", text)


def kind(text: str) -> int | None:
    t = text.lower()
    if "rise" in t or "lever" in t:
        return RISE
    if "set" in t or "coucher" in t:
        return SET
    return None


def phase_code(text: str) -> str | None:
    return PHASES.get(re.sub(r"[^A-Z]", "", text.upper()))


def months_in(line: list[str], today: date) -> dict[int, str]:
    return {c: k for c, txt in enumerate(line) if (k := month_key(txt, today))}


def column_map(mcols: dict[int, str], kcols: dict[int, int], width: int) -> dict[int, tuple[str, int]]:
    """Associe chaque colonne de données à (mois, lever|coucher)."""
    months = list(dict.fromkeys(v for _, v in sorted(mcols.items())))
    if not months:
        return {}
    cols = sorted(kcols) if kcols else list(range(1, width))
    kinds = kcols or {c: i % 2 for i, c in enumerate(cols)}
    if all(c in mcols for c in cols):
        return {c: (mcols[c], kinds[c]) for c in cols}
    # En-têtes de mois sans colspan : les colonnes sont réparties dans l'ordre.
    if len(cols) % len(months):
        return {}
    g = len(cols) // len(months)
    return {c: (months[i // g], kinds[c]) for i, c in enumerate(cols)}


# ---------- Interprétation des pages ----------

def parse_riseset(html: str, today: date) -> dict[str, list]:
    """Tableaux « jour | lever | coucher » (un ou plusieurs mois côte à côte)."""
    found: dict[str, dict[int, list]] = {}
    odd = []
    for title, rows in read_tables(html):
        mcols: dict[int, str] = {}
        kcols: dict[int, int] = {}
        for line in grid(rows):
            if not line or as_day(line[0]) is None:
                heads = months_in(line, today)
                if heads:
                    mcols, kcols = heads, {}
                kinds = {c: k for c, txt in enumerate(line) if (k := kind(txt)) is not None}
                if kinds:
                    kcols = kinds
                continue
            day = as_day(line[0])
            mapping = column_map(mcols or ({0: title} if title else {}), kcols, len(line))
            for c, (mkey, k) in mapping.items():
                if c >= len(line) or is_blank(line[c]):
                    continue
                t = as_time(line[c])
                if t is None:
                    odd.append(f"{mkey} j{day} : « {line[c]} »")
                    continue
                found.setdefault(mkey, {}).setdefault(day, [None, None])[k] = t
    if odd:
        raise ValueError("valeurs non reconnues : " + ", ".join(odd[:5]))
    return {k: [[d, *v] for d, v in sorted(days.items())] for k, days in sorted(found.items())}


def parse_phases(html: str, today: date) -> dict[str, list]:
    """Tableaux « phase | jour | heure | minute » (un ou plusieurs mois côte à côte)."""
    found: dict[str, set] = {}
    for title, rows in read_tables(html):
        mcols: dict[int, str] = {}
        for line in grid(rows):
            codes = [c for c, txt in enumerate(line) if phase_code(txt)]
            row_months = months_in(line, today)
            if not codes:
                if row_months:
                    mcols = row_months
                continue
            for c in codes:
                rest = line[c + 1:c + 4] + ["", "", ""]
                day = as_day(rest[0])
                hhmm = as_time(rest[1])
                if hhmm is None and re.fullmatch(r"\d{1,2}", rest[1]) and re.fullmatch(r"\d{2}", rest[2]):
                    h, mi = int(rest[1]), int(rest[2])
                    hhmm = f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None
                month = month_for(c, line, row_months, mcols, title)
                if day and hhmm and month:
                    found.setdefault(month, set()).add((day, hhmm, phase_code(line[c])))
    return {k: [list(e) for e in sorted(v)] for k, v in sorted(found.items())}


def month_for(c: int, line: list[str], row_months: dict[int, str], mcols: dict[int, str], title):
    left = [k for col, k in row_months.items() if col < c]
    if left:  # mois indiqué dans la ligne elle-même, à gauche de la phase
        return left[-1]
    if c in mcols:
        return mcols[c]
    months = list(dict.fromkeys(v for _, v in sorted(mcols.items())))
    if months and len(line) % len(months) == 0:
        return months[min(c // (len(line) // len(months)), len(months) - 1)]
    return title


# ---------- Contrôles de cohérence ----------

def complete_months(months: dict[str, list], label: str) -> dict[str, list]:
    """Garde les mois dont tous les jours sont présents (un mois partiel est ignoré, et signalé)."""
    if not months:
        raise ValueError("aucun tableau reconnu")
    full = {}
    for key, rows in months.items():
        y, m = map(int, key.split("-"))
        if [r[0] for r in rows] == list(range(1, calendar.monthrange(y, m)[1] + 1)):
            full[key] = rows
        else:
            print(f"{label} : {key} incomplet ({len(rows)} jours lus), ignoré.", file=sys.stderr)
    if not full:
        raise ValueError("aucun mois complet")
    return full


def check_sun(months: dict[str, list]) -> dict[str, list]:
    months = complete_months(months, LABELS["sun"])
    for key, rows in months.items():
        for d, rise, sset in rows:
            # À Maurice, le soleil se lève entre 5 h 15 et 7 h et se couche entre 17 h 30 et 19 h.
            if not (rise and sset and "04:45" <= rise <= "07:30" and "17:00" <= sset <= "19:30"):
                raise ValueError(f"{key}-{d:02d} : lever {rise} / coucher {sset} invraisemblables")
    return months


def check_moon(months: dict[str, list]) -> dict[str, list]:
    months = complete_months(months, LABELS["moon"])
    for key, rows in months.items():
        if sum(not r[1] for r in rows) > 2 or sum(not r[2] for r in rows) > 2:
            raise ValueError(f"{key} : trop de jours sans lever ou sans coucher de lune")
    return months


def phase_events(months: dict[str, list]) -> list[tuple[datetime, str]]:
    return sorted((datetime(int(k[:4]), int(k[5:7]), d, *map(int, t.split(":"))), code)
                  for k, rows in months.items() for d, t, code in rows)


def check_phases(months: dict[str, list]) -> dict[str, list]:
    if not months:
        raise ValueError("aucun tableau reconnu")
    for key, rows in months.items():
        if len(rows) < 3:
            raise ValueError(f"{key} : seulement {len(rows)} phase(s) lue(s)")
    ev = phase_events(months)
    for (t0, c0), (t1, c1) in zip(ev, ev[1:]):
        gap = (t1 - t0).total_seconds() / 86400
        if CYCLE[(CYCLE.index(c0) + 1) % 4] != c1 and gap < 20:
            raise ValueError(f"phases dans le désordre : {c0} le {t0:%d/%m %H:%M} puis {c1} le {t1:%d/%m %H:%M}")
        if CYCLE[(CYCLE.index(c0) + 1) % 4] == c1 and not 5.5 <= gap <= 9.5:
            raise ValueError(f"écart invraisemblable entre {c0} ({t0:%d/%m}) et {c1} ({t1:%d/%m})")
    return months


def check_moon_vs_phases(moon: dict[str, list], phases: dict[str, list]) -> None:
    """Repère une inversion des colonnes lever/coucher : à la pleine lune, la lune se lève
    le soir ; à la nouvelle lune, le matin."""
    rises = {f"{k}-{r[0]:02d}": r[1] for k, rows in moon.items() for r in rows}
    for t, code in phase_events(phases):
        rise = rises.get(f"{t:%Y-%m-%d}")
        if not rise:
            continue
        if code == "FM" and not "14:00" <= rise <= "22:00":
            raise ValueError(f"lever de lune à {rise} le jour de la pleine lune ({t:%d/%m}) : colonnes inversées ?")
        if code == "NM" and not "03:00" <= rise <= "10:00":
            raise ValueError(f"lever de lune à {rise} le jour de la nouvelle lune ({t:%d/%m}) : colonnes inversées ?")


PARSE = {"sun": parse_riseset, "moon": parse_riseset, "phases": parse_phases}
CHECK = {"sun": check_sun, "moon": check_moon, "phases": check_phases}


def dump(html: str, limit: int = 45) -> str:
    """Aperçu des tableaux de la page, pour diagnostiquer un changement de format."""
    out = []
    for i, (title, rows) in enumerate(read_tables(html), 1):
        lines = [" | ".join(line) for line in grid(rows) if any(line)]
        if lines:
            out.append(f"--- tableau {i}{f' (après « {title} »)' if title else ''} : {len(lines)} lignes")
            out += lines[:limit]
    if not out:
        out = ["(aucun tableau dans la page) Texte : " + " ".join(tokenize(html))[:3000]]
    return "\n".join(out)


def summary(name: str, months: dict[str, list]) -> str:
    if name == "phases":
        return ", ".join(f"{k} ({' '.join(f'{c} {d}/{t}' for d, t, c in rows)})" for k, rows in months.items())
    return ", ".join(f"{k} ({len(rows)} j, 1er : {rows[0][1] or '—'}/{rows[0][2] or '—'})" for k, rows in months.items())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in SOURCES:
        ap.add_argument(f"--{name}", metavar="PAGE.html", help=f"copie enregistrée de la page ({LABELS[name]})")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = now.astimezone(MAURITIUS).date()
    data = {"sources": SOURCES, "sun": {}, "moon": {}, "phases": {}}
    if DATA_FILE.exists():
        data = {**data, **json.loads(DATA_FILE.read_text(encoding="utf-8"))}
    data["sources"] = SOURCES
    data["checked_at"] = now.isoformat(timespec="seconds")

    ok, parsed = True, {}
    for name, url in SOURCES.items():
        try:
            saved = getattr(args, name)
            html = Path(saved).read_text(encoding="utf-8") if saved else fetch(url)
        except Exception as e:  # réseau, fichier…
            print(f"{LABELS[name]} : page illisible ({e}) — données existantes conservées.", file=sys.stderr)
            ok = False
            continue
        try:
            months = CHECK[name](PARSE[name](html, today))
        except ValueError as e:
            print(f"{LABELS[name]} : {e} — données existantes conservées.\n{dump(html)}", file=sys.stderr)
            ok = False
            continue
        parsed[name] = months

    if "moon" in parsed:
        try:
            check_moon_vs_phases(parsed["moon"], {**data["phases"], **parsed.get("phases", {})})
        except ValueError as e:
            print(f"{LABELS['moon']} : {e} — données existantes conservées.", file=sys.stderr)
            del parsed["moon"]
            ok = False

    changed = False
    cutoff = (now.year * 12 + now.month - 1) - KEEP_MONTHS
    for name, months in parsed.items():
        changed |= any(data[name].get(k) != v for k, v in months.items())
        data[name].update(months)
        data[name] = {k: v for k, v in sorted(data[name].items())
                      if int(k[:4]) * 12 + int(k[5:7]) - 1 >= cutoff}
        print(f"{LABELS[name]} : {summary(name, months)}")
    if changed:
        data["updated_at"] = data["checked_at"]

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Nouvelles données." if changed else "Aucun changement.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
