from locust import HttpUser, task, between

class MissileUser(HttpUser):
    wait_time = between(0.2, 1.0)
    
    @task
    def launch(self):
        # Use query parameters instead of JSON body for the launch endpoint
        self.client.post("/launch", params={
            "lat": 36.5, 
            "lon": -123.1,
            "targetLat": 34.05, 
            "targetLon": -118.25,
            "missileType": "SCUD-C"
        })