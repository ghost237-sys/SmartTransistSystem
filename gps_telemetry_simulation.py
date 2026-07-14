"""
GPS Telemetry Simulation for Public Transit App
================================================
A self-contained simulation script that demonstrates real-time GPS telemetry
with manual state machine triggers for a public transit booking system.

Requirements: pip install fastapi uvicorn
Run with: uvicorn gps_telemetry_simulation:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import math
from enum import Enum
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import time
from datetime import datetime

# =============================================================================
# STATE MACHINE DEFINITION
# =============================================================================

class BookingState(str, Enum):
    """Strict state machine for commuter booking session"""
    IDLE = "IDLE"
    SEARCHING = "SEARCHING"
    MATCHED = "MATCHED"
    EN_ROUTE = "EN_ROUTE"
    BOARDED = "BOARDED"
    DELAYED = "DELAYED"
    COMPLETED = "COMPLETED"


# =============================================================================
# GLOBAL IN-MEMORY DATA STORE
# =============================================================================

class SimulationState:
    """Global simulation state - in-memory data store"""
    
    def __init__(self):
        # State machine
        self.current_state = BookingState.IDLE
        
        # Vehicle position and movement
        self.vehicle_lat = 0.0
        self.vehicle_lng = 0.0
        self.current_route_index = 0
        self.base_speed = 0.0003  # Degrees per tick (approx 30m per second at equator)
        self.current_speed = self.base_speed
        self.is_delayed = False
        
        # User position
        self.user_lat = 0.0
        self.user_lng = 0.0
        
        # Route waypoints (Nairobi CBD to Westlands route example)
        self.route_coordinates = [
            (-1.286389, 36.817223),  # Nairobi CBD (Kenya Cinema)
            (-1.285000, 36.819000),  # Moi Avenue
            (-1.283500, 36.821000),  # University Way
            (-1.281500, 36.823500),  # Museum Hill
            (-1.279000, 36.826000),  # Westlands Road
            (-1.276500, 36.828500),  # Sarit Centre area
            (-1.274000, 36.831000),  # Mpaka Road
            (-1.271500, 36.833500),  # General Mathenge
            (-1.269000, 36.836000),  # Waiyaki Way
            (-1.266500, 36.838500),  # Westlands Terminal
        ]
        
        # User stage (pickup point)
        self.user_stage_lat = -1.279000  # Museum Hill
        self.user_stage_lng = 36.826000
        
        # Initialize positions
        self.vehicle_lat = self.route_coordinates[0][0]
        self.vehicle_lng = self.route_coordinates[0][1]
        self.user_lat = self.user_stage_lat
        self.user_lng = self.user_stage_lng
        
        # Simulation control
        self.simulation_running = True
        self.last_update_time = datetime.now()
        
        # Statistics
        self.total_distance_traveled = 0.0
        self.delay_duration = 0.0


# Global instance
sim_state = SimulationState()


# =============================================================================
# GPS SIMULATION ENGINE
# =============================================================================

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    Returns distance in meters.
    """
    R = 6371000  # Earth's radius in meters
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def interpolate_position(
    start_lat: float, 
    start_lng: float, 
    end_lat: float, 
    end_lng: float, 
    progress: float
) -> tuple[float, float]:
    """
    Interpolate position between two coordinates based on progress (0.0 to 1.0).
    Uses linear interpolation for simplicity.
    """
    lat = start_lat + (end_lat - start_lat) * progress
    lng = start_lng + (end_lng - start_lng) * progress
    return lat, lng


def gps_simulation_loop():
    """
    Background thread that continuously updates vehicle position along the route.
    Runs independently of the state machine - vehicle always moves.
    """
    print("🚀 GPS Simulation Engine Started")
    
    while sim_state.simulation_running:
        try:
            # Get current and next waypoint
            current_idx = sim_state.current_route_index
            
            # Check if we've reached the end of the route
            if current_idx >= len(sim_state.route_coordinates) - 1:
                # Loop back to start for continuous simulation
                sim_state.current_route_index = 0
                current_idx = 0
            
            start_lat, start_lng = sim_state.route_coordinates[current_idx]
            end_lat, end_lng = sim_state.route_coordinates[current_idx + 1]
            
            # Calculate segment distance
            segment_distance = haversine_distance(start_lat, start_lng, end_lat, end_lng)
            
            # Calculate progress increment based on speed
            # Speed is in degrees per tick, convert to progress (0-1)
            if segment_distance > 0:
                # Convert speed from degrees to meters for this calculation
                speed_meters_per_tick = sim_state.current_speed * 111000  # Approx conversion
                progress_increment = speed_meters_per_tick / segment_distance
            else:
                progress_increment = 1.0
            
            # Track progress within segment (simplified - we just move toward next waypoint)
            # For smoother movement, we'd need to track segment progress, but for demo
            # we'll move incrementally toward the next waypoint
            
            # Calculate current position by moving toward next waypoint
            lat_diff = end_lat - start_lat
            lng_diff = end_lng - start_lng
            
            # Normalize direction
            distance = math.sqrt(lat_diff ** 2 + lng_diff ** 2)
            if distance > 0:
                move_factor = sim_state.current_speed / distance
                sim_state.vehicle_lat += lat_diff * move_factor
                sim_state.vehicle_lng += lng_diff * move_factor
            
            # Check if we've reached the next waypoint
            dist_to_next = haversine_distance(
                sim_state.vehicle_lat, 
                sim_state.vehicle_lng, 
                end_lat, 
                end_lng
            )
            
            if dist_to_next < 10:  # Within 10 meters of waypoint
                sim_state.current_route_index += 1
                print(f"📍 Reached waypoint {sim_state.current_route_index}/{len(sim_state.route_coordinates)}")
            
            # Update user position if boarded (snap to vehicle)
            if sim_state.current_state == BookingState.BOARDED:
                sim_state.user_lat = sim_state.vehicle_lat
                sim_state.user_lng = sim_state.vehicle_lng
            
            # Track statistics
            sim_state.total_distance_traveled += sim_state.current_speed * 111000
            
            # Update timestamp
            sim_state.last_update_time = datetime.now()
            
        except Exception as e:
            print(f"❌ Error in GPS simulation: {e}")
        
        # Sleep for 1 second (fixed interval)
        time.sleep(1)


# =============================================================================
# API MODELS
# =============================================================================

class StateTransitionRequest(BaseModel):
    """Request model for state transitions"""
    target_state: BookingState


class TelemetryResponse(BaseModel):
    """Response model for telemetry data"""
    timestamp: str
    state: str
    vehicle: dict
    user: dict
    user_stage: dict
    eta: Optional[float] = None
    is_delayed: bool
    distance_to_user: Optional[float] = None
    total_distance_traveled: float


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="GPS Telemetry Simulation",
    description="Real-time GPS telemetry simulation for public transit app",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# MANUAL STATE TRANSITION ENDPOINTS
# =============================================================================

@app.post("/api/trigger/match")
async def trigger_match():
    """
    Manual trigger: Transition from SEARCHING to MATCHED state.
    Simulates vehicle matching with user's request.
    """
    if sim_state.current_state != BookingState.SEARCHING:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger MATCH from state {sim_state.current_state}"
        )
    
    sim_state.current_state = BookingState.MATCHED
    print(f"✅ State transition: SEARCHING -> MATCHED")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/en-route")
async def trigger_en_route():
    """
    Manual trigger: Transition from MATCHED to EN_ROUTE state.
    Simulates vehicle starting its journey to pick up the user.
    """
    if sim_state.current_state != BookingState.MATCHED:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger EN_ROUTE from state {sim_state.current_state}"
        )
    
    sim_state.current_state = BookingState.EN_ROUTE
    print(f"✅ State transition: MATCHED -> EN_ROUTE")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/board")
async def trigger_board():
    """
    Manual trigger: Transition from EN_ROUTE to BOARDED state.
    Simulates user boarding the vehicle.
    """
    if sim_state.current_state not in [BookingState.EN_ROUTE, BookingState.DELAYED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger BOARD from state {sim_state.current_state}"
        )
    
    sim_state.current_state = BookingState.BOARDED
    # Snap user to vehicle position immediately
    sim_state.user_lat = sim_state.vehicle_lat
    sim_state.user_lng = sim_state.vehicle_lng
    print(f"✅ State transition: EN_ROUTE/DELAYED -> BOARDED")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/delay")
async def trigger_delay():
    """
    Manual trigger: Transition to DELAYED state.
    Simulates vehicle delay - slows down movement by 90%.
    """
    if sim_state.current_state not in [BookingState.EN_ROUTE, BookingState.BOARDED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger DELAY from state {sim_state.current_state}"
        )
    
    sim_state.current_state = BookingState.DELAYED
    sim_state.is_delayed = True
    sim_state.current_speed = sim_state.base_speed * 0.1  # Slow down by 90%
    print(f"⚠️ State transition: -> DELAYED (speed reduced by 90%)")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/resume")
async def trigger_resume():
    """
    Manual trigger: Resume from DELAYED state.
    Restores normal speed and returns to previous state.
    """
    if sim_state.current_state != BookingState.DELAYED:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger RESUME from state {sim_state.current_state}"
        )
    
    sim_state.is_delayed = False
    sim_state.current_speed = sim_state.base_speed
    
    # Return to EN_ROUTE or BOARDED based on context
    # For simplicity, we'll go to EN_ROUTE
    sim_state.current_state = BookingState.EN_ROUTE
    print(f"✅ State transition: DELAYED -> EN_ROUTE (speed restored)")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/complete")
async def trigger_complete():
    """
    Manual trigger: Transition to COMPLETED state.
    Simulates journey completion.
    """
    if sim_state.current_state not in [BookingState.BOARDED, BookingState.EN_ROUTE]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger COMPLETE from state {sim_state.current_state}"
        )
    
    sim_state.current_state = BookingState.COMPLETED
    print(f"✅ State transition: -> COMPLETED")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/reset")
async def trigger_reset():
    """
    Manual trigger: Reset to IDLE state.
    Resets simulation to initial state.
    """
    sim_state.current_state = BookingState.IDLE
    sim_state.is_delayed = False
    sim_state.current_speed = sim_state.base_speed
    sim_state.current_route_index = 0
    sim_state.vehicle_lat = sim_state.route_coordinates[0][0]
    sim_state.vehicle_lng = sim_state.route_coordinates[0][1]
    sim_state.user_lat = sim_state.user_stage_lat
    sim_state.user_lng = sim_state.user_stage_lng
    sim_state.total_distance_traveled = 0.0
    print(f"🔄 Simulation reset to IDLE")
    return {"status": "success", "current_state": sim_state.current_state.value}


@app.post("/api/trigger/search")
async def trigger_search():
    """
    Manual trigger: Start searching for vehicle.
    Transitions from IDLE to SEARCHING.
    """
    if sim_state.current_state != BookingState.IDLE:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot trigger SEARCH from state {sim_state.current_state}"
        )
    
    sim_state.current_state = BookingState.SEARCHING
    print(f"🔍 State transition: IDLE -> SEARCHING")
    return {"status": "success", "current_state": sim_state.current_state.value}


# =============================================================================
# TELEMETRY ENDPOINTS
# =============================================================================

@app.get("/api/telemetry", response_model=TelemetryResponse)
async def get_telemetry():
    """
    Get current telemetry data.
    Returns context-aware data based on current state.
    """
    # Calculate distance to user
    distance_to_user = haversine_distance(
        sim_state.vehicle_lat,
        sim_state.vehicle_lng,
        sim_state.user_lat,
        sim_state.user_lng
    )
    
    # Calculate ETA (linear distance / speed)
    eta = None
    if sim_state.current_state in [BookingState.MATCHED, BookingState.EN_ROUTE]:
        if sim_state.current_speed > 0:
            # Speed in m/s: current_speed * 111000
            speed_mps = sim_state.current_speed * 111000
            if speed_mps > 0:
                eta = distance_to_user / speed_mps
    
    # Build response
    response = TelemetryResponse(
        timestamp=datetime.now().isoformat(),
        state=sim_state.current_state.value,
        vehicle={
            "lat": sim_state.vehicle_lat,
            "lng": sim_state.vehicle_lng,
            "speed_kmh": sim_state.current_speed * 111000 * 3.6,  # Convert to km/h
            "route_index": sim_state.current_route_index,
        },
        user={
            "lat": sim_state.user_lat,
            "lng": sim_state.user_lng,
        },
        user_stage={
            "lat": sim_state.user_stage_lat,
            "lng": sim_state.user_stage_lng,
        },
        eta=eta,
        is_delayed=sim_state.is_delayed,
        distance_to_user=distance_to_user,
        total_distance_traveled=sim_state.total_distance_traveled,
    )
    
    return response


@app.get("/api/state")
async def get_state():
    """Get current state machine state"""
    return {
        "current_state": sim_state.current_state.value,
        "is_delayed": sim_state.is_delayed,
        "current_speed": sim_state.current_speed,
        "route_index": sim_state.current_route_index,
    }


@app.get("/api/route")
async def get_route():
    """Get the complete route coordinates"""
    return {
        "route": sim_state.route_coordinates,
        "user_stage": {
            "lat": sim_state.user_stage_lat,
            "lng": sim_state.user_stage_lng,
        }
    }


# =============================================================================
# STARTUP AND SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Start the GPS simulation thread on startup"""
    simulation_thread = threading.Thread(target=gps_simulation_loop, daemon=True)
    simulation_thread.start()
    print("🎯 GPS Telemetry Simulation API Started")
    print("📡 Available at: http://localhost:8000")
    print("📚 API docs at: http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    sim_state.simulation_running = False
    print("🛑 GPS Telemetry Simulation API Stopped")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
