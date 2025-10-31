"""Compute walkability scores aggregated by an area field (e.g., `sa4`).

Writes CSV to `outputs/per_area_scores.csv` and prints a brief summary.

Usage:
    PYTHONPATH=. python scripts/per_area_scores.py --field sa4
"""
import argparse
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd

# Ensure the repository root is on sys.path so this script can be run directly
# (without requiring PYTHONPATH to be set externally).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.walkability import load_gpkg, compute_walkability_score, compute_road_length_density


def ensure_projected(gdf):
    if gdf is None or gdf.empty:
        return gdf
    if gdf.crs is None:
        return gdf
    if getattr(gdf.crs, 'is_geographic', False):
        return gdf.to_crs(epsg=3857)
    return gdf


def compute_per_area(roads_fp, cad_fp, field='sa4'):
    cad = load_gpkg(str(cad_fp))
    roads = load_gpkg(str(roads_fp))

    # ensure projected
    cad = ensure_projected(cad)
    roads = ensure_projected(roads)

    if field not in cad.columns:
        raise ValueError(f'Field "{field}" not found in cadastre columns: {list(cad.columns)}')

    results = []
    groups = cad.groupby(field)
    for name, grp in groups:
        try:
            area_geom = grp.unary_union
            # clip datasets
            cad_clip = gpd.clip(cad, gpd.GeoSeries([area_geom], crs=cad.crs))
            roads_clip = gpd.clip(roads, gpd.GeoSeries([area_geom], crs=roads.crs))
            score = compute_walkability_score(roads_clip, cad_clip, area_geom=area_geom)
            results.append({
                field: name,
                'score': score,
                'n_parcels': len(cad_clip),
                'road_km_per_km2': compute_road_length_density(roads_clip) if len(roads_clip)>0 else 0.0,
            })
        except Exception as e:
            results.append({field: name, 'score': None, 'error': str(e)})

    df = pd.DataFrame(results)
    return df


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--field', default='sa4', help='Cadastre attribute to aggregate by (default: sa4)')
    args = p.parse_args()

    root = Path('.').resolve()
    data_dir = root / 'data'
    roads_fp = data_dir / 'roads.gpkg'
    cad_fp = data_dir / 'cadastre.gpkg'

    out_dir = root / 'outputs'
    out_dir.mkdir(exist_ok=True)

    df = compute_per_area(roads_fp, cad_fp, field=args.field)
    out_fp = out_dir / f'per_area_scores_{args.field}.csv'
    df.to_csv(out_fp, index=False)
    print('Wrote', out_fp)

    # print top areas
    print('\nTop 10 by score:')
    print(df.dropna(subset=['score']).sort_values('score', ascending=False).head(10).to_string(index=False))


if __name__ == '__main__':
    main()
