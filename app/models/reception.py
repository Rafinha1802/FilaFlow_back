from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime
import uuid
from app.core.database import Base

class ReceptionPatient(Base):
    __tablename__ = "reception_patients"

    id = Column(String, primary_key=True, default=lambda: f"rec-{uuid.uuid4().hex[:8]}")
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, default="clinica-vida")
    patient_name = Column(String, nullable=False)
    document = Column(String, nullable=True) # CPF
    phone = Column(String, nullable=True)
    insurance_name = Column(String, default="Unimed") # Unimed, Bradesco Saúde, Amil, SulAmérica, Particular
    card_number = Column(String, nullable=True) # Carteirinha
    procedure = Column(String, default="Consulta Oftalmologia Geral")
    doctor_name = Column(String, default="Dr. Carlos Mendes")
    room = Column(String, default="Consultório 04")
    status = Column(String, default="awaiting_auth") # awaiting_auth, verifying, authorized, declined
    auth_code = Column(String, nullable=True) # Guia do convênio (ex: "AUT-98214")
    is_priority = Column(Boolean, default=False)
    notes = Column(String, nullable=True)
    ticket_number = Column(String, nullable=True) # Ex: "#49" quando liberado para a fila do médico
    created_at = Column(DateTime, default=datetime.utcnow)
    authorized_at = Column(DateTime, nullable=True)
