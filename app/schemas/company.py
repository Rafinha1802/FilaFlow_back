from pydantic import BaseModel
from typing import Optional, List

class CompanyBase(BaseModel):
    id: str
    company_name: str
    unit_name: str
    category: str
    badge_color: Optional[str] = "emerald"
    address: Optional[str] = None
    avg_wait: Optional[str] = "25 min"
    room: Optional[str] = "Consultório 04"
    attendant_name: Optional[str] = "Dr. Carlos Mendes"
    email: Optional[str] = None
    phone: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    class Config:
        from_attributes = True
