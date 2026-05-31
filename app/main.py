from uuid import uuid4, UUID
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from app.models import (
    BulkProcessAccepted, BatchStatus, HospitalBulkResult, HospitalCreate,
    DeleteResult, BulkDeleteRequest, BulkDeleteResponse,
    UpdateResult, BulkUpdateRequest, BulkUpdateResponse, BatchActivateResponse
)
from app.services import (
    process_bulk_hospitals, validate_csv_format, batch_statuses, 
    parse_csv_to_hospitals, save_batch_status, process_bulk_delete,
    process_bulk_update, activate_batch
)
from app.config import settings

app = FastAPI(title="Hospital Bulk Processing System")

@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/hospitals/bulk", response_model=BulkProcessAccepted, status_code=202)
async def bulk_create_hospitals(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    content = (await file.read()).decode("utf-8")
    
    validation_errors = validate_csv_format(content)
    if validation_errors:
        raise HTTPException(status_code=400, detail=validation_errors)
    
    batch_id = uuid4()
    hospitals_to_create = parse_csv_to_hospitals(content, batch_id)
    
    # Initialize batch status
    batch_status = BatchStatus(
        batch_id=batch_id,
        status="processing",
        total=len(hospitals_to_create),
        processed=0,
        failed=0,
        results=[],
        original_hospitals=[h["data"] for h in hospitals_to_create],
        start_time=datetime.now()
    )
    batch_statuses[batch_id] = batch_status
    save_batch_status(batch_status)
    
    # Start background task
    background_tasks.add_task(process_bulk_hospitals, batch_id, hospitals_to_create)
    
    return BulkProcessAccepted(
        batch_id=batch_id,
        status="processing",
        eta_seconds=len(hospitals_to_create) * 0.5 # Rough estimate
    )

@app.post("/hospitals/batch/{batch_id}/resume", response_model=BulkProcessAccepted, status_code=202)
async def resume_batch(
    batch_id: UUID,
    background_tasks: BackgroundTasks
):
    if batch_id not in batch_statuses:
        raise HTTPException(status_code=404, detail="Batch ID not found.")

    status = batch_statuses[batch_id]
    if status.status == "processing":
        raise HTTPException(status_code=400, detail="Batch is already being processed.")
    if status.failed == 0 and status.activated:
        raise HTTPException(status_code=400, detail="Batch is already successfully completed and activated.")

    failed_rows = [res.row for res in status.results if res.status == "failed"]
    processed_rows = [res.row for res in status.results]
    missing_rows = [i for i, _ in enumerate(status.original_hospitals, 1) if i not in processed_rows]
    to_retry_indices = set(failed_rows) | set(missing_rows)

    if to_retry_indices:
        hospitals_to_retry = [
            {"row": idx, "data": status.original_hospitals[idx - 1]}
            for idx in sorted(to_retry_indices)
        ]
        status.results = [res for res in status.results if res.row not in to_retry_indices]
        status.processed = len(status.results)
        status.failed = 0
        status.status = "processing"
        status.start_time = datetime.now()
        status.end_time = None
        save_batch_status(status)
        background_tasks.add_task(process_bulk_hospitals, batch_id, hospitals_to_retry)
        eta_seconds = len(hospitals_to_retry) * 0.5
    else:
        status.status = "processing"
        status.start_time = datetime.now()
        status.end_time = None
        save_batch_status(status)
        background_tasks.add_task(activate_batch, batch_id)
        eta_seconds = 1.0

    return BulkProcessAccepted(
        batch_id=batch_id,
        status="processing",
        eta_seconds=eta_seconds
    )

@app.post("/hospitals/bulk-delete", response_model=BulkDeleteResponse, status_code=202)
async def bulk_delete_hospitals(
    background_tasks: BackgroundTasks,
    request: BulkDeleteRequest
):
    """Bulk delete multiple hospitals (async operation)"""
    if not request.hospital_ids:
        raise HTTPException(status_code=400, detail="hospital_ids list cannot be empty.")
    
    batch_id = uuid4()
    
    # Start background task for deletion
    background_tasks.add_task(process_bulk_delete, batch_id, request.hospital_ids)
    
    return BulkDeleteResponse(
        batch_id=batch_id,
        status="processing",
        total=len(request.hospital_ids),
        successful=0,
        failed=0,
        results=[]
    )

@app.get("/hospitals/batch/{batch_id}/status", response_model=BatchStatus)
async def get_batch_status(batch_id: UUID):
    if batch_id not in batch_statuses:
        raise HTTPException(status_code=404, detail="Batch ID not found.")
    return batch_statuses[batch_id]

@app.post("/hospitals/validate-csv")
async def validate_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    
    content = (await file.read()).decode("utf-8")
    errors = validate_csv_format(content)
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }

@app.post("/hospitals/bulk-update", response_model=BulkUpdateResponse, status_code=202)
async def bulk_update_hospitals(
    background_tasks: BackgroundTasks,
    request: BulkUpdateRequest
):
    """Bulk update multiple hospitals (async operation)"""
    if not request.hospitals:
        raise HTTPException(status_code=400, detail="hospitals list cannot be empty.")
    
    batch_id = uuid4()
    
    # Start background task for updating
    background_tasks.add_task(process_bulk_update, batch_id, request.hospitals)
    
    return BulkUpdateResponse(
        batch_id=batch_id,
        status="processing",
        total=len(request.hospitals),
        successful=0,
        failed=0,
        results=[]
    )

@app.patch("/hospitals/batch/{batch_id}/activate", response_model=BatchActivateResponse, status_code=200)
async def activate_hospitals_batch(batch_id: UUID):
    """Activate a specific batch of hospitals"""
    try:
        result = await activate_batch(batch_id)
        
        # Update batch status if it exists
        if batch_id in batch_statuses:
            batch_statuses[batch_id].activated = result["activated"]
            if result["activated"]:
                batch_statuses[batch_id].status = "completed"
            save_batch_status(batch_statuses[batch_id])
        
        return BatchActivateResponse(
            batch_id=batch_id,
            status=result["status"],
            activated=result["activated"],
            message=result["message"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
