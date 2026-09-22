from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.core.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True) # e.g. "clinica-vida"
    company_name = Column(String, nullable=False)
    unit_name = Column(String, nullable=False)
    category = Column(String, nullable=False) # Clínica, Laboratório, Restaurante, etc.
    badge_color = Column(String, default="emerald")
    address = Column(String, nullable=True)
    avg_wait = Column(String, default="25 min")
    room = Column(String, default="Consultório 04")
    attendant_name = Column(String, default="Dr. Carlos Mendes")
    email = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
