import csv
import io
import time
import asyncio
from typing import List, Dict
from uuid import UUID, uuid4
from datetime import datetime
import httpx
from app.config import settings
from app.models import HospitalCreate, HospitalBulkResult, BatchStatus, DeleteResult, UpdateResult, BatchActivateResponse, HospitalUpdate

import json
import os
from pydantic import TypeAdapter

# Persistent storage for batch statuses
STORAGE_FILE = "batch_statuses.json"

def save_batch_status(status: BatchStatus):
    batch_statuses[status.batch_id] = status
    data = {str(k): v.model_dump(mode="json") for k, v in batch_statuses.items()}
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f)

def load_batch_statuses():
    global batch_statuses
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, "r") as f:
                data = json.load(f)
                adapter = TypeAdapter(BatchStatus)
                batch_statuses = {UUID(k): adapter.validate_python(v) for k, v in data.items()}
        except Exception as e:
            print(f"Error loading batch statuses: {e}")
            batch_statuses = {}
    else:
        batch_statuses = {}

# Initialize
batch_statuses: Dict[UUID, BatchStatus] = {}
load_batch_statuses()

async def process_bulk_hospitals(batch_id: UUID, hospitals_to_create: List[Dict]):
    status = batch_statuses[batch_id]
    
    async with httpx.AsyncClient(base_url=settings.HOSPITAL_API_BASE_URL, timeout=30.0) as client:
        # Create hospitals concurrently
        tasks = [
            create_hospital_task(client, h["data"], h["row"], batch_id)
            for h in hospitals_to_create
        ]
        
        # Process them as they complete to update progress in real-time
        for coro in asyncio.as_completed(tasks):
            res = await coro
            status.results.append(res)
            status.processed += 1
            if res.status == "failed":
                status.failed += 1
            save_batch_status(status)
            
        # Update status based on results
        if status.failed == 0 and status.total > 0:
            try:
                activate_resp = await client.patch(f"/hospitals/batch/{batch_id}/activate")
                activate_resp.raise_for_status()
                status.activated = True
                status.status = "completed"
                for res in status.results:
                    if res.status == "created":
                        res.status = "created_and_activated"
            except Exception as e:
                status.status = "partially_completed"
                for res in status.results:
                    if res.status == "created":
                        res.status = "created_but_activation_failed"
                        res.error = f"Activation failed: {str(e)}"
        elif status.failed > 0:
            status.status = "failed" if status.failed == status.total else "partially_completed"
            for res in status.results:
                if res.status == "created":
                    res.status = "created_but_not_activated_due_to_other_failures"
        else:
            status.status = "completed"

    status.end_time = datetime.now()
    save_batch_status(status)

async def create_hospital_task(client: httpx.AsyncClient, hospital: HospitalCreate, row_idx: int, batch_id: UUID) -> HospitalBulkResult:
    # Simulation: Fail if name contains "Fail"
    if "Fail" in hospital.name:
        return HospitalBulkResult(
            row=row_idx,
            name=hospital.name,
            status="failed",
            error="Simulated failure for testing resume capability.",
            data=hospital
        )
    try:
        resp = await client.post("/hospitals/", json=hospital.model_dump(mode="json"))
        if resp.status_code == 200:
            data = resp.json()
            return HospitalBulkResult(
                row=row_idx,
                hospital_id=data["id"],
                name=hospital.name,
                status="created",
                data=hospital
            )
        else:
            return HospitalBulkResult(
                row=row_idx,
                name=hospital.name,
                status="failed",
                error=f"API Error: {resp.status_code} - {resp.text}",
                data=hospital
            )
    except Exception as e:
        return HospitalBulkResult(
            row=row_idx,
            name=hospital.name,
            status="failed",
            error=str(e),
            data=hospital
        )

def validate_csv_format(content: str) -> List[str]:
    errors = []
    f = io.StringIO(content)
    reader = csv.DictReader(f)
    
    if not reader.fieldnames or "name" not in reader.fieldnames or "address" not in reader.fieldnames:
        errors.append("CSV must contain 'name' and 'address' columns.")
        return errors

    rows = list(reader)
    if len(rows) > settings.MAX_CSV_SIZE:
        errors.append(f"CSV exceeds maximum size of {settings.MAX_CSV_SIZE} hospitals.")
    
    for i, row in enumerate(rows, 1):
        if not row.get("name"):
            errors.append(f"Row {i}: Name is required.")
        if not row.get("address"):
            errors.append(f"Row {i}: Address is required.")
            
    return errors

def parse_csv_to_hospitals(content: str, batch_id: UUID) -> List[Dict]:
    f = io.StringIO(content)
    reader = csv.DictReader(f)
    hospitals = []
    for i, row in enumerate(reader, 1):
        hospitals.append({
            "row": i,
            "data": HospitalCreate(
                name=row["name"],
                address=row["address"],
                phone=row.get("phone") or None,
                creation_batch_id=batch_id
            )
        })
    return hospitals

