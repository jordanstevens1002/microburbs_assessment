# Walkability / Liveability analysis

This repository contains a minimal setup to compute a simple walkability
score from provided geospatial data (roads and cadastre).

What I added:
- `requirements.txt` — geospatial Python dependencies
- `src/walkability.py` — core functions to compute metrics and a combined score
- `scripts/run_analysis.py` — small CLI to run the analysis against `data/`
- `tests/test_walkability.py` — pytest tests for core logic

How to use (recommended in a virtualenv):

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run a quick analysis (expects `data/roads.gpkg` and `data/cadastre.gpkg`):

```bash
python scripts/run_analysis.py
```

Notes:
- The scoring functions expect projected CRS (meters). If your data are in
  geographic coordinates, the CLI attempts to reproject to EPSG:3857.
- Intersection detection in `compute_intersection_density` is a simple
  O(n^2) approach and should be improved for large networks (use spatial
  indexing / node extraction).

Next steps (suggested):
- Add more metrics (amenities, transit stops, land use mix).
- Improve performance for large datasets (use rtree and spatial joins).
- Tune normalization scales to local benchmarks.
