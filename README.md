# Amsterdam in voxels

> Based on **[Warsaw in voxels](https://github.com/stared/warsaw-vibe-voxel)** by Piotr Migdał (MIT): this is
> its pipeline and viewer, ported to Amsterdam's open data, with a year slider through the city's history added.

A 3400 × 3300 m diorama of central Amsterdam at 1 m voxels, centred on the Dam: the canal belt and the Jordaan,
the old centre, Centraal Station and the IJ, south to the Rijksmuseum and the Vondelpark's edge. Fourteen landmarks
are drawn at 0.5 m. Date, hour and weather are sliders, and a year slider takes the city back through time: the
buildings standing then, the town plan of the time underfoot, canals since filled in as water, and the city
archive's old pictures of each place.

```sh
cd web && npx pnpm@12.11.2 install && npx pnpm@12.11.2 dev     # http://localhost:5173  (?view=westerkerk&year=1700&weather=clear)
sh scripts/build_data.sh                                       # rebuild the data from the sources (~2 GB of downloads)
```

How it is built, every source, the year slider and the known limits: [AMSTERDAM.md](AMSTERDAM.md).

Camera presets: `?view=` overview, dam, westerkerk, rijksmuseum, munttoren, zuiderkerk, centraal, canals, city.

## Sources

- **AHN** (Actueel Hoogtebestand Nederland) heights, **PDOK** aerial photos, **BGT** large-scale topography and
  **Kadaster's 3D Basisvoorziening** 20 cm surface model (CC0 / CC BY 4.0)
- **3D BAG** (TU Delft 3D geoinformation group, CC BY 4.0) and the **BAG** construction years
- **Gemeente Amsterdam** open data: the tree register, historical soil information (filled-in canals)
- **Stadsarchief Amsterdam**, Beeldbank: copyright-free photos, prints and drawings (linked, not copied)
- **Amsterdam Time Machine**: the historical town plans 1625-1985 (Webmapper, Jan Hartmann / UvA)
- **OpenStreetMap** © OpenStreetMap contributors (ODbL), **Wikidata** (CC0) and Wikipedia page views

## Credits

A port of [stared/warsaw-vibe-voxel](https://github.com/stared/warsaw-vibe-voxel) by Piotr Migdał (MIT), whose
pipeline and viewer do most of the work; its original README is in [README.warsaw.md](README.warsaw.md).
