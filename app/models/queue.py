from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from datetime import datetime
from app.core.database import Base

class Queue(Base):
    __tablename__ = "queues"

    id = Column(String, primary_key=True, index=True) # e.g. "clinica-vida"
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False) # e.g. "Consulta Oftalmologia Geral"
    attendant_name = Column(String, default="Dr. Carlos Mendes")
    room = Column(String, default="Consultório 04")
    initial_wait_min = Column(Integer, default=30)
    current_waiting = Column(Integer, default=0)
    status = Column(String, default="active") # active, paused
    created_at = Column(DateTime, default=datetime.utcnow)
