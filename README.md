[README.md](https://github.com/user-attachments/files/33644096/README.md)
# Park Access Analysis

**How many residents live within a 10-minute walk of a park?**

A Python tool that measures walkable park access using the real street and path network, OpenStreetMap park data, and 2020 Census block populations. It runs end to end with one command for any U.S. place.

![Lake Bluff park access map](outputs/lake_bluff/park_access_map.png)

## Key finding: Lake Bluff, Illinois

| Measure | Result |
| --- | --- |
| Parks analyzed | 8 |
| Residents within a 10-minute walk of a park | 2,663 of 5,621 (**47.4%**) |
| Village land area within a 10-minute walk of a park | 24.7% |

Nearly half of Lake Bluff's residents live within a 10-minute walk of a park, even though only about a quarter of the village's area does. The gap shows that the parks sit in or near the more densely populated neighborhoods, while much of the land outside the walk areas has fewer residents (larger lots, open land, and non-residential areas). It also shows why measuring access by **people** rather than **area** matters.

## Method

1. **Parks and boundary.** Download the place boundary and all park polygons (`leisure=park`) from OpenStreetMap with OSMnx.
2. **Walking network.** Download every walkable street and path within the boundary plus a 1,000 m buffer, so routes that leave and re-enter the boundary are kept. Project to the local UTM zone so distances are in meters.
3. **Walk times.** Convert each street segment's length to walking minutes at 80 m/min (about 3 mph).
4. **Walk areas.** Run a multi-source Dijkstra shortest-path search from the network node nearest each park, keeping every node reachable within 10 minutes. Buffer the reachable streets by 50 m and dissolve them into one walk-area polygon.
5. **Population.** Download 2020 Census blocks with their population (`POP20`). Keep blocks inside the boundary, and flag a block as served if its representative point falls inside the walk area.
6. **Outputs.** Calculate the share of residents served, and save a map, a CSV table, and GeoPackages for GIS software.

## How to run it

**1. Set up the environment** (one time, using [Miniforge](https://github.com/conda-forge/miniforge)):

```
conda create -n parks -c conda-forge python=3.11 geopandas osmnx matplotlib folium mapclassify jupyterlab
conda activate parks
pip install pygris
```

**2. Run the script** for any place, giving the state and the county the place is in:

```
python park_access.py "Lake Bluff, Illinois, USA" --state IL --county Lake
```

Optional settings:

```
--minutes 15    walk time in minutes (default 10)
--speed 75      walking speed in meters per minute (default 80)
```

Results print in the terminal and are saved to `outputs/<place_name>/`.

## Repository contents

| File | Purpose |
| --- | --- |
| `park_access.py` | The complete, reusable analysis as one command-line script |
| `01_download_parks.ipynb` | Development notebook: downloading and cleaning park data |
| `02_walk_areas.ipynb` | Development notebook: building the walking network and walk areas |
| `03_population_access.ipynb` | Development notebook: Census blocks and population access |
| `outputs/lake_bluff/` | Map, CSV table, and GeoPackages for Lake Bluff |

The notebooks document how the analysis was built step by step. The script reproduces their result exactly (47.4%), which served as a regression test.

## Quality checks

- Park polygons, walk areas, and served blocks were each reviewed in QGIS over an OpenStreetMap basemap.
- An early version downloaded the network only inside the village boundary. This disconnected a section of the village reached by roads outside the boundary and placed one park's walk area in the wrong location. Adding the 1,000 m network buffer fixed it.

## Limitations

- **Park data.** Only features tagged `leisure=park` in OpenStreetMap are included. Beaches, school grounds, and nature preserves tagged differently are not, so access may be underestimated.
- **Park entrances.** Walk times are measured from the network point nearest each park's center. This underestimates access to large parks, which people can enter from any edge. Using points along park boundaries would be more precise.
- **Block assignment.** Each block counts as entirely served or not, based on one representative point. Areal weighting (splitting a block's population by the share of its area inside the walk area) would be more precise.
- **Edge effects.** Parks just outside the boundary are not counted, though nearby residents may use them.
- **Single county.** The script assumes the place lies within one county.

## Tools and data

- **Python:** GeoPandas, OSMnx, NetworkX, pygris, Matplotlib
- **QGIS** for visual quality checks
- **OpenStreetMap** park and street data, © OpenStreetMap contributors (ODbL)
- **U.S. Census Bureau** 2020 TIGER/Line census blocks

## Author

**Jessica Keller**
GIS portfolio: [ArcGIS StoryMaps](ADD-YOUR-STORYMAP-LINK-HERE)
