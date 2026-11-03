"""Old pictures from Wikimedia Commons, added to the city archive's -> web/public/data/photos.json

For every label whose Wikidata item (data/raw/notable.json, by name) has a Commons category (P373): the files in that
category dated before 1950 under a free licence (public domain, CC0, CC BY, CC BY-SA), not interiors, plans, tombs or
objects; up to 8 per place spread over the years. Paintings and prints from the Rijksmuseum and others, early
photographs. Each keeps its author and licence for the credit, and links to its Commons page; thumbnails are
Commons' own, not copied. Run after photos.py, which it extends.

usage: uv run python scripts/photos_commons.py
"""
import json
import re
import time
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"
S = requests.Session()
S.headers["User-Agent"] = "amsterdam-voxel/0.1 (https://github.com/melvinwevers/amsterdam-voxel)"
OUT = Path("web/public/data/photos.json")
SKIP = re.compile(r"interi|orgel|organ|plattegrond|floor ?plan|grafsteen|grave|tomb|epitaaf|medal|penning|munt\b|coin|"
                  r"bord|plate|tegel|tile|glas-in-lood|stained|doopvont|preekstoel|pulpit|kansel|detail|wapen|coat of arms",
                  re.I)
FREE = re.compile(r"public domain|^pd|cc0|cc[ -]by", re.I)


def get(api, **p):
    for wait in (1, 4, 15, 40):
        try:
            r = S.get(api, params=dict(format="json", **p), timeout=60)
            if r.ok:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(wait)
    return {}


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


meta = json.load(open("web/public/data/meta.json"))
notable = json.load(open("data/raw/notable.json"))
by_name = {}
for q, e in notable.items():
    for n in (e.get("pl"), e.get("en")):
        if n:
            by_name.setdefault(n, q)
labels = {l["name"]: l for l in meta["labels"]}
qids = {n: by_name[n] for n in labels if n in by_name}
cats = {}
qs = list(set(qids.values()))
for i in range(0, len(qs), 50):
    r = get(WD, action="wbgetentities", ids="|".join(qs[i:i + 50]), props="claims")
    for q, ent in r.get("entities", {}).items():
        c = ent.get("claims", {}).get("P373")
        if c:
            cats[q] = c[0]["mainsnak"]["datavalue"]["value"]
print(len(labels), "labels,", len(qids), "with a Wikidata item,", len(cats), "with a Commons category")

photos = json.load(open(OUT))
places = {p["name"]: p for p in photos["places"]}
added = 0
for name, q in qids.items():
    if q not in cats:
        continue
    files, cont = [], {}
    while len(files) < 1500:
        r = get(API, action="query", list="categorymembers", cmtitle="Category:" + cats[q], cmtype="file", cmlimit=500, **cont)
        files += [m["title"] for m in r.get("query", {}).get("categorymembers", [])]
        if "continue" not in r:
            break
        cont = r["continue"]
    found = []
    for i in range(0, len(files), 50):
        r = get(API, action="query", titles="|".join(files[i:i + 50]), prop="imageinfo", iiprop="extmetadata|url",
                iiurlwidth=420, iiextmetadatafilter="DateTimeOriginal|LicenseShortName|Artist|ObjectName|ImageDescription")
        for pg in r.get("query", {}).get("pages", {}).values():
            ii = (pg.get("imageinfo") or [{}])[0]
            m = ii.get("extmetadata", {})
            y = re.search(r"\b(1[4-9]\d\d)\b", clean(m.get("DateTimeOriginal", {}).get("value")))
            lic = clean(m.get("LicenseShortName", {}).get("value"))
            title = clean(m.get("ObjectName", {}).get("value")) or pg["title"][5:].rsplit(".", 1)[0]
            if not y or int(y.group(1)) >= 1950 or not FREE.search(lic) or not ii.get("thumburl"):
                continue
            if SKIP.search(pg["title"]) or SKIP.search(title):
                continue
            found.append(dict(year=int(y.group(1)), title=title[:160], kind="commons", by=clean(m.get("Artist", {}).get("value"))[:80] or None,
                              thumb=ii["thumburl"], link=ii.get("descriptionurl"), license=lic))
    if not found:
        continue
    found.sort(key=lambda f: f["year"])
    if len(found) > 8:
        step = (len(found) - 1) / 7
        found = [found[round(j * step)] for j in range(8)]
    l = labels[name]
    p = places.setdefault(name, dict(name=name, x=l["x"], y=l["y"], items=[]))
    have = {it["link"] for it in p["items"]}
    p["items"] += [f for f in found if f["link"] not in have]
    added += len(found)
    print(f"{name}: +{len(found)} from Commons ({found[0]['year']}-{found[-1]['year']})")
    time.sleep(0.2)
photos["places"] = list(places.values())
photos["source"] = "Stadsarchief Amsterdam, Beeldbank (copyright-free records); Wikimedia Commons (free licences, credited per picture)"
json.dump(photos, open(OUT, "w"), ensure_ascii=False)
print(len(photos["places"]), "places with old pictures,", sum(len(p["items"]) for p in photos["places"]), "pictures;", added, "from Commons")
