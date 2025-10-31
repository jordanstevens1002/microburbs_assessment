"""Simple CLI to run walkability analysis on provided data files.

Usage (example):
    python scripts/run_analysis.py

This script loads `data/roads.gpkg` and `data/cadastre.gpkg`, computes a
walkability score for the full extent, and prints a summary.
"""
import sys
from pathlib import Path

import geopandas as gpd

from src.walkability import load_gpkg, compute_walkability_score


def main():
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    roads_fp = data_dir / "roads.gpkg"
    cad_fp = data_dir / "cadastre.gpkg"

    if not roads_fp.exists() or not cad_fp.exists():
        print(f"Expected files not found in {data_dir}. Found: {list(data_dir.iterdir())}")
        sys.exit(1)

    print("Loading roads...")
    roads = load_gpkg(str(roads_fp))
    print("Loading cadastre...")
    cad = load_gpkg(str(cad_fp))

    # ensure projected CRS; if geographic, attempt a reasonable projection
    if roads.crs and roads.crs.is_geographic:
        roads = roads.to_crs(epsg=3857)
    if cad.crs and cad.crs.is_geographic:
        cad = cad.to_crs(epsg=3857)

    score = compute_walkability_score(roads, cad)
    print("Walkability score (0-100):", round(score, 2))


if __name__ == "__main__":
    main()
