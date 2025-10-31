import pytest
from shapely.geometry import LineString, Polygon
import geopandas as gpd

from src.walkability import compute_road_length_density, compute_intersection_density, compute_parcel_density, compute_walkability_score


def make_roads():
    # cross shaped roads within a 1000m x 1000m square
    l1 = LineString([(0, 500), (1000, 500)])
    l2 = LineString([(500, 0), (500, 1000)])
    return gpd.GeoDataFrame(geometry=[l1, l2], crs="EPSG:3857")


def make_parcels():
    # create 4 parcels in the square
    p1 = Polygon([(0, 0), (500, 0), (500, 500), (0, 500)])
    p2 = Polygon([(500, 0), (1000, 0), (1000, 500), (500, 500)])
    p3 = Polygon([(0, 500), (500, 500), (500, 1000), (0, 1000)])
    p4 = Polygon([(500, 500), (1000, 500), (1000, 1000), (500, 1000)])
    return gpd.GeoDataFrame(geometry=[p1, p2, p3, p4], crs="EPSG:3857")


def test_metrics_and_score_range():
    roads = make_roads()
    parcels = make_parcels()

    rd = compute_road_length_density(roads)
    assert rd > 0

    idens = compute_intersection_density(roads)
    assert idens > 0

    pd = compute_parcel_density(parcels)
    assert pd > 0

    score = compute_walkability_score(roads, parcels)
    assert 0.0 <= score <= 100.0


def test_more_intersections_increase_score():
    roads = make_roads()
    parcels = make_parcels()
    base_score = compute_walkability_score(roads, parcels)

    # add diagonal roads to increase intersections
    diag = LineString([(0, 0), (1000, 1000)])
    import geopandas as gpd
    roads2 = gpd.GeoDataFrame({'geometry': [diag]}, crs=roads.crs)
    roads2 = gpd.pd.concat([roads, roads2], ignore_index=True)
    s2 = compute_walkability_score(roads2, parcels)
    assert s2 >= base_score
