import argparse
import json
import sys
import time

import httpx

DEFAULT_BASE_URL = "https://bulk-hospital-service.onrender.com"

CSV_CONTENT = """name,address,phone
Deployment Test Hospital A,100 Deploy St,555-0001
Deployment Test Hospital B,200 Deploy Ave,555-0002
"""


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def print_response(resp: httpx.Response) -> None:
    print(resp.status_code)
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def run_health_check(client: httpx.Client, base_url: str) -> None:
    print("\n==> Health check")
    resp = client.get(f"{base_url}/")
    print_response(resp)
    if resp.status_code != 200:
        fail("Health check failed")


def run_bulk_create(client: httpx.Client, base_url: str) -> str:
    print("\n==> Bulk create")
    files = {
        "file": ("deploy_test.csv", CSV_CONTENT, "text/csv")
    }
    resp = client.post(f"{base_url}/hospitals/bulk", files=files)
    print_response(resp)
    if resp.status_code != 202:
        fail("Bulk create failed")

    batch_id = resp.json().get("batch_id")
    if not batch_id:
        fail("Bulk create did not return a batch_id")
    return batch_id


def poll_batch_status(client: httpx.Client, base_url: str, batch_id: str) -> dict:
    print("\n==> Poll batch status")
    status_url = f"{base_url}/hospitals/batch/{batch_id}/status"
    for attempt in range(15):
        resp = client.get(status_url)
        print(f"Attempt {attempt + 1}: {resp.status_code}")
        data = resp.json()
        print(json.dumps(data, indent=2))
        if resp.status_code != 200:
            fail("Batch status request failed")

        if data.get("status") != "processing":
            return data

        time.sleep(2)

    fail("Batch status remained processing too long")


def build_updates(batch_status: dict) -> dict:
    hospital_ids = [
        result["hospital_id"]
        for result in batch_status.get("results", [])
        if result.get("hospital_id")
    ]

    if not hospital_ids:
        fail("No hospital IDs found in batch results")

    return {
        "hospitals": [
            {"id": hospital_id, "name": f"Deployment Updated Hospital {hospital_id}"}
            for hospital_id in hospital_ids
        ]
    }


def run_bulk_update(client: httpx.Client, base_url: str, payload: dict) -> dict:
    print("\n==> Bulk update")
    resp = client.post(f"{base_url}/hospitals/bulk-update", json=payload)
    print_response(resp)
    if resp.status_code != 202:
        fail("Bulk update failed")
    return resp.json()


def run_activate_batch(client: httpx.Client, base_url: str, batch_id: str) -> dict:
    print("\n==> Activate batch")
    resp = client.patch(f"{base_url}/hospitals/batch/{batch_id}/activate")
    print_response(resp)
    if resp.status_code != 200:
        fail("Activate batch request failed")
    return resp.json()


def run_bulk_delete(client: httpx.Client, base_url: str, payload: dict) -> dict:
    print("\n==> Bulk delete")
    resp = client.post(f"{base_url}/hospitals/bulk-delete", json=payload)
    print_response(resp)
    if resp.status_code != 202:
        fail("Bulk delete failed")
    return resp.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deployment endpoint tests")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the deployed app (default: {DEFAULT_BASE_URL})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = normalize_base_url(args.base_url)
    print(f"Deployment test base URL: {base_url}")

    with httpx.Client(timeout=30.0) as client:
        run_health_check(client, base_url)
        batch_id = run_bulk_create(client, base_url)
        batch_status = poll_batch_status(client, base_url, batch_id)

        update_payload = build_updates(batch_status)
        run_bulk_update(client, base_url, update_payload)

        activate_response = run_activate_batch(client, base_url, batch_id)
        if activate_response.get("activated"):
            print("Batch activation succeeded")
        else:
            print("Batch activation returned failure message, but endpoint is reachable")

        delete_payload = {"hospital_ids": [item["id"] for item in update_payload["hospitals"]]}
        run_bulk_delete(client, base_url, delete_payload)

    print("\nDeployment endpoint test script completed.")


if __name__ == "__main__":
    main()
