from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid
import random

from app.core.database import get_db
from app.core.deps import get_current_company
from app.models.company import Company
from app.models.reception import ReceptionPatient
from app.models.ticket import Ticket
from app.models.queue import Queue
from app.schemas.reception import (
    ReceptionPatientResponse,
    ReceptionPatientCreate,
    ReceptionAuthorizeRequest
)
from app.routers.websocket import ws_manager

router = APIRouter(prefix="/api/reception", tags=["Reception & Insurance"])

@router.get("/waiting-list", response_model=List[ReceptionPatientResponse])
def get_reception_waiting_list(
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Lista os pacientes na recepção da empresa autenticada."""
    patients = db.query(ReceptionPatient).filter(
        ReceptionPatient.company_id == current_company.id
    ).order_by(ReceptionPatient.created_at.desc()).all()
    return patients

@router.post("/waiting-list", response_model=ReceptionPatientResponse)
async def add_reception_patient(
    payload: ReceptionPatientCreate,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Adiciona paciente na recepção da empresa autenticada."""
    patient = ReceptionPatient(
        company_id=current_company.id,
        patient_name=payload.patient_name,
        document=payload.document,
        phone=payload.phone,
        insurance_name=payload.insurance_name or "Unimed",
        card_number=payload.card_number,
        procedure=payload.procedure or "Consulta Oftalmologia Geral",
        doctor_name=payload.doctor_name or current_company.attendant_name or "Médico Responsável",
        room=payload.room or current_company.room or "Consultório 01",
        status="awaiting_auth",
        is_priority=payload.is_priority or False,
        notes=payload.notes
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    # Broadcast exclusivo para o painel da recepção desta empresa
    await ws_manager.broadcast({
        "type": "RECEPTION_PATIENT_ADDED",
        "companyId": current_company.id,
        "patient": {
            "id": patient.id,
            "patientName": patient.patient_name,
            "insuranceName": patient.insurance_name,
            "status": patient.status
        }
    }, company_id=current_company.id)

    return patient

@router.put("/waiting-list/{patient_id}/status")
async def update_patient_status(
    patient_id: str,
    status: str,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Atualiza o status de autorização do paciente na recepção."""
    patient = db.query(ReceptionPatient).filter(
        ReceptionPatient.id == patient_id,
        ReceptionPatient.company_id == current_company.id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado na recepção da sua empresa")

    patient.status = status
    db.commit()
    db.refresh(patient)

    await ws_manager.broadcast({
        "type": "RECEPTION_STATUS_UPDATED",
        "companyId": current_company.id,
        "patientId": patient.id,
        "status": status
    }, company_id=current_company.id)

    return {"message": f"Status atualizado para '{status}'", "patient": patient}

@router.post("/waiting-list/{patient_id}/authorize")
async def authorize_patient_and_send_to_doctor(
    patient_id: str,
    payload: Optional[ReceptionAuthorizeRequest] = None,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Autoriza o convênio do paciente e gera automaticamente o ticket na fila do médico."""
    patient = db.query(ReceptionPatient).filter(
        ReceptionPatient.id == patient_id,
        ReceptionPatient.company_id == current_company.id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado na recepção da sua empresa")

    queue_id = (payload.queue_id if payload and payload.queue_id else None) or current_company.id
    
    # Validar se a fila pertence a esta empresa
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=404, detail="Fila de atendimento de destino não encontrada")
    if queue.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: a fila de destino pertence a outra empresa"
        )

    auth_code = (payload.auth_code if payload and payload.auth_code else None) or f"AUT-{random.randint(10000, 99999)}"

    # Gerar próximo número de senha na fila
    last_ticket = db.query(Ticket).filter(Ticket.queue_id == queue_id).order_by(Ticket.created_at.desc()).first()
    try:
        current_num = int(last_ticket.ticket_number.replace("#", "")) if last_ticket else 48
        next_num = f"#{current_num + 1}"
    except Exception:
        next_num = f"#{random.randint(49, 90)}"

    waiting_count = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).count()

    is_priority = payload.is_priority if (payload and payload.is_priority is not None) else patient.is_priority
    new_position = 1 if is_priority else waiting_count + 1

    # Atualizar paciente na recepção
    patient.status = "authorized"
    patient.auth_code = auth_code
    patient.ticket_number = next_num
    patient.authorized_at = datetime.utcnow()

    # Criar ticket oficial na fila do médico
    new_ticket = Ticket(
        id=f"ticket-{uuid.uuid4().hex[:6]}",
        queue_id=queue_id,
        ticket_number=next_num,
        customer_name=patient.patient_name,
        service_name=f"{patient.procedure} ({patient.insurance_name})",
        status="waiting",
        position=new_position,
        is_priority=is_priority,
        initial_wait_min=(waiting_count + 1) * 10,
        estimated_wait_text=f"~{(waiting_count + 1) * 10} min",
        joined_at=datetime.now().strftime("%H:%M")
    )
    db.add(new_ticket)
    queue.current_waiting += 1

    db.commit()
    db.refresh(patient)

    # Transmitir evento para a sala da empresa e da fila
    event_data = {
        "type": "PATIENT_AUTHORIZED_FOR_DOCTOR",
        "companyId": current_company.id,
        "queueId": queue_id,
        "patientId": patient.id,
        "patientName": patient.patient_name,
        "insuranceName": patient.insurance_name,
        "authCode": auth_code,
        "ticket": {
            "id": new_ticket.id,
            "ticket": new_ticket.ticket_number,
            "name": new_ticket.customer_name,
            "service": new_ticket.service_name,
            "time": new_ticket.estimated_wait_text,
            "isPriority": new_ticket.is_priority
        }
    }
    await ws_manager.broadcast(event_data, company_id=current_company.id, queue_id=queue_id)

    return {
        "message": f"Convênio {patient.insurance_name} autorizado com sucesso! Senha {next_num} enviada para a fila do médico.",
        "authCode": auth_code,
        "ticketNumber": next_num,
        "patient": patient,
        "doctorTicket": {
            "ticket": new_ticket.ticket_number,
            "name": new_ticket.customer_name,
            "service": new_ticket.service_name,
            "time": new_ticket.estimated_wait_text,
            "isPriority": new_ticket.is_priority
        }
    }

@router.delete("/waiting-list/{patient_id}")
def remove_reception_patient(
    patient_id: str,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Remove paciente da lista de recepção da empresa."""
    patient = db.query(ReceptionPatient).filter(
        ReceptionPatient.id == patient_id,
        ReceptionPatient.company_id == current_company.id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado na recepção da sua empresa")

    db.delete(patient)
    db.commit()
    return {"message": "Paciente removido da lista de espera da recepção"}
