from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime, timezone
import uuid
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class SubscriptionOrder(Base):
    __tablename__ = "subscription_orders"

    id = Column(String, primary_key=True, default=lambda: f"ord-{uuid.uuid4().hex[:8]}")
    company_name = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    document = Column(String, nullable=True) # CNPJ / CPF
    plan_name = Column(String, nullable=False) # Starter, Profissional, Enterprise
    billing_cycle = Column(String, default="monthly") # monthly, annual
    payment_method = Column(String, default="pix") # pix, card, boleto
    amount = Column(Float, default=189.00)
    status = Column(String, default="pending") # pending, paid, cancelled
    pix_code = Column(String, nullable=True)
    pix_qr_code_base64 = Column(String, nullable=True)
    gateway = Column(String, default="mercadopago")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
