from locust import HttpUser, task, between
import json
import time


class CommuterUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    token_fetched_at = 0

    def get_token(self):
        if not self.token or (time.time() - self.token_fetched_at) > 240:
            response = self.client.post('/api/auth/token/', json={
                'username': 'test_commuter',
                'password': 'testpass123',
            })
            if response.status_code == 200:
                self.token = response.json()['access']
                self.token_fetched_at = time.time()

    def auth_headers(self):
        self.get_token()
        return {'Authorization': f'Bearer {self.token}'}

    @task(3)
    def list_trips(self):
        self.client.get('/api/routing/trips/', headers=self.auth_headers())

    @task(2)
    def check_seat_availability(self):
        self.client.get(
            '/api/routing/stops/c413561d-0215-4eef-9575-eb2dcb4ff8de/seat-availability/',
            headers=self.auth_headers()
        )

    @task(1)
    def track_parcel(self):
        self.client.get(
            '/api/parcels/track/KE-NNWJF9/',
            headers=self.auth_headers()
        )


class FleetOwnerUser(HttpUser):
    wait_time = between(2, 5)
    token = None
    token_fetched_at = 0

    def get_token(self):
        if not self.token or (time.time() - self.token_fetched_at) > 240:
            response = self.client.post('/api/auth/token/', json={
                'username': 'supermetro_owner',
                'password': 'testpass123',
            })
            if response.status_code == 200:
                self.token = response.json()['access']
                self.token_fetched_at = time.time()

    def auth_headers(self):
        self.get_token()
        return {'Authorization': f'Bearer {self.token}'}

    @task(2)
    def fleet_analytics(self):
        self.client.get(
            '/api/fleet/analytics/?start=2026-06-01&end=2026-06-30',
            headers=self.auth_headers()
        )

    @task(1)
    def live_fleet(self):
        self.client.get('/api/fleet/live/', headers=self.auth_headers())