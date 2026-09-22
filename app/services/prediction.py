from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging

from app.models.ticket import Ticket
from app.models.queue import Queue
from app.routers.websocket import ws_manager

logger = logging.getLogger("filaflow.prediction")

def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

class QueuePredictor:
    """Motor de IA Preditiva para Filas em Tempo Real.
    Substitui números estáticos por estimativas baseadas em histórico real de duração e atrasos em curso."""

    @staticmethod
    def calculate_metrics(queue_id: str, db: Session) -> Dict[str, Any]:
        """Calcula a média real de atendimento para a fila com base nos tickets finalizados."""
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        baseline = queue.initial_wait_min if queue and queue.initial_wait_min else 15

        # Buscar até os últimos 15 atendimentos finalizados com duração calculada
        finished = db.query(Ticket).filter(
            Ticket.queue_id == queue_id,
            Ticket.status == "finished",
            Ticket.actual_duration_min != None,
            Ticket.actual_duration_min > 0
        ).order_by(Ticket.finished_at.desc()).limit(15).all()

        if finished:
            durations = [t.actual_duration_min for t in finished]
            avg_duration = round(sum(durations) / len(durations))
            # Garantir limite razoável (mínimo 3 minutos)
            avg_duration = max(3, avg_duration)
            sample_size = len(durations)
        else:
            avg_duration = baseline
            sample_size = 0

        return {
            "avg_duration_min": avg_duration,
            "sample_size": sample_size,
            "baseline_min": baseline
        }

    @staticmethod
    def check_active_overtime(queue_id: str, avg_duration: int, db: Session) -> Dict[str, Any]:
        """Verifica se o paciente atualmente em consulta/atendimento já ultrapassou o tempo médio esperado."""
        attending = db.query(Ticket).filter(
            Ticket.queue_id == queue_id,
            Ticket.status == "attending"
        ).first()

        now = datetime.now(timezone.utc)
        delay_min = 0
        elapsed_min = 0
        remaining_current_min = avg_duration

        if attending and attending.started_at:
            started_utc = _to_utc(attending.started_at)
            elapsed_seconds = (now - started_utc).total_seconds()
            elapsed_min = max(0, int(elapsed_seconds / 60))

            if elapsed_min > avg_duration:
                delay_min = elapsed_min - avg_duration
                remaining_current_min = 3  # Estimativa de encerramento em breve
            else:
                remaining_current_min = max(2, avg_duration - elapsed_min)

        return {
            "attending_ticket": attending,
            "elapsed_min": elapsed_min,
            "delay_min": delay_min,
            "remaining_current_min": remaining_current_min
        }

    @classmethod
    async def recalculate_queue(
        cls,
        queue_id: str,
        db: Session,
        emit_event: bool = True
    ) -> Dict[str, Any]:
        """Executa a heurística de IA preditiva para recalcular as previsões de todos os tickets na fila."""
        queue = db.query(Queue).filter(Queue.id == queue_id).first()
        if not queue:
            return {"error": "Fila não encontrada"}

        metrics = cls.calculate_metrics(queue_id, db)
        avg_duration = metrics["avg_duration_min"]

        overtime = cls.check_active_overtime(queue_id, avg_duration, db)
        delay_min = overtime["delay_min"]
        rem_current = overtime["remaining_current_min"]

        # Buscar senhas aguardando ordenadas por posição
        waiting_tickets = db.query(Ticket).filter(
            Ticket.queue_id == queue_id,
            Ticket.status == "waiting"
        ).order_by(Ticket.position.asc()).all()

        updated_tickets = []
        for idx, ticket in enumerate(waiting_tickets):
            # Tempo previsto: tempo restante da consulta atual + (posição anterior * média real)
            accumulated_min = rem_current + (idx * avg_duration)
            accumulated_min = max(2, accumulated_min)

            # Ajuste de faixa estimada
            min_bound = max(1, accumulated_min - 3)
            max_bound = accumulated_min + 4
            estimated_text = f"{min_bound}-{max_bound} min"

            ticket.initial_wait_min = accumulated_min
            ticket.estimated_wait_text = estimated_text

            if delay_min > 0:
                ticket.delay_warning = f"+{delay_min} min na consulta anterior"
                ticket.status_detail = f"Previsão ajustada: +{delay_min} min de atraso detectado por IA"
            else:
                ticket.delay_warning = None
                ticket.status_detail = "Previsão recalculada por IA (dados reais)"

            updated_tickets.append({
                "id": ticket.id,
                "ticket": ticket.ticket_number,
                "name": ticket.customer_name,
                "wait_min": accumulated_min,
                "estimated_text": estimated_text,
                "delay_warning": ticket.delay_warning
            })

        queue.current_waiting = len(waiting_tickets)
        db.commit()

        event_data = {
            "type": "AI_PREDICTIONS_UPDATED",
            "companyId": queue.company_id,
            "queueId": queue_id,
            "avgDurationMin": avg_duration,
            "delayDetectedMin": delay_min,
            "waitingCount": len(waiting_tickets),
            "tickets": updated_tickets
        }

        if emit_event:
            await ws_manager.broadcast(event_data, company_id=queue.company_id, queue_id=queue_id)

        return event_data
