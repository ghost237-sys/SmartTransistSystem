from django.contrib.gis.geos import Point

# How close a commuter must be to a route stop to see that line (urban corridors).
COMMUTER_ROUTE_RADIUS_KM = 8


def distance_km_between(point_a, point_b):
    return point_a.transform(3857, clone=True).distance(
        point_b.transform(3857, clone=True)
    ) / 1000


def nearest_stop_to_point(point, stops):
    """Return (stop, distance_km) for the closest stop in the queryset/list."""
    nearest_stop = None
    nearest_distance = float('inf')

    for stop in stops:
        if not stop.location:
            continue
        dist = distance_km_between(point, stop.location)
        if dist < nearest_distance:
            nearest_distance = dist
            nearest_stop = stop

    if nearest_stop is None:
        return None, None
    return nearest_stop, round(nearest_distance, 2)
