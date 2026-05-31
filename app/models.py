from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class HospitalBase(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None

class HospitalCreate(HospitalBase):
    creation_batch_id: Optional[UUID] = None

class Hospital(HospitalBase):
    id: int
    creation_batch_id: Optional[UUID]
    active: bool
    created_at: datetime

class HospitalBulkResult(BaseModel):
    row: int
    hospital_id: Optional[int] = None
    name: str
    status: str
    error: Optional[str] = None
    data: Optional[HospitalCreate] = None  # Store original data for resume

class BulkProcessResponse(BaseModel):
    batch_id: UUID
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    processing_time_seconds: float
    batch_activated: bool
    hospitals: List[HospitalBulkResult]

class BatchStatus(BaseModel):
    batch_id: UUID
    status: str # "processing", "completed", "failed", "partially_completed"
    total: int
    processed: int
    failed: int
    results: List[HospitalBulkResult]
    original_hospitals: List[HospitalCreate] = [] # Store all for resume
    activated: bool = False
    start_time: datetime
    end_time: Optional[datetime] = None

class BulkProcessAccepted(BaseModel):
    batch_id: UUID
    status: str
    eta_seconds: float

class DeleteResult(BaseModel):
    hospital_id: int
    name: str
    status: str
    error: Optional[str] = None

class BulkDeleteRequest(BaseModel):
    hospital_ids: List[int]

class BulkDeleteResponse(BaseModel):
    batch_id: UUID
    status: str
    total: int
    successful: int
    failed: int
    results: List[DeleteResult]

class HospitalUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

class UpdateResult(BaseModel):
    hospital_id: int
    name: str
    status: str
    error: Optional[str] = None

class BulkUpdateRequest(BaseModel):
    hospitals: List[HospitalUpdate]

class BulkUpdateResponse(BaseModel):
    batch_id: UUID
    status: str
    total: int
    successful: int
    failed: int
    results: List[UpdateResult]

class BatchActivateResponse(BaseModel):
    batch_id: UUID
    status: str
    activated: bool
    message: str

