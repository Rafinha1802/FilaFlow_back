from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.order import SubscriptionOrder
from app.schemas.order import OrderCreate, OrderResponse

router = APIRouter(prefix="/api/checkout", tags=["Checkout"])

@router.post("/orders", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    order = SubscriptionOrder(
        company_name=payload.company_name,
        customer_name=payload.customer_name,
        email=payload.email,
        document=payload.document,
        plan_name=payload.plan_name,
        billing_cycle=payload.billing_cycle,
        payment_method=payload.payment_method,
        amount=payload.amount or 189.0,
        status="paid"
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
