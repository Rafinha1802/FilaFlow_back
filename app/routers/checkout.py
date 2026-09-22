from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.core.database import get_db
from app.models.order import SubscriptionOrder
from app.schemas.order import OrderCreate, OrderResponse, WebhookPayload
from app.services.payment import PaymentGatewayService

router = APIRouter(prefix="/api/checkout", tags=["Checkout"])

@router.post("/orders", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """Cria um novo pedido com status inicial 'pending' e gera o payload Pix oficial com QR Code."""
    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    
    order = SubscriptionOrder(
        id=order_id,
        company_name=payload.company_name,
        customer_name=payload.customer_name,
        email=payload.email,
        document=payload.document,
        plan_name=payload.plan_name,
        billing_cycle=payload.billing_cycle,
        payment_method=payload.payment_method,
        amount=payload.amount or 189.0,
        status="pending"
    )

    # Gera o Pix EMV BR Code oficial e QR Code
    PaymentGatewayService.process_new_order(order)

    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order_status(order_id: str, db: Session = Depends(get_db)):
    """Consulta o status atual do pedido (para polling de pagamento na tela de checkout)."""
    order = db.query(SubscriptionOrder).filter(SubscriptionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return order

@router.post("/orders/{order_id}/pay", response_model=OrderResponse)
async def confirm_payment_endpoint(order_id: str, db: Session = Depends(get_db)):
    """Confirma o pagamento do pedido (aprovação instantânea via Pix ou gateway)."""
    try:
        updated_order = await PaymentGatewayService.confirm_payment(order_id=order_id, db=db)
        return updated_order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/webhook")
async def payment_webhook(payload: WebhookPayload, db: Session = Depends(get_db)):
    """Webhook para recebimento de notificações assíncronas do gateway (Mercado Pago, Stripe, Asaas)."""
    order_id = payload.order_id
    if not order_id and payload.data and "id" in payload.data:
        order_id = payload.data["id"]

    if not order_id:
        # Tenta recuperar de query params ou headers se necessário
        return {"status": "ignored", "reason": "No order_id found in webhook payload"}

    order = db.query(SubscriptionOrder).filter(SubscriptionOrder.id == order_id).first()
    if not order:
        return {"status": "not_found", "order_id": order_id}

    if order.status != "paid":
        await PaymentGatewayService.confirm_payment(order_id=order_id, db=db)

    return {"status": "processed", "order_id": order_id}
