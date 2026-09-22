from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.models.ticket import Ticket
from app.models.queue import Queue
from app.models.company import Company
from app.schemas.ticket import TicketManualCreate, TicketDelayRequest
from app.routers.websocket import ws_manager
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

@router.post("/next")
async def call_next_ticket(queue_id: str = "clinica-vida", db: Session = Depends(get_db)):
    # Find active waiting tickets
    waiting_tickets = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).order_by(Ticket.position.asc()).all()

    if not waiting_tickets:
        raise HTTPException(status_code=400, detail="Não há clientes na fila de espera")

    called_ticket = waiting_tickets[0]
    called_ticket.status = "called"

    # Finish any currently attending ticket
    current_attending = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "attending"
    ).all()
    for att in current_attending:
        att.status = "finished"

    called_ticket.status = "attending"

    # Update positions for the remaining waiting tickets
    remaining = waiting_tickets[1:]
    for idx, t in enumerate(remaining, start=1):
        t.position = idx
        t.initial_wait_min = max(2, t.initial_wait_min - 8)
        t.estimated_wait_text = f"{max(2, t.initial_wait_min - 4)}-{t.initial_wait_min + 3} min"

    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if queue:
        queue.current_waiting = len(remaining)

    db.commit()

    # Broadcast via WebSocket
    event_data = {
        "type": "TICKET_CALLED",
        "queueId": queue_id,
        "ticket": {
            "id": called_ticket.id,
            "ticket": called_ticket.ticket_number,
            "name": called_ticket.customer_name,
            "service": called_ticket.service_name,
            "room": queue.room if queue else "Consultório 04",
            "isUser": called_ticket.is_user
        },
        "remainingCount": len(remaining)
    }
    await ws_manager.broadcast(event_data)

    return {
        "message": f"Senha {called_ticket.ticket_number} chamada com sucesso",
        "calledTicket": {
            "ticket": called_ticket.ticket_number,
            "name": called_ticket.customer_name,
            "service": called_ticket.service_name,
            "isUser": called_ticket.is_user
        },
        "remainingQueue": [
            {
                "id": t.id,
                "ticket": t.ticket_number,
                "name": t.customer_name,
                "service": t.service_name,
                "time": f"~{t.initial_wait_min} min",
                "isPriority": t.is_priority,
                "isUser": t.is_user
            }
            for t in remaining
        ]
    }

@router.post("/delay")
async def report_delay(payload: Optional[TicketDelayRequest] = None, db: Session = Depends(get_db)):
    queue_id = payload.queue_id if payload else "clinica-vida"
    additional = payload.additional_minutes if payload else 5

    waiting_tickets = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).all()

    for t in waiting_tickets:
        t.initial_wait_min += additional
        t.estimated_wait_text = f"{t.initial_wait_min - 3}-{t.initial_wait_min + 5} min"
        t.delay_warning = f"+{additional} min na consulta anterior"
        t.status_detail = f"Previsão ajustada: +{additional} min de atraso detectado por IA"

    db.commit()

    event_data = {
        "type": "DELAY_REPORTED",
        "queueId": queue_id,
        "additionalMinutes": additional,
        "message": "Atraso detectado. A IA recalculou a fila."
    }
    await ws_manager.broadcast(event_data)

    return {
        "message": f"Atraso de +{additional} min registrado. IA recalculou as previsões.",
        "affectedCount": len(waiting_tickets)
    }

@router.post("/manual")
async def add_manual_ticket(payload: TicketManualCreate, db: Session = Depends(get_db)):
    queue_id = payload.queue_id or "clinica-vida"
    import random
    next_num = f"#{random.randint(50, 95)}"

    waiting_count = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).count()

    new_pos = 1 if payload.is_priority else waiting_count + 1

    new_ticket = Ticket(
        id=f"ticket-{uuid.uuid4().hex[:6]}",
        queue_id=queue_id,
        ticket_number=next_num,
        customer_name=payload.name,
        service_name=payload.service_name,
        status="waiting",
        position=new_pos,
        is_priority=payload.is_priority,
        initial_wait_min=(waiting_count + 1) * 12,
        estimated_wait_text=f"~{(waiting_count + 1) * 12} min",
        joined_at=datetime.now().strftime("%H:%M")
    )

    db.add(new_ticket)
    db.commit()

    event_data = {
        "type": "TICKET_ADDED",
        "queueId": queue_id,
        "ticket": {
            "ticket": new_ticket.ticket_number,
            "name": new_ticket.customer_name,
            "service": new_ticket.service_name,
            "isPriority": new_ticket.is_priority
        }
    }
    await ws_manager.broadcast(event_data)

    return {
        "message": f"Senha {new_ticket.ticket_number} emitida no balcão",
        "ticket": {
            "ticket": new_ticket.ticket_number,
            "name": new_ticket.customer_name,
            "service": new_ticket.service_name,
            "time": new_ticket.estimated_wait_text,
            "isPriority": new_ticket.is_priority
        }
    }

@router.post("/{ticket_id}/on-my-way")
async def notify_on_my_way(ticket_id: str):
    await ws_manager.broadcast({
        "type": "CLIENT_ON_MY_WAY",
        "ticketId": ticket_id,
        "message": "Paciente notificou que está a caminho!"
    })
    return {"message": "Atendente notificado: Você está a caminho!"}

@router.delete("/{ticket_id}")
def cancel_ticket(ticket_id: str, db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not t:
        # Search by ticket_number
        t = db.query(Ticket).filter(Ticket.ticket_number == ticket_id).first()
    if t:
        t.status = "cancelled"
        db.commit()
    return {"message": "Desistência registrada com sucesso"}
