import time
import random
import logging
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.db import connections

logger = logging.getLogger(__name__)

# Global state to keep track of trip positions
# format: {trip_id: {'segment_idx': int, 'step_idx': int}}
TRIP_STATES = {}

def interpolate_point(start, end, t):
    """Linear interpolation between start (lat, lng) and end (lat, lng)."""
    lat = start[0] + (end[0] - start[0]) * t
    lng = start[1] + (end[1] - start[1]) * t
    return lat, lng

def start_gps_simulation():
    """Background loop to simulate vehicle movements along active trips."""
    logger.info("Initializing background GPS simulator thread...")
    # Give the server a few seconds to fully initialize
    time.sleep(5)
    
    steps_per_segment = 10
    
    while True:
        try:
            from domains.routing.models import Trip
            from domains.tracking.redis_client import set_vehicle_position, publish_position_update
            from domains.tracking.models import VehiclePosition
            
            # Query active/departed trips
            active_trips = list(Trip.objects.filter(
                status__in=['active', 'departed']
            ).select_related('route', 'vehicle'))
            
            active_trip_ids = {str(trip.id) for trip in active_trips}
            
            # Clean up old trip states
            for tid in list(TRIP_STATES.keys()):
                if tid not in active_trip_ids:
                    TRIP_STATES.pop(tid, None)
                    
            for trip in active_trips:
                trip_id = str(trip.id)
                stops = list(trip.route.stops.order_by('sequence'))
                if len(stops) < 2:
                    continue
                
                waypoints = [(stop.location.y, stop.location.x) for stop in stops]
                
                # Get or initialize state
                if trip_id not in TRIP_STATES:
                    TRIP_STATES[trip_id] = {'segment_idx': 0, 'step_idx': 0}
                    
                state = TRIP_STATES[trip_id]
                segment_idx = state['segment_idx']
                step_idx = state['step_idx']
                
                # Safety check in case stops changed
                if segment_idx >= len(waypoints) - 1:
                    segment_idx = 0
                    step_idx = 0
                    
                start_pt = waypoints[segment_idx]
                end_pt = waypoints[segment_idx + 1]
                t_val = step_idx / steps_per_segment
                
                lat, lng = interpolate_point(start_pt, end_pt, t_val)
                speed = round(random.uniform(30.0, 55.0), 1)
                now_str = timezone.now().isoformat()
                
                # Update Redis
                set_vehicle_position(
                    vehicle_id=str(trip.vehicle_id),
                    latitude=lat,
                    longitude=lng,
                    speed_kmh=speed,
                    recorded_at=now_str,
                    ttl_seconds=30
                )
                
                # Broadcast WS
                publish_position_update(
                    trip_id=trip_id,
                    vehicle_id=str(trip.vehicle_id),
                    latitude=lat,
                    longitude=lng,
                    speed_kmh=speed,
                    recorded_at=now_str
                )
                
                # Write to DB history log
                VehiclePosition.objects.create(
                    vehicle_id=trip.vehicle_id,
                    trip_id=trip.id,
                    location=Point(lng, lat, srid=4326),
                    speed_kmh=speed,
                    recorded_at=timezone.now()
                )
                
                # Increment step/segment
                step_idx += 1
                if step_idx >= steps_per_segment:
                    step_idx = 0
                    segment_idx += 1
                    if segment_idx >= len(waypoints) - 1:
                        segment_idx = 0
                        
                state['segment_idx'] = segment_idx
                state['step_idx'] = step_idx
                
        except Exception as e:
            logger.error(f"Error in background GPS simulation loop: {e}", exc_info=True)
            
        finally:
            # Prevent connection leak in background threads
            connections.close_all()
            
        time.sleep(5)
