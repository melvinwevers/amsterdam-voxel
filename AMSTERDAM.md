# Amsterdam port: source data

A port of [stared/warsaw-vibe-voxel](https://github.com/stared/warsaw-vibe-voxel) (Piotr Migdał, MIT) to Amsterdam.

The AOI (`scripts/aoi.py`) is 3400 × 3300 m on the RD New axes (EPSG:28992), centred on the Dam: from the Westerkerk
and the Jordaan east to Artis, from the IJ behind Centraal Station south to the Rijksmuseum. The grid is not rotated:
the canal belt is a horseshoe with no single axis.

```sh
sh scripts/fetch_nl.sh          # ~1.7 GB into data/raw, cached; LAZ=1 adds the AHN5 point clouds (~4 GB)
```

| Script | Source | Output in `data/raw/` | Size |
|---|---|---|---|
| `fetch_ahn.py` | AHN4 0.5 m DSM + DTM (flown 2020–22), [PDOK WCS](https://service.pdok.nl/rws/ahn/wcs/v1_0?request=GetCapabilities&service=WCS), CC0 | `ahn/{dsm,dtm}_<x>_<y>.tif`, 500 m tiles | 260 MB |
| `fetch_ahn.py --laz` | AHN5 point clouds (flown 2023), [GeoTiles](https://geotiles.citg.tudelft.nl/), CC0 | `ahn5/<sheet>_<nn>.LAZ` | ~4 GB |
| `fetch_ortho.py` | 8 cm RGB ortho `2026_orthoHR`, [PDOK WMS](https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0?request=GetCapabilities&service=wms), CC BY 4.0 | `ortho/<layer>_<x>_<y>.tif`, 200 m tiles | 315 MB |
| `fetch_bgt.py` | BGT large-scale topography (water, roads, pavements, bridges, quays, poles, furniture), [PDOK download API](https://api.pdok.nl/lv/bgt/download/v1_0/ui/), CC0 | `bgt/bgt_<type>.gml` (GML 3.1, arcs included) | 1.1 GB |
| `fetch_3dbag.py` | [3D BAG](https://3dbag.nl) v20250903 buildings, LoD1.2/1.3/2.2 from AHN5, CC BY 4.0 | `3dbag/<z>-<x>-<y>.city.json.gz` (CityJSON) | 57 MB |
| `fetch_bomen.py` | Amsterdam tree register, [api.data.amsterdam.nl](https://api.data.amsterdam.nl/v1/docs/datasets/bomen.html) | `trees/bomen.geojson`, 19 094 trees | 14 MB |
| `fetch_osm.sh` | OSM, Geofabrik Noord-Holland extract, ODbL | `osm.json` (same format as before) | |

Notes:
- The AHN WCS DSM has nodata (3.4e38) over water: it is gridded from every point except those classified as water.
- data.3dbag.nl and 3dbag.nl were unreachable on 2 Nov 2026; `fetch_3dbag.py` reads the tile index from the object
  store behind them, which the index's own links point to anyway.
- The BGT geometry has arcs (`gml:Arc`); GDAL/OGR linearises them on read.
- The AHN5 sheet table in `fetch_ahn.py` (`SHEETS`) covers 15 × 18.75 km around the centre; extend it if the AOI grows.

## Building it

```sh
sh scripts/build_data.sh        # fetch, prep, voxelize, then the viewer's layers
cd web && npx pnpm@12.11.2 dev  # http://localhost:5173/?view=westerkerk&weather=clear
```

What changed from Warsaw to make it run (`CITY`, `CRS` and `LEAF_OFF` in `scripts/aoi.py` switch it):
- `prep.py` reads the AHN/PDOK tiles and fills AHN's gaps (no DSM over water, no DTM under buildings); water at NAP -0.40 m.
- Landmarks: Warsaw's curated geometry (PKiN, bridges, Teatr Wielki) runs only for Warsaw; Amsterdam has its own
  labels and camera presets (`landmarks.py`), and ~150 more labels picked automatically by Dutch + English Wikipedia
  page views (`notable.py`, `labels.py`), with events and paintings filtered out.
- Trees: Amsterdam's register; the AHN LiDAR and the ortho are leaf-off, so crowns are found from the per-sample
  maximum height around every register tree instead of from green in the ortho.
- Facades: OSM has colours for 31 of 29 k buildings, so walls come from the BAG construction year (`start_date`):
  old-centre brick with some plastered fronts, 19th-c. brick and stucco, Amsterdam School brick, post-war and
  modern palettes. Roofs keep their colour from the ortho.
- Viewer: sun at Amsterdam, Dutch climate, no Vistula slider, credits.

## The year slider: Amsterdam through time

"Built by" in the bar (URL `?year=1700`) shows the city as it stood in that year, as far as open data can tell:
- Buildings: each OSM building's BAG construction year (`start_date`), corrected for a few landmarks whose BAG year is
  a restoration's (`year` in `scripts/overrides_amsterdam.json`); later ones lie flat as footprints. Unknown years
  (BAG's 1005 code) stay. Voxels the LiDAR caught with no building to date them (sheds, scaffolding) go in any past
  year. Demolished buildings cannot come back: the past is emptier than it was.
- Street life: no cars before 1920, no trams before 1900 (the simulation and the parked vehicles in the voxels).
- The ground: the latest of six historical town plans at or before the year (Amsterdam Time Machine:
  Berckenrode 1625, De Broen 1724, Loman 1876, Publieke Werken 1909, 1943, 1985), draped on streets and on the
  footprints of buildings not yet built (`scripts/fetch_maps.py`).
- Water: canals and harbours filled in after the year are water again (`scripts/dempingen.py`, from the city's
  historical soil data: 589 fillings in the map, 1333-1980).
- Old pictures: click a label for the city archive's copyright-free photos, prints and drawings of the place,
  nearest the slider's year first (`scripts/photos.py`, linked from the archive, not copied).

## Landmarks at 0.5 m

`scripts/insets.py` rebuilds 14 landmarks (Westertoren and Westerkerk, Zuiderkerk, Munttoren, Montelbaanstoren,
Schreierstoren, Oude Kerk, Nieuwe Kerk, Royal Palace, Rijksmuseum, Beurs van Berlage, Waag, Portuguese Synagogue,
Concertgebouw) at twice the resolution from Kadaster's 3D Basisvoorziening DSM 20 cm (2025, PDOK): the highest point
per 0.5 m cell inside the outline, coloured from the curated 1 m model. The viewer (`web/src/insets.ts`) meshes them
at unit scale, places them by a half-scale mesh matrix and hides their 1 m versions.

Known limits:
- Facade colours are typical for each building's era, not measured per building: no open street-level imagery
  was usable (the city's panorama API returned errors on 2 Nov 2026).
- Landmarks have no curated detail yet (the Westertoren's stone and timber crown, the Rijksmuseum's stone bands).
- Canal-house gables are at 1 m voxels (only the 14 landmarks are at 0.5 m); 3D BAG LoD2.2 roofs are fetched but not
  used yet.
- The city's street-level point cloud (`puntenwolk`, coloured from the panoramas) would give real facade colours,
  but its file server only resolves inside the city network (Nov 2026).
- Some land reclamation is missing from the fillings data (Centraal Station's islands, 1870s), so it stays land.
