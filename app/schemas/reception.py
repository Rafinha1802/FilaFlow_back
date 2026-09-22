from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReceptionPatientBase(BaseModel):
    patient_name: str
    document: Optional[str] = None # CPF
    phone: Optional[str] = None
    insurance_name: Optional[str] = "Unimed"
    card_number: Optional[str] = None
    procedure: Optional[str] = "Consulta Oftalmologia Geral"
    doctor_name: Optional[str] = "Dr. Carlos Mendes"
    room: Optional[str] = "Consultório 04"
    is_priority: Optional[bool] = False
    notes: Optional[str] = None

class ReceptionPatientCreate(ReceptionPatientBase):
    pass

class ReceptionAuthorizeRequest(BaseModel):
    auth_code: Optional[str] = None # Guia de autorização (ex: "AUT-77291")
    queue_id: Optional[str] = "clinica-vida"
    is_priority: Optional[bool] = False

class ReceptionPatientResponse(ReceptionPatientBase):
    id: str
    company_id: Optional[str] = None
    status: str
    auth_code: Optional[str] = None
    ticket_number: Optional[str] = None
    created_at: datetime
    authorized_at: Optional[datetime] = None

    class Config:
        from_attributes = True
