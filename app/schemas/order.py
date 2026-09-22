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
    pix_code: Optional[str] = None
    pix_qr_code_base64: Optional[str] = None
    gateway: Optional[str] = "mercadopago"
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WebhookPayload(BaseModel):
    action: Optional[str] = None
    event: Optional[str] = None
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    data: Optional[dict] = None
