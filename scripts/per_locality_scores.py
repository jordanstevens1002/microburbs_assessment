"""Compute walkability scores per locality using G-NAF points.

Approach:
- Read `data/gnaf_prop.parquet` (parquet read via pandas + pyarrow)
- Convert WKB hex in `geom` column to shapely geometries and create a GeoDataFrame
- Group by `locality_name` (or user-specified field), build a convex hull + buffer around points
- Clip roads and cadastre to that area and compute a walkability score

Outputs CSV to `outputs/per_locality_scores_<field>.csv`.
"""
import argparse
import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely import wkb

# ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.walkability import compute_walkability_score, load_gpkg, compute_road_length_density


def points_from_parquet(parquet_fp, geom_col='geom'):
    df = pd.read_parquet(parquet_fp)
    # geom stored as hex WKB strings
    geom_series = df[geom_col].apply(lambda s: wkb.loads(bytes.fromhex(s)) if pd.notna(s) else None)
    gdf = gpd.GeoDataFrame(df, geometry=geom_series, crs='EPSG:4326')
    return gdf


def ensure_projected(gdf):
    if gdf is None or gdf.empty:
        return gdf
    if gdf.crs is None:
        return gdf
    if getattr(gdf.crs, 'is_geographic', False):
        return gdf.to_crs(epsg=3857)
    return gdf


def compute_per_locality(gnaf_fp, roads_fp, cad_fp, field='locality_name', buffer_m=500, min_points=5):
    gnaf = points_from_parquet(gnaf_fp)
    roads = load_gpkg(str(roads_fp))
    cad = load_gpkg(str(cad_fp))

    gnaf = ensure_projected(gnaf)
    roads = ensure_projected(roads)
    cad = ensure_projected(cad)

    if field not in gnaf.columns:
        raise ValueError(f'Field "{field}" not found in G-NAF columns: {list(gnaf.columns)}')

    results = []
    groups = gnaf.groupby(field)
    for name, grp in groups:
        if len(grp) < min_points:
            # skip very small localities
            continue
        try:
            pts_union = grp.geometry.unary_union
            area_geom = pts_union.convex_hull.buffer(buffer_m)
            # clip
            cad_clip = cad[cad.intersects(area_geom)]
            roads_clip = roads[roads.intersects(area_geom)]
            score = compute_walkability_score(roads_clip, cad_clip, area_geom=area_geom)
            results.append({
                field: name,
                'n_points': len(grp),
                'score': score,
                'n_parcels': len(cad_clip),
                'road_km_per_km2': compute_road_length_density(roads_clip) if len(roads_clip)>0 else 0.0,
            })
        except Exception as e:
            results.append({field: name, 'score': None, 'error': str(e)})

    return pd.DataFrame(results)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--field', default='locality_name')
    p.add_argument('--buffer', type=float, default=500.0)
    p.add_argument('--min-points', type=int, default=5)
    args = p.parse_args()

    root = Path('.').resolve()
    data_dir = root / 'data'
    gnaf_fp = data_dir / 'gnaf_prop.parquet'
    roads_fp = data_dir / 'roads.gpkg'
    cad_fp = data_dir / 'cadastre.gpkg'

    out_dir = root / 'outputs'
    out_dir.mkdir(exist_ok=True)

    df = compute_per_locality(gnaf_fp, roads_fp, cad_fp, field=args.field, buffer_m=args.buffer, min_points=args.min_points)
    out_fp = out_dir / f'per_locality_scores_{args.field}.csv'
    df.to_csv(out_fp, index=False)
    print('Wrote', out_fp)
    print('\nTop 10 by score:')
    print(df.dropna(subset=['score']).sort_values('score', ascending=False).head(10).to_string(index=False))


if __name__ == '__main__':
    main()
