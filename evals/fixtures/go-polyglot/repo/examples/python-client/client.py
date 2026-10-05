"""Partner example: create a delivery on fleetd. Not part of the service."""
import requests


def create_delivery(base_url: str, token: str) -> dict:
    resp = requests.post(base_url + "/v1/deliveries", headers={"Authorization": "Bearer " + token}, timeout=10)
    resp.raise_for_status()
    return resp.json()
