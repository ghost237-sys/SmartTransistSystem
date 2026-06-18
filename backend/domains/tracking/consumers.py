import json
from channels.generic.websocket import AsyncWebsocketConsumer


class TripTrackingConsumer(AsyncWebsocketConsumer):
    """
    Commuters connect to ws/trip/<trip_id>/tracking/ to receive live
    position updates for that specific trip. Joins the Channels group
    'trip_<trip_id>', the same group name broadcast_position_update()
    sends to.
    """
    async def connect(self):
        self.trip_id = self.scope['url_route']['kwargs']['trip_id']
        self.group_name = f'trip_{self.trip_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def position_update(self, event):
        """
        Handler name matches the 'type' key sent in group_send
        ('position.update' -> position_update, Channels converts dots
        to underscores when routing to handler methods).
        """
        await self.send(text_data=json.dumps({
            'vehicle_id': event['vehicle_id'],
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'speed_kmh': event['speed_kmh'],
            'recorded_at': event['recorded_at'],
        }))