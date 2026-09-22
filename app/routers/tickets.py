from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_company
from app.models.ticket import Ticket
from app.models.queue import Queue
from app.models.company import Company
from app.schemas.ticket import TicketManualCreate, TicketDelayRequest
from app.routers.websocket import ws_manager
from app.services.prediction import QueuePredictor

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

def get_now_utc() -> datetime:
    return datetime.now(timezone.utc)

@router.post("/next")
async def call_next_ticket(
    queue_id: Optional[str] = Query(None),
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Chama a próxima senha da fila.
    Resolve dinamicamente a fila da empresa autenticada caso queue_id não seja informado.
    Registra timestamps reais de início e fim para alimentar a IA preditiva."""
    
    # Resolução dinâmica da fila da empresa
    if not queue_id:
        queue = db.query(Queue).filter(Queue.company_id == current_company.id).first()
        if not queue:
            raise HTTPException(status_code=404, detail="Nenhuma fila encontrada para esta empresa")
        queue_id = queue.id
    else:
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        if not queue:
            raise HTTPException(status_code=404, detail="Fila de atendimento não encontrada")

    if queue.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: esta fila pertence a outra empresa"
        )

    # Buscar senhas aguardando
    waiting_tickets = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).order_by(Ticket.position.asc()).all()

    if not waiting_tickets:
        raise HTTPException(status_code=400, detail="Não há clientes na fila de espera")

    called_ticket = waiting_tickets[0]
    now = get_now_utc()

    # Finalizar atendimentos anteriores em andamento gravando finished_at e actual_duration_min
    current_attending = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "attending"
    ).all()

    for att in current_attending:
        att.status = "finished"
        att.finished_at = now
        if att.started_at:
            st_utc = att.started_at.replace(tzinfo=timezone.utc) if att.started_at.tzinfo is None else att.started_at
            duration = max(1, round((now - st_utc).total_seconds() / 60))
            att.actual_duration_min = duration

    # Iniciar atendimento do novo ticket com started_at real
    called_ticket.status = "attending"
    called_ticket.started_at = now

    # Atualizar posições dos tickets restantes
    remaining = waiting_tickets[1:]
    for idx, t in enumerate(remaining, start=1):
        t.position = idx

    db.commit()

    # Recalcular previsões da fila usando a IA Preditiva baseada em dados reais
    await QueuePredictor.recalculate_queue(queue_id=queue_id, db=db, emit_event=True)

    # Buscar a lista atualizada com previsões da IA
    refreshed_remaining = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).order_by(Ticket.position.asc()).all()

    # Broadcast via WebSocket
    event_data = {
        "type": "TICKET_CALLED",
        "companyId": current_company.id,
        "queueId": queue_id,
        "ticket": {
            "id": called_ticket.id,
            "ticket": called_ticket.ticket_number,
            "name": called_ticket.customer_name,
            "service": called_ticket.service_name,
            "room": queue.room or current_company.room or "Consultório 01",
            "isUser": called_ticket.is_user,
            "startedAt": now.isoformat()
        },
        "remainingCount": len(refreshed_remaining)
    }
    await ws_manager.broadcast(event_data, company_id=current_company.id, queue_id=queue_id)

    return {
        "message": f"Senha {called_ticket.ticket_number} chamada com sucesso",
        "calledTicket": {
            "ticket": called_ticket.ticket_number,
            "name": called_ticket.customer_name,
            "service": called_ticket.service_name,
            "isUser": called_ticket.is_user,
            "startedAt": now.isoformat()
        },
        "remainingQueue": [
            {
                "id": t.id,
                "ticket": t.ticket_number,
                "name": t.customer_name,
                "service": t.service_name,
                "time": t.estimated_wait_text or f"~{t.initial_wait_min} min",
                "isPriority": t.is_priority,
                "isUser": t.is_user,
                "delayWarning": t.delay_warning
            }
            for t in refreshed_remaining
        ]
    }

@router.post("/{ticket_id}/finish")
async def finish_attending_ticket(
    ticket_id: str,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Conclui o atendimento de um ticket, registra finished_at e recalcula previsões da fila."""
    t = db.query(Ticket).filter((Ticket.id == ticket_id) | (Ticket.ticket_number == ticket_id)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")

    queue = db.query(Queue).filter(Queue.id == t.queue_id).first()
    if not queue or queue.company_id != current_company.id:
        raise HTTPException(status_code=403, detail="Acesso negado: fila não pertence à sua empresa")

    now = get_now_utc()
    t.status = "finished"
    t.finished_at = now
    if t.started_at:
        st_utc = t.started_at.replace(tzinfo=timezone.utc) if t.started_at.tzinfo is None else t.started_at
        t.actual_duration_min = max(1, round((now - st_utc).total_seconds() / 60))

    db.commit()

    # Recalcula a IA com a nova métrica real
    await QueuePredictor.recalculate_queue(queue_id=t.queue_id, db=db, emit_event=True)

    await ws_manager.broadcast({
        "type": "TICKET_FINISHED",
        "companyId": current_company.id,
        "queueId": t.queue_id,
        "ticketId": t.id,
        "actualDurationMin": t.actual_duration_min
    }, company_id=current_company.id, queue_id=t.queue_id)

    return {
        "message": f"Atendimento da senha {t.ticket_number} concluído.",
        "actualDurationMin": t.actual_duration_min
    }

@router.post("/recalculate")
async def trigger_ai_recalculation(
    queue_id: Optional[str] = Query(None),
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Executa sob demanda a IA Preditiva de tempo real e atrasos para uma fila."""
    if not queue_id:
        q = db.query(Queue).filter(Queue.company_id == current_company.id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Nenhuma fila encontrada para esta empresa")
        queue_id = q.id
    else:
        q = db.query(Queue).filter(Queue.id == queue_id).first()
        if not q or q.company_id != current_company.id:
            raise HTTPException(status_code=403, detail="Acesso negado à fila informada")

    result = await QueuePredictor.recalculate_queue(queue_id=queue_id, db=db, emit_event=True)
    return {
        "message": "IA recalculou previsões com base nos dados em tempo real.",
        "data": result
    }

@router.post("/delay")
async def report_delay(
    payload: Optional[TicketDelayRequest] = None,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Registra ajuste manual de tempo ou recalcula fila."""
    queue_id = payload.queue_id if payload and payload.queue_id else None
    if not queue_id:
        q = db.query(Queue).filter(Queue.company_id == current_company.id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Nenhuma fila encontrada")
        queue_id = q.id

    additional = payload.additional_minutes if payload else 5

    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=404, detail="Fila não encontrada")

    if queue.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: esta fila pertence a outra empresa"
        )

    waiting_tickets = db.query(Ticket).filter(
        Ticket.queue_id == queue_id,
        Ticket.status == "waiting"
    ).all()

    for t in waiting_tickets:
        t.initial_wait_min += additional
        t.estimated_wait_text = f"{max(2, t.initial_wait_min - 3)}-{t.initial_wait_min + 5} min"
        t.delay_warning = f"+{additional} min na consulta anterior"
        t.status_detail = f"Previsão ajustada: +{additional} min de atraso detectado por IA"

    db.commit()

    event_data = {
        "type": "DELAY_REPORTED",
        "companyId": current_company.id,
        "queueId": queue_id,
        "additionalMinutes": additional,
        "message": "Atraso detectado. A IA recalculou a fila."
    }
    await ws_manager.broadcast(event_data, company_id=current_company.id, queue_id=queue_id)

    return {
        "message": f"Atraso de +{additional} min registrado. IA recalculou as previsões.",
        "affectedCount": len(waiting_tickets)
    }

@router.post("/manual")
async def add_manual_ticket(
    payload: TicketManualCreate,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """Emite senha manual no balcão da empresa."""
    queue_id = payload.queue_id
    if not queue_id:
        q = db.query(Queue).filter(Queue.company_id == current_company.id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Nenhuma fila encontrada")
        queue_id = q.id

    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=404, detail="Fila não encontrada")

    if queue.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: esta fila pertence a outra empresa"
        )

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
        initial_wait_min=(waiting_count + 1) * (queue.initial_wait_min or 15),
        estimated_wait_text=f"~{(waiting_count + 1) * (queue.initial_wait_min or 15)} min",
        joined_at=datetime.now().strftime("%H:%M")
    )

    db.add(new_ticket)
    queue.current_waiting = waiting_count + 1
    db.commit()

    # Recalcula com a IA preditiva
    await QueuePredictor.recalculate_queue(queue_id=queue_id, db=db, emit_event=False)

    event_data = {
        "type": "TICKET_ADDED",
        "companyId": current_company.id,
        "queueId": queue_id,
        "ticket": {
            "ticket": new_ticket.ticket_number,
            "name": new_ticket.customer_name,
            "service": new_ticket.service_name,
            "isPriority": new_ticket.is_priority
        }
    }
    await ws_manager.broadcast(event_data, company_id=current_company.id, queue_id=queue_id)

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
async def notify_on_my_way(ticket_id: str, db: Session = Depends(get_db)):
    """Notifica a recepção/médico que o paciente está a caminho (chamada pública do paciente)."""
    t = db.query(Ticket).filter((Ticket.id == ticket_id) | (Ticket.ticket_number == ticket_id)).first()
    cid = None
    qid = None
    if t:
        qid = t.queue_id
        q = db.query(Queue).filter(Queue.id == t.queue_id).first()
        if q:
            cid = q.company_id

    await ws_manager.broadcast({
        "type": "CLIENT_ON_MY_WAY",
        "ticketId": ticket_id,
        "companyId": cid,
        "queueId": qid,
        "message": "Paciente notificou que está a caminho!"
    }, company_id=cid, queue_id=qid)

    return {"message": "Atendente notificado: Você está a caminho!"}

@router.delete("/{ticket_id}")
def cancel_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Cancela uma senha."""
    t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not t:
        t = db.query(Ticket).filter(Ticket.ticket_number == ticket_id).first()
    if t:
        t.status = "cancelled"
        db.commit()
    return {"message": "Desistência registrada com sucesso"}
