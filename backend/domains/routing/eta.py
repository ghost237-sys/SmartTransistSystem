from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from domains.tracking.redis_client import get_vehicle_position


def estimate_arrival(trip, stop):
    """
    Rough ETA: straight-line distance from the vehicle's last known
    position to the target stop, divided by current speed (falling back
    to a conservative average if speed is zero/unknown — e.g. stopped
    at a previous stage). Returns None if we have no live position at
    all (vehicle offline / Redis key expired).
    """
    position = get_vehicle_position(str(trip.vehicle_id))
    if position is None:
        return None

    vehicle_point = Point(position['longitude'], position['latitude'], srid=4326)

    # transform to a metric SRID for an accurate distance in meters;
    # 4326 (plain lat/lng) doesn't give meaningful distances directly
    distance_meters = vehicle_point.transform(3857, clone=True).distance(
        stop.location.transform(3857, clone=True)
    )

    speed_kmh = position.get('speed_kmh') or 20  # conservative fallback: matatu average urban speed
    if speed_kmh <= 0:
        speed_kmh = 20

    speed_ms = speed_kmh * 1000 / 3600
    eta_seconds = distance_meters / speed_ms

    return {
        'distance_km': round(distance_meters / 1000, 2),
        'eta_minutes': round(eta_seconds / 60, 1),
    }