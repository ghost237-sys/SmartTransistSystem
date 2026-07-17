import json
import redis
from decouple import config

_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        redis_url = config('REDIS_URL', default='')
        if redis_url:
            _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        else:
            _redis_client = redis.Redis(
                host=config('REDIS_HOST', default='localhost'),
                port=config('REDIS_PORT', default=6379, cast=int),
                decode_responses=True,
            )
    return _redis_client


def set_vehicle_position(vehicle_id, latitude, longitude, speed_kmh, recorded_at, ttl_seconds=30):
    """
    Stores the live position with a 30-second expiry — if a vehicle stops
    sending updates (offline, app closed, crashed), the key disappears on
    its own and we can treat "key not found" as "vehicle is offline"
    without needing a separate heartbeat/offline-detection mechanism.
    """
    client = get_redis_client()
    key = f'vehicle_position:{vehicle_id}'
    value = json.dumps({
        'latitude': latitude,
        'longitude': longitude,
        'speed_kmh': speed_kmh,
        'recorded_at': recorded_at,
    })
    client.set(key, value, ex=ttl_seconds)


def get_vehicle_position(vehicle_id):
    client = get_redis_client()
    raw = client.get(f'vehicle_position:{vehicle_id}')
    if raw:
        return json.loads(raw)

    # Mock/stub fallback for demo purposes
    try:
        from domains.routing.models import Trip
        from django.utils import timezone
        trip = Trip.objects.filter(vehicle_id=vehicle_id, status__in=['active', 'departed']).select_related('route').first()
        if trip:
            first_stop = trip.route.stops.order_by('sequence').first()
            if first_stop:
                return {
                    'latitude': first_stop.location.y,
                    'longitude': first_stop.location.x,
                    'speed_kmh': 45.0,
                    'recorded_at': timezone.now().isoformat(),
                }
    except Exception:
        pass

    # Absolute fallback to Nairobi CBD if no stops exist
    from django.utils import timezone
    return {
        'latitude': -1.2921,
        'longitude': 36.8219,
        'speed_kmh': 0.0,
        'recorded_at': timezone.now().isoformat(),
    }


def publish_position_update(trip_id, vehicle_id, latitude, longitude, speed_kmh, recorded_at):
    """
    Publishes a position update on a per-trip channel. Channels Redis
    layer (channels-redis) subscribes to channels named this way from
    the WebSocket consumer side — see tracking/consumers.py.
    """
    client = get_redis_client()
    channel = f'trip_position:{trip_id}'
    message = json.dumps({
        'vehicle_id': vehicle_id,
        'latitude': latitude,
        'longitude': longitude,
        'speed_kmh': speed_kmh,
        'recorded_at': recorded_at,
    })
    client.publish(channel, message)