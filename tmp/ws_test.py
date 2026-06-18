import asyncio
import websockets

TRIP_ID = "5169ef3b-105a-42bf-ae3f-bbc9695925d3"

async def listen():
    uri = f"ws://localhost:8000/ws/trip/{TRIP_ID}/tracking/"
    async with websockets.connect(uri) as ws:
        print(f"Connected to {uri}")
        while True:
            message = await ws.recv()
            print("Received:", message)

asyncio.run(listen())
