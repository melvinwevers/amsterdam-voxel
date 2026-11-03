"""Old pictures of the labelled places, from the city archive's image bank -> web/public/data/photos.json

Stadsarchief Amsterdam, Beeldbank (archief.amsterdam/api/opensearch, the archive's open search API): for every label
on the map (meta.json), the records found under its name that
  - are marked copyright-free ("Auteursrechtvrij"): no others are used,
  - are a photo, print, drawing or postcard,
  - name the place in their title or building field (a search hit alone is not enough),
  - carry a year.
Up to 12 per place, spread over the years. The viewer shows them in the place's "Then" panel (web/src/photos.ts),
nearest the year slider's year first; thumbnails are linked from the archive's image server, never copied.

usage: uv run python scripts/photos.py
"""
import html
import json
import re
import time
import unicodedata
from pathlib import Path

import requests

API = "https://archief.amsterdam/api/opensearch/"
UA = {"User-Agent": "amsterdam-voxel/0.1 (research prototype)"}
OUT = Path("web/public/data/photos.json")
TYPES = {"foto", "prent", "tekening", "prentbriefkaart", "aquarel", "schilderij"}
STOP = {"de", "het", "van", "en", "op", "in", "aan", "amsterdam", "the", "of", "museum", "kerk", "huis"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def field(item, k):
    m = re.search(rf"<{k}>(.*?)</{k}>", item, re.S)
    return html.unescape(m.group(1).strip()) if m else None


def search(q, n=80):
    for wait in (2, 5, 15, 30):
        try:
            r = requests.get(API, params={"q": q, "count": n}, headers=UA, timeout=60)
            if r.ok:
                return re.findall(r"<item>(.*?)</item>", r.text, re.S)
        except requests.RequestException:
            pass
        time.sleep(wait)
    return []


def matches(place, text):
    """the place's distinctive words all in the text (diacritics and case ignored)"""
    words = [w for w in norm(place).split() if w not in STOP and len(w) > 2] or norm(place).split()
    t = norm(text)
    return all(re.search(rf"\b{re.escape(w)}", t) for w in words)


def spread(items, k=12):
    """k items spread over the years: sort by year, take evenly spaced ones"""
    items = sorted(items, key=lambda i: i["year"])
    if len(items) <= k:
        return items
    step = (len(items) - 1) / (k - 1)
    return [items[round(j * step)] for j in range(k)]


meta = json.load(open("web/public/data/meta.json"))
places, seen = [], set()
for l in meta["labels"]:
    name = l["name"]
    if name in seen:
        continue
    seen.add(name)
    found = {}
    for it in search(name):
        title, gebouw = field(it, "dc_title") or "", field(it, "sk_gebouw") or ""
        kind, rights, date = field(it, "sk_documenttype"), field(it, "sr_rechthebbende"), field(it, "dc_date") or ""
        y = re.search(r"\b(1[2-9]\d\d)\b", date)
        thumb = re.search(r'<enclosure\s+url="([^"]+)"', it)
        link = field(it, "link")
        if rights != "Auteursrechtvrij" or kind not in TYPES or not y or not thumb or not link:
            continue
        if not (matches(name, title) or matches(name, gebouw)):
            continue
        found[link] = dict(year=int(y.group(1)), title=title[:160], kind=kind, by=field(it, "sk_vervaardiger"),
                           thumb=thumb.group(1), link=link)
    if found:
        picks = spread(list(found.values()))
        places.append(dict(name=name, x=l["x"], y=l["y"], items=picks))
        print(f"{name}: {len(found)} usable, {picks[0]['year']}-{picks[-1]['year']}")
    time.sleep(0.3)
json.dump(dict(source="Stadsarchief Amsterdam, Beeldbank (records marked copyright-free)", places=places),
          open(OUT, "w"), ensure_ascii=False)
print(len(places), "places with old pictures,", sum(len(p["items"]) for p in places), "pictures")
