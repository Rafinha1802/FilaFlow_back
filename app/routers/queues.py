from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.core.deps import get_current_company
from app.models.queue import Queue
from app.models.ticket import Ticket
from app.models.company import Company
from app.schemas.queue import QueueCreate, QueueResponse

router = APIRouter(prefix="/api/queues", tags=["Queues"])

@router.get("/me")
def get_my_queues(
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Retorna todas as filas/profissionais da empresa autenticada com status em tempo real."""
    queues = db.query(Queue).filter(Queue.company_id == current_company.id).all()
    result = []
    
    for q in queues:
        waiting_tickets = db.query(Ticket).filter(
            Ticket.queue_id == q.id,
            Ticket.status == "waiting"
        ).order_by(Ticket.position.asc()).all()

        current_attending = db.query(Ticket).filter(
            Ticket.queue_id == q.id,
            Ticket.status == "attending"
        ).first()

        result.append({
            "id": q.id,
            "companyId": q.company_id,
            "name": q.name,
            "attendantName": q.attendant_name,
            "room": q.room,
            "initialWaitMin": q.initial_wait_min,
            "currentWaiting": len(waiting_tickets),
            "status": q.status,
            "currentAttending": {
                "id": current_attending.id,
                "ticket": current_attending.ticket_number,
                "name": current_attending.customer_name,
                "service": current_attending.service_name,
                "startedAt": current_attending.started_at.isoformat() if current_attending and current_attending.started_at else None
            } if current_attending else None,
            "waitingTickets": [
                {
                    "id": t.id,
                    "ticket": t.ticket_number,
                    "name": t.customer_name,
                    "service": t.service_name,
                    "time": t.estimated_wait_text,
                    "isPriority": t.is_priority,
                    "delayWarning": t.delay_warning
                }
                for t in waiting_tickets
            ]
        })
    return result

@router.post("", response_model=QueueResponse)
def create_queue(
    payload: QueueCreate,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Cria uma nova fila/profissional vinculada à empresa autenticada."""
    queue_id = f"{current_company.id}-{uuid.uuid4().hex[:4]}"
    new_queue = Queue(
        id=queue_id,
        company_id=current_company.id,
        name=payload.name,
        attendant_name=payload.attendant_name or current_company.attendant_name,
        room=payload.room or current_company.room,
        initial_wait_min=payload.initial_wait_min or 20,
        current_waiting=0,
        status="active"
    )
    db.add(new_queue)
    db.commit()
    db.refresh(new_queue)
    return new_queue

@router.get("", response_model=List[dict])
def get_all_queues(db: Session = Depends(get_db)):
    """Retorna listagem pública de filas para aplicativo do paciente e painéis."""
    queues = db.query(Queue).all()
    result = []
    for q in queues:
        company = db.query(Company).filter(Company.id == q.company_id).first()
        waiting_tickets = db.query(Ticket).filter(
            Ticket.queue_id == q.id,
            Ticket.status == "waiting"
        ).order_by(Ticket.position.asc()).all()

        ahead_list = [
            {
                "ticket": t.ticket_number,
                "name": t.customer_name,
                "status": "Em atendimento" if i == 0 else "Aguardando",
                "time": t.joined_at or "14:20",
                "isUser": t.is_user
            }
            for i, t in enumerate(waiting_tickets)
        ]

        user_ticket = next((t for t in waiting_tickets if t.is_user), None)

        result.append({
            "id": q.id,
            "companyName": company.company_name if company else "Empresa",
            "unitName": company.unit_name if company else "Unidade Centro",
            "category": company.category if company else "Clínica",
            "badgeColor": company.badge_color if company else "emerald",
            "serviceName": q.name,
            "attendantName": q.attendant_name,
            "room": q.room,
            "ticketNumber": user_ticket.ticket_number if user_ticket else (waiting_tickets[0].ticket_number if waiting_tickets else "01"),
            "position": user_ticket.position if user_ticket else (len(waiting_tickets) if waiting_tickets else 1),
            "initialWaitMin": q.initial_wait_min,
            "estimatedWaitText": f"{max(5, q.initial_wait_min - 4)}-{q.initial_wait_min + 5} min",
            "status": "waiting",
            "statusDetail": "Previsão atualizada por IA",
            "isAiRecalculating": False,
            "delayWarning": None,
            "joinedAt": user_ticket.joined_at if user_ticket else "14:05",
            "aheadList": ahead_list
        })
    return result

@router.get("/{queue_id}")
def get_queue(queue_id: str, db: Session = Depends(get_db)):
    """Retorna detalhes de uma fila específica."""
    q = db.query(Queue).filter(Queue.id == queue_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Fila não encontrada")
    
    company = db.query(Company).filter(Company.id == q.company_id).first()
    waiting_tickets = db.query(Ticket).filter(
        Ticket.queue_id == q.id,
        Ticket.status == "waiting"
    ).order_by(Ticket.position.asc()).all()

    return {
        "id": q.id,
        "companyName": company.company_name if company else "",
        "serviceName": q.name,
        "room": q.room,
        "attendantName": q.attendant_name,
        "currentWaiting": len(waiting_tickets),
        "tickets": [
            {
                "id": t.id,
                "ticket": t.ticket_number,
                "name": t.customer_name,
                "service": t.service_name,
                "time": t.estimated_wait_text,
                "isPriority": t.is_priority,
                "isUser": t.is_user,
                "status": t.status,
                "delayWarning": t.delay_warning
            }
            for t in waiting_tickets
        ]
    }
