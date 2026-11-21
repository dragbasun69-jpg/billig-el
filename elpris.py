"""Elprisnotis: skickar notiser om dygnets billigaste kvartar via ntfy.

Körs av GitHub Actions. Hämtar morgondagens kvartspriser från elprisetjustnu.se
när de har publicerats (cirka kl 13), skickar en plan direkt och schemalägger
en påminnelse strax innan varje billig period börjar.

Bara standardbiblioteket används, så inget behöver installeras.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Stockholm")
STATEFIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skickat.txt")
VECKODAGAR = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"]
MANADER = ["jan", "feb", "mar", "apr", "maj", "jun",
           "jul", "aug", "sep", "okt", "nov", "dec"]


def config():
    def tal(namn, standard):
        varde = os.environ.get(namn, "").strip()
        return int(varde) if varde else standard

    return {
        "elomrade": os.environ.get("ELOMRADE", "").strip() or "SE4",
        "antal": tal("ANTAL_KVARTAR", 8),
        "fore": tal("PAMINN_MINUTER_FORE", 5),
        "tyst_fran": tal("TYST_FRAN", 22),
        "tyst_till": tal("TYST_TILL", 7),
        "topic": os.environ.get("NTFY_TOPIC", "").strip(),
        "server": (os.environ.get("NTFY_SERVER", "").strip() or "https://ntfy.sh").rstrip("/"),
        "sida": os.environ.get("SIDA_URL", "").strip(),
        "torrkorning": os.environ.get("TORRKORNING", "") == "1",
    }


# ---------- Hämta och räkna ----------

def hamta_priser(dag, elomrade):
    """Returnerar lista med (start, slut, öre/kWh) eller None om priserna saknas."""
    url = (f"https://www.elprisetjustnu.se/api/v1/prices/"
           f"{dag:%Y}/{dag:%m-%d}_{elomrade}.json")
    try:
        with urllib.request.urlopen(url, timeout=30) as svar:
            data = json.load(svar)
    except urllib.error.HTTPError as fel:
        if fel.code == 404:
            return None
        raise
    return tolka_priser(data)


def tolka_priser(data):
    kvartar = []
    for rad in data:
        start = datetime.fromisoformat(rad["time_start"]).astimezone(TZ)
        slut = datetime.fromisoformat(rad["time_end"]).astimezone(TZ)
        kvartar.append((start, slut, rad["SEK_per_kWh"] * 100))
    kvartar.sort(key=lambda k: k[0])
    return kvartar


def billigaste_perioder(kvartar, antal):
    """Väljer de billigaste kvartarna och slår ihop dem som ligger i följd."""
    valda = sorted(kvartar, key=lambda k: (k[2], k[0]))[:antal]
    valda.sort(key=lambda k: k[0])
    perioder = []
    for kvart in valda:
        if perioder and perioder[-1][-1][1] == kvart[0]:
            perioder[-1].append(kvart)
        else:
            perioder.append([kvart])
    return [
        {
            "start": p[0][0],
            "slut": p[-1][1],
            "snitt": sum(k[2] for k in p) / len(p),
        }
        for p in perioder
    ]


# ---------- Formatering ----------

def ore(varde):
    """Öre med decimalkomma, t.ex. 41,3."""
    return f"{varde:.1f}".replace(".", ",").replace("-", "−")


def klocka(t):
    return f"{t:%H:%M}"


def slutklocka(p):
    # En period som slutar vid midnatt visas som 24:00, inte 00:00.
    if p["slut"].date() > p["start"].date() and p["slut"].hour == 0 and p["slut"].minute == 0:
        return "24:00"
    return klocka(p["slut"])


def dagnamn(dag):
    return f"{VECKODAGAR[dag.weekday()]} {dag.day} {MANADER[dag.month - 1]}"


def i_tyst_tid(t, fran, till):
    if fran == till:
        return False
    if fran < till:
        return fran <= t.hour < till
    return t.hour >= fran or t.hour < till


def bygg_plan(dag, kvartar, perioder, cfg):
    dygnssnitt = sum(k[2] for k in kvartar) / len(kvartar)
    rader = [f"{klocka(p['start'])}–{slutklocka(p)}   {ore(p['snitt'])} öre"
             for p in perioder]
    minuter = cfg["antal"] * 15
    tid = f"{minuter // 60} h" if minuter % 60 == 0 else f"{minuter} min"
    text = (
        "\n".join(rader)
        + f"\n\nDygnets snitt: {ore(dygnssnitt)} öre/kWh"
        + f"\nDe {cfg['antal']} billigaste kvartarna ({tid}). Spotpris utan moms."
    )
    titel = f"Billigast el i morgon, {dagnamn(dag)}"
    return titel, text, dygnssnitt


def bygg_paminnelse(p, dygnssnitt):
    titel = f"Billig el kl {klocka(p['start'])}–{slutklocka(p)}"
    text = f"Snitt {ore(p['snitt'])} öre/kWh, att jämföra med dygnets {ore(dygnssnitt)}."
    return titel, text


# ---------- Skicka ----------

def skicka(cfg, titel, text, nar=None, prioritet="default", taggar="zap"):
    if cfg["torrkorning"] or not cfg["topic"]:
        tidpunkt = f" (schemalagd {nar:%Y-%m-%d %H:%M})" if nar else ""
        print(f"--- {titel}{tidpunkt}\n{text}\n")
        return
    rubriker = {
        "Title": titel.encode("utf-8"),
        "Priority": prioritet,
        "Tags": taggar,
        "Content-Type": "text/plain; charset=utf-8",
    }
    if nar is not None:
        rubriker["At"] = str(int(nar.timestamp()))
    if cfg["sida"]:
        rubriker["Click"] = cfg["sida"]
    req = urllib.request.Request(
        f"{cfg['server']}/{cfg['topic']}",
        data=text.encode("utf-8"),
        headers=rubriker,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as svar:
        svar.read()


def redan_skickat(dag):
    try:
        with open(STATEFIL, encoding="utf-8") as f:
            return f.read().strip() == dag.isoformat()
    except FileNotFoundError:
        return False


def markera_skickat(dag):
    with open(STATEFIL, "w", encoding="utf-8") as f:
        f.write(dag.isoformat() + "\n")


# ---------- Huvudflöde ----------

def kor(cfg, nu=None, kvartar=None):
    nu = nu or datetime.now(TZ)
    imorgon = (nu + timedelta(days=1)).date()

    if kvartar is None:
        if not cfg["torrkorning"] and redan_skickat(imorgon):
            print(f"Redan skickat för {imorgon}.")
            return False
        kvartar = hamta_priser(imorgon, cfg["elomrade"])
        if not kvartar:
            print(f"Priserna för {imorgon} är inte publicerade än.")
            return False

    perioder = billigaste_perioder(kvartar, cfg["antal"])
    titel, text, dygnssnitt = bygg_plan(imorgon, kvartar, perioder, cfg)
    skicka(cfg, titel, text, taggar="calendar")

    for p in perioder:
        nar = p["start"] - timedelta(minutes=cfg["fore"])
        if i_tyst_tid(p["start"], cfg["tyst_fran"], cfg["tyst_till"]):
            print(f"Ingen påminnelse kl {klocka(p['start'])} (tyst tid).")
            continue
        if nar <= nu + timedelta(seconds=30):
            continue
        ptitel, ptext = bygg_paminnelse(p, dygnssnitt)
        skicka(cfg, ptitel, ptext, nar=nar, prioritet="high", taggar="zap")

    if not cfg["torrkorning"]:
        markera_skickat(imorgon)
    print(f"Klart: {len(perioder)} billiga perioder för {imorgon}.")
    return True


if __name__ == "__main__":
    installningar = config()
    if not installningar["topic"] and not installningar["torrkorning"]:
        sys.exit("NTFY_TOPIC saknas. Lägg in den som secret i GitHub.")
    kor(installningar)
