from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrderCreate(BaseModel):
    company_name: str
    customer_name: str
    email: str
    document: Optional[str] = None
    plan_name: str = "Profissional"
    billing_cycle: str = "monthly"
    payment_method: str = "pix"
    amount: Optional[float] = 189.00

class OrderResponse(OrderCreate):
    id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
