import json
import redis
from decouple import config

_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=config('REDIS_HOST'),
            port=config('REDIS_PORT', cast=int),
            decode_responses=True,
        )
    return _redis_client


def set_vehicle_position(vehicle_id, latitude, longitude, speed_kmh, recorded_at):
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
    client.set(key, value, ex=30)


def get_vehicle_position(vehicle_id):
    client = get_redis_client()
    raw = client.get(f'vehicle_position:{vehicle_id}')
    return json.loads(raw) if raw else None


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