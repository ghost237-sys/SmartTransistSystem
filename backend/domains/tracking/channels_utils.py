from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_position_update(trip_id, vehicle_id, latitude, longitude, speed_kmh, recorded_at):
    """
    Sends a position update to the Channels group for this trip.
    Any WebSocket consumer that has joined group 'trip_<trip_id>'
    (see tracking/consumers.py) will receive this as a message.

    async_to_sync is required here because this function is called from
    a synchronous Django view (APIView.post is sync), but Channels'
    channel_layer API is async-native.
    """
    channel_layer = get_channel_layer()
    group_name = f'trip_{trip_id}'

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'position.update',
            'vehicle_id': vehicle_id,
            'latitude': latitude,
            'longitude': longitude,
            'speed_kmh': speed_kmh,
            'recorded_at': recorded_at,
        }
    )