"""
park_access.py

Measures what share of a place's residents live within a short walk of a park.

Steps:
  1. Download the place boundary and park polygons from OpenStreetMap.
  2. Download the walking network (plus a buffer around the boundary).
  3. Build walk areas: every street reachable within N minutes of a park.
  4. Count 2020 Census block population inside vs. outside the walk areas.
  5. Save a map, a CSV table, and GeoPackages for QGIS.

Usage (run from the park-access folder, with the parks environment active):
    python park_access.py "Lake Bluff, Illinois, USA" --state IL --county Lake

Optional settings:
    --minutes 15     walk time in minutes (default 10)
    --speed 75       walking speed in meters per minute (default 80, about 3 mph)
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import pygris

# Overpass server settings (see Step 6a in the guide)
ox.settings.overpass_url = "https://overpass-api.de/api"
ox.settings.requests_timeout = 300


def get_boundary_and_parks(place):
    """Download the place boundary and park polygons from OpenStreetMap."""
    boundary = ox.geocode_to_gdf(place)

    parks = ox.features_from_place(place, tags={"leisure": "park"})
    parks = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])]
    parks = parks.reset_index()
    if "name" not in parks.columns:
        parks["name"] = None
    parks = parks[["name", "geometry"]]

    return boundary, parks


def build_network(boundary, utm_crs, buffer_m=1000):
    """Download the walking network for the boundary plus a buffer, in meters."""
    area = boundary.to_crs(utm_crs).buffer(buffer_m).to_crs(epsg=4326).union_all()
    G = ox.graph_from_polygon(area, network_type="walk")
    return ox.project_graph(G, to_crs=utm_crs)


def build_walk_area(G, parks_proj, minutes, speed, street_buffer_m=50):
    """Return one polygon covering every street within `minutes` of a park."""
    # Minutes to walk each street segment
    for u, v, k, data in G.edges(keys=True, data=True):
        data["walk_time"] = data["length"] / speed

    # Nearest network node to each park's center
    centroids = parks_proj.geometry.centroid
    park_nodes = ox.distance.nearest_nodes(G, X=centroids.x, Y=centroids.y)

    # Shortest walk time from every node to its nearest park
    reach_times = nx.multi_source_dijkstra_path_length(
        G, set(park_nodes), cutoff=minutes, weight="walk_time"
    )

    # Buffer the reachable streets and dissolve them into one polygon
    reachable = G.subgraph(reach_times.keys())
    edges = ox.graph_to_gdfs(reachable, nodes=False)
    walk_area = edges.buffer(street_buffer_m).union_all()

    return gpd.GeoDataFrame(geometry=[walk_area], crs=G.graph["crs"])


def get_blocks_with_access(boundary_proj, walk_area, state, county):
    """Download 2020 Census blocks and flag the ones inside the walk area."""
    blocks = pygris.blocks(state=state, county=county, year=2020, cache=True)
    blocks = blocks.to_crs(boundary_proj.crs)

    # Keep blocks whose representative point is inside the boundary
    points = blocks.representative_point()
    blocks = blocks[points.within(boundary_proj.union_all())].copy()

    # True if the block's representative point is inside the walk area
    blocks["served"] = blocks.representative_point().within(walk_area.union_all())

    return blocks


def make_map(boundary_proj, blocks, parks_proj, title, path):
    """Save a map of served (gold) and unserved (grey) blocks."""
    ax = boundary_proj.plot(color="none", edgecolor="black", figsize=(8, 8))
    blocks[blocks["served"]].plot(ax=ax, color="gold", edgecolor="white", linewidth=0.3)
    blocks[~blocks["served"]].plot(ax=ax, color="lightgrey", edgecolor="white", linewidth=0.3)
    parks_proj.plot(ax=ax, color="green")
    ax.set_title(title)
    ax.set_axis_off()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()


def main():
    # Read the settings typed on the command line
    parser = argparse.ArgumentParser(description="Measure walkable park access.")
    parser.add_argument("place", help='e.g. "Lake Bluff, Illinois, USA"')
    parser.add_argument("--state", required=True, help="state abbreviation, e.g. IL")
    parser.add_argument("--county", required=True, help="county name, e.g. Lake")
    parser.add_argument("--minutes", type=float, default=10, help="walk time (default 10)")
    parser.add_argument("--speed", type=float, default=80, help="meters per minute (default 80)")
    args = parser.parse_args()

    # Make an output folder named after the place, e.g. outputs/lake_bluff
    slug = args.place.split(",")[0].strip().lower().replace(" ", "_")
    out_dir = Path("outputs") / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"1/5 Downloading boundary and parks for {args.place}...")
    boundary, parks = get_boundary_and_parks(args.place)
    if parks.empty:
        print("No parks found in OpenStreetMap for this place. Stopping.")
        return
    print(f"    Found {len(parks)} parks.")

    # Pick the right UTM zone for this place automatically (units in meters)
    utm_crs = boundary.estimate_utm_crs()
    boundary_proj = boundary.to_crs(utm_crs)
    parks_proj = parks.to_crs(utm_crs)

    print("2/5 Downloading the walking network...")
    G = build_network(boundary, utm_crs)

    print(f"3/5 Building {args.minutes:g}-minute walk areas...")
    walk_area = build_walk_area(G, parks_proj, args.minutes, args.speed)

    print("4/5 Downloading 2020 Census blocks (can take a few minutes)...")
    blocks = get_blocks_with_access(boundary_proj, walk_area, args.state, args.county)

    served_pop = blocks.loc[blocks["served"], "POP20"].sum()
    total_pop = blocks["POP20"].sum()
    pct = served_pop / total_pop * 100 if total_pop else 0

    print("5/5 Saving outputs...")
    place_name = args.place.split(",")[0].strip()
    title = f"{place_name}: blocks within a {args.minutes:g}-minute walk of a park (gold)"
    make_map(boundary_proj, blocks, parks_proj, title, out_dir / "park_access_map.png")
    blocks.to_file(out_dir / "blocks_access.gpkg")
    walk_area.to_file(out_dir / "walk_area.gpkg")
    parks_proj.to_file(out_dir / "parks.gpkg")
    blocks[["GEOID20", "POP20", "served"]].to_csv(out_dir / "block_access.csv", index=False)

    print()
    print(f"Result: {served_pop:,} of {total_pop:,} residents ({pct:.1f}%) live within")
    print(f"a {args.minutes:g}-minute walk of a park in {place_name}.")
    print(f"Outputs saved to {out_dir}/")


# Run main() only when this file is run directly, not when it's imported
if __name__ == "__main__":
    main()
