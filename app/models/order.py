from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
import uuid
from app.core.database import Base

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
    status = Column(String, default="paid") # pending, paid, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
