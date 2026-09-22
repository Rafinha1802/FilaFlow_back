import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.queue import Queue
from app.models.ticket import Ticket
from app.models.order import SubscriptionOrder

client = TestClient(app)

def get_auth_token(email="atendimento@clinicavida.com.br", password="123456"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]

def test_01_predictive_ai_and_real_timestamps():
    """Garante registro real de started_at e finished_at e cálculo preditivo de tempo."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Adicionar duas senhas na fila
    add1 = client.post(
        "/api/tickets/manual",
        json={"name": "Paciente IA 1", "service_name": "Consulta"},
        headers=headers
    )
    assert add1.status_code == 200

    add2 = client.post(
        "/api/tickets/manual",
        json={"name": "Paciente IA 2", "service_name": "Consulta"},
        headers=headers
    )
    assert add2.status_code == 200

    # 2. Chamar a primeira senha (POST /next sem queue_id -> resolução dinâmica)
    call1 = client.post("/api/tickets/next", headers=headers)
    assert call1.status_code == 200
    called1 = call1.json()["calledTicket"]
    assert "startedAt" in called1
    assert called1["startedAt"] is not None

    # Verificar no banco que started_at foi registrado
    db = SessionLocal()
    try:
        t1 = db.query(Ticket).filter(Ticket.ticket_number == called1["ticket"]).first()
        assert t1 is not None
        assert t1.status == "attending"
        assert t1.started_at is not None

        # Simular que começou há 25 minutos para testar a IA de cálculo de duração
        t1.started_at = datetime.now(timezone.utc) - timedelta(minutes=25)
        db.commit()
    finally:
        db.close()

    # 3. Chamar a próxima senha: o primeiro ticket deve ser finalizado com duration calculada
    call2 = client.post("/api/tickets/next", headers=headers)
    assert call2.status_code == 200

    db = SessionLocal()
    try:
        t1_after = db.query(Ticket).filter(Ticket.ticket_number == called1["ticket"]).first()
        assert t1_after.status == "finished"
        assert t1_after.finished_at is not None
        assert t1_after.actual_duration_min is not None
        assert t1_after.actual_duration_min >= 20
    finally:
        db.close()

    # 4. Testar endpoint /recalculate
    recalc = client.post("/api/tickets/recalculate", headers=headers)
    assert recalc.status_code == 200
    data = recalc.json()["data"]
    assert "avgDurationMin" in data
    assert "waitingCount" in data

def test_02_multi_professional_queues():
    """Garante suporte a múltiplos profissionais/filas e consulta de filas por empresa."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Consultar /api/queues/me
    me_queues = client.get("/api/queues/me", headers=headers)
    assert me_queues.status_code == 200
    queues_list = me_queues.json()
    assert len(queues_list) >= 1
    assert all(q["companyId"] == "clinica-vida" for q in queues_list)

    # 2. Criar uma nova fila/médico adicional para a mesma empresa
    unique_name = f"Dra. Camila - Dermatologia {uuid.uuid4().hex[:4]}"
    create_q = client.post("/api/queues", json={
        "name": unique_name,
        "attendant_name": "Dra. Camila Dermatologista",
        "room": "Consultório 07",
        "initial_wait_min": 25
    }, headers=headers)
    assert create_q.status_code == 200
    new_q_data = create_q.json()
    assert new_q_data["company_id"] == "clinica-vida"
    assert new_q_data["name"] == unique_name

    # 3. Verificar que /api/queues/me agora inclui a nova fila
    me_queues_after = client.get("/api/queues/me", headers=headers).json()
    assert any(q["id"] == new_q_data["id"] for q in me_queues_after)

def test_03_checkout_pix_and_payment_flow():
    """Garante criação de pedido pending com Pix BR Code e confirmação de pagamento."""
    # 1. Criar pedido
    order_payload = {
        "company_name": "Clínica Nova Saúde",
        "customer_name": "Dr. Marcelo",
        "email": "marcelo@novasaude.com",
        "plan_name": "Profissional",
        "amount": 189.00,
        "payment_method": "pix"
    }
    order_res = client.post("/api/checkout/orders", json=order_payload)
    assert order_res.status_code == 200
    order = order_res.json()
    
    # Status inicial deve ser 'pending'
    assert order["status"] == "pending"
    order_id = order["id"]

    # Deve conter código Pix Copia e Cola no padrão oficial EMV (começa com 000201)
    assert "pix_code" in order
    assert order["pix_code"] is not None
    assert order["pix_code"].startswith("00020126")
    assert len(order["pix_code"]) > 50

    # Deve conter QR Code em base64
    assert "pix_qr_code_base64" in order
    assert order["pix_qr_code_base64"].startswith("data:image/svg+xml;base64,")

    # 2. Consultar status via polling
    status_res = client.get(f"/api/checkout/orders/{order_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "pending"

    # 3. Confirmar pagamento via endpoint /pay
    pay_res = client.post(f"/api/checkout/orders/{order_id}/pay")
    assert pay_res.status_code == 200
    paid_order = pay_res.json()
    assert paid_order["status"] == "paid"
    assert paid_order["paid_at"] is not None

    # 4. Testar webhook de confirmação em outro pedido
    order2 = client.post("/api/checkout/orders", json=order_payload).json()
    order2_id = order2["id"]
    assert order2["status"] == "pending"

    webhook_res = client.post("/api/checkout/webhook", json={
        "action": "payment.created",
        "order_id": order2_id
    })
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "processed"

    # Verificar no banco que order2 foi pago
    order2_check = client.get(f"/api/checkout/orders/{order2_id}").json()
    assert order2_check["status"] == "paid"
    assert order2_check["paid_at"] is not None
