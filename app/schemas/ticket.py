from pydantic import BaseModel
from typing import Optional

class TicketBase(BaseModel):
    queue_id: str
    ticket_number: str
    customer_name: str
    service_name: str
    status: Optional[str] = "waiting"
    position: Optional[int] = 1
    is_user: Optional[bool] = False
    is_priority: Optional[bool] = False
    estimated_wait_text: Optional[str] = "30-40 min"
    initial_wait_min: Optional[int] = 35
    delay_warning: Optional[str] = None
    status_detail: Optional[str] = None
    joined_at: Optional[str] = None

class TicketCreate(TicketBase):
    pass

class TicketManualCreate(BaseModel):
    name: str
    service_name: str
    is_priority: bool = False
    queue_id: Optional[str] = "clinica-vida"

class TicketDelayRequest(BaseModel):
    queue_id: Optional[str] = "clinica-vida"
    additional_minutes: Optional[int] = 5

class TicketResponse(TicketBase):
    id: str

    class Config:
        from_attributes = True
