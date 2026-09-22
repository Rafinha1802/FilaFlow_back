from pydantic import BaseModel
from typing import Optional, List

class QueueBase(BaseModel):
    id: str
    company_id: str
    name: str
    attendant_name: Optional[str] = "Dr. Carlos Mendes"
    room: Optional[str] = "Consultório 04"
    initial_wait_min: Optional[int] = 30
    current_waiting: Optional[int] = 0
    status: Optional[str] = "active"

class QueueCreate(QueueBase):
    pass

class QueueResponse(QueueBase):
    class Config:
        from_attributes = True
