from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from datetime import datetime, timezone
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String, primary_key=True, index=True) # e.g. "ticket-47"
    queue_id = Column(String, ForeignKey("queues.id"), nullable=False)
    ticket_number = Column(String, nullable=False) # e.g. "47" or "#47"
    customer_name = Column(String, nullable=False)
    service_name = Column(String, nullable=False)
    status = Column(String, default="waiting") # waiting, called, attending, delayed, ready, finished, cancelled
    position = Column(Integer, default=1)
    is_user = Column(Boolean, default=False)
    is_priority = Column(Boolean, default=False)
    estimated_wait_text = Column(String, default="30-40 min")
    initial_wait_min = Column(Integer, default=35)
    delay_warning = Column(String, nullable=True)
    status_detail = Column(String, nullable=True)
    joined_at = Column(String, nullable=True) # e.g. "14:05"
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    actual_duration_min = Column(Integer, nullable=True)