async def delete_hospital(client: httpx.AsyncClient, hospital_id: int) -> Dict:
    """Delete a single hospital by ID"""
    try:
        resp = await client.delete(f"/hospitals/{hospital_id}")
        if resp.status_code in [200, 204]:
            return {"status": "deleted", "error": None}
        else:
            return {"status": "failed", "error": f"API Error: {resp.status_code} - {resp.text}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

async def process_bulk_delete(batch_id: UUID, hospital_ids: List[int]) -> Dict:
    """Process bulk deletion of hospitals"""
    results = []
    successful = 0
    failed = 0
    
    async with httpx.AsyncClient(base_url=settings.HOSPITAL_API_BASE_URL, timeout=30.0) as client:
        # Create delete tasks concurrently
        tasks = [
            delete_hospital_task(client, hospital_id)
            for hospital_id in hospital_ids
        ]
        
        # Process them as they complete
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.append(res)
            if res.status == "deleted":
                successful += 1
            else:
                failed += 1
    
    return {
        "batch_id": batch_id,
        "status": "completed",
        "total": len(hospital_ids),
        "successful": successful,
        "failed": failed,
        "results": results
    }

async def delete_hospital_task(client: httpx.AsyncClient, hospital_id: int) -> DeleteResult:
    """Task to delete a single hospital and return result"""
    try:
        # First fetch the hospital to get its name
        get_resp = await client.get(f"/hospitals/{hospital_id}")
        if get_resp.status_code != 200:
            return DeleteResult(
                hospital_id=hospital_id,
                name="Unknown",
                status="failed",
                error=f"Could not fetch hospital: {get_resp.status_code}"
            )
        
        hospital_data = get_resp.json()
        hospital_name = hospital_data.get("name", "Unknown")
        
        # Delete the hospital
        delete_resp = await client.delete(f"/hospitals/{hospital_id}")
        if delete_resp.status_code in [200, 204]:
            return DeleteResult(
                hospital_id=hospital_id,
                name=hospital_name,
                status="deleted"
            )
        else:
            return DeleteResult(
                hospital_id=hospital_id,
                name=hospital_name,
                status="failed",
                error=f"API Error: {delete_resp.status_code} - {delete_resp.text}"
            )
    except Exception as e:
        return DeleteResult(
            hospital_id=hospital_id,
            name="Unknown",
            status="failed",
            error=str(e)
        )

async def process_bulk_update(batch_id: UUID, hospitals_to_update: List[HospitalUpdate]) -> Dict:
    """Process bulk update of hospitals"""
    from app.models import UpdateResult
    
    results = []
    successful = 0
    failed = 0
    
    async with httpx.AsyncClient(base_url=settings.HOSPITAL_API_BASE_URL, timeout=30.0) as client:
        # Create update tasks concurrently
        tasks = [
            update_hospital_task(client, hospital)
            for hospital in hospitals_to_update
        ]
        
        # Process them as they complete
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.append(res)
            if res.status == "updated":
                successful += 1
            else:
                failed += 1
    
    return {
        "batch_id": batch_id,
        "status": "completed",
        "total": len(hospitals_to_update),
        "successful": successful,
        "failed": failed,
        "results": results
    }

async def update_hospital_task(client: httpx.AsyncClient, hospital_update: HospitalUpdate) -> UpdateResult:
    """Task to update a single hospital and return result"""
    from app.models import UpdateResult
    
    hospital_id = hospital_update.id
    try:
        # Get hospital details first
        get_resp = await client.get(f"/hospitals/{hospital_id}")
        if get_resp.status_code != 200:
            return UpdateResult(
                hospital_id=hospital_id,
                name="Unknown",
                status="failed",
                error=f"Could not fetch hospital: {get_resp.status_code}"
            )
        
        hospital_data = get_resp.json()
        hospital_name = hospital_update.name or hospital_data.get("name", "Unknown")
        
        # Update the hospital
        update_data = {}
        if hospital_update.name is not None:
            update_data["name"] = hospital_update.name
        if hospital_update.address is not None:
            update_data["address"] = hospital_update.address
        if hospital_update.phone is not None:
            update_data["phone"] = hospital_update.phone
        
        if not update_data:
            return UpdateResult(
                hospital_id=hospital_id,
                name=hospital_name,
                status="failed",
                error="No update fields provided."
            )
        
        update_resp = await client.put(f"/hospitals/{hospital_id}", json=update_data)
        if update_resp.status_code in [200, 201]:
            return UpdateResult(
                hospital_id=hospital_id,
                name=hospital_name,
                status="updated"
            )
        else:
            return UpdateResult(
                hospital_id=hospital_id,
                name=hospital_name,
                status="failed",
                error=f"API Error: {update_resp.status_code} - {update_resp.text}"
            )
    except Exception as e:
        return UpdateResult(
            hospital_id=hospital_id,
            name="Unknown",
            status="failed",
            error=str(e)
        )

async def activate_batch(batch_id: UUID) -> Dict:
    """Activate a specific batch of hospitals"""
    async with httpx.AsyncClient(base_url=settings.HOSPITAL_API_BASE_URL, timeout=30.0) as client:
        try:
            activate_resp = await client.patch(f"/hospitals/batch/{batch_id}/activate")
            if activate_resp.status_code in [200, 201]:
                return {
                    "batch_id": batch_id,
                    "status": "success",
                    "activated": True,
                    "message": "Batch activated successfully"
                }
            else:
                return {
                    "batch_id": batch_id,
                    "status": "failed",
                    "activated": False,
                    "message": f"Activation failed: {activate_resp.status_code} - {activate_resp.text}"
                }
        except Exception as e:
            return {
                "batch_id": batch_id,
                "status": "failed",
                "activated": False,
                "message": f"Error: {str(e)}"
            }
