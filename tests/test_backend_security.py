import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.reception import ReceptionPatient
from app.models.queue import Queue
from app.core.security import decode_access_token

client = TestClient(app)

def test_01_login_nonexistent_email():
    """Garante que e-mail inexistente não faz fallback para clinica-vida e retorna 401."""
    res = client.post("/api/auth/login", json={
        "email": f"naoexiste_{uuid.uuid4().hex[:6]}@qualquer.com",
        "password": "qualquercoisa"
    })
    assert res.status_code == 401
    assert "E-mail ou senha incorretos" in res.json()["detail"]

def test_02_login_incorrect_password():
    """Garante que senha errada para empresa existente retorna 401."""
    res = client.post("/api/auth/login", json={
        "email": "atendimento@clinicavida.com.br",
        "password": "senha_totalmente_errada"
    })
    assert res.status_code == 401
    assert "E-mail ou senha incorretos" in res.json()["detail"]

def test_03_login_success_and_valid_jwt():
    """Garante que credenciais corretas geram JWT real e dados corretos do usuário."""
    res = client.post("/api/auth/login", json={
        "email": "atendimento@clinicavida.com.br",
        "password": "123456"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["id"] == "clinica-vida"

    # Validar JWT decodificando
    payload = decode_access_token(data["access_token"])
    assert payload is not None
    assert payload["sub"] == "clinica-vida"
    assert payload["email"] == "atendimento@clinicavida.com.br"

def test_04_register_and_login_flow():
    """Garante cadastro de nova empresa com hash de senha e login subsequente."""
    unique_suffix = uuid.uuid4().hex[:6]
    test_email = f"contato_{unique_suffix}@policlinica.com"
    test_pwd = "SenhaForte@9988"

    # 1. Registrar
    reg_res = client.post("/api/auth/register", json={
        "company_name": f"Policlínica {unique_suffix}",
        "admin_name": "Dr. Fernando",
        "email": test_email,
        "password": test_pwd,
        "category": "Policlínica",
        "unit_name": "Unidade Pinheiros"
    })
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    company_id = reg_data["company"]["id"]

    # Verificar que a senha foi salva como hash bcrypt no banco
    db = SessionLocal()
    try:
        saved_comp = db.query(Company).filter(Company.id == company_id).first()
        assert saved_comp is not None
        assert saved_comp.hashed_password != test_pwd
        assert saved_comp.hashed_password.startswith("$2b$")
    finally:
        db.close()

    # 2. Login com as credenciais criadas
    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": test_pwd
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 3. Testar rota protegida /api/auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["id"] == company_id

def test_05_register_duplicate_email_fails():
    """Garante que cadastro com e-mail duplicado é rejeitado com 400."""
    res = client.post("/api/auth/register", json={
        "company_name": "Outra Clínica",
        "admin_name": "Admin",
        "email": "atendimento@clinicavida.com.br",
        "password": "qualquersenha"
    })
    assert res.status_code == 400
    assert "cadastrad" in res.json()["detail"].lower()

def test_06_route_protection_tickets_without_token():
    """Garante que rotas de atendimento sem token são bloqueadas com 401/403."""
    res_next = client.post("/api/tickets/next?queue_id=clinica-vida")
    assert res_next.status_code == 401

    res_delay = client.post("/api/tickets/delay", json={"queue_id": "clinica-vida", "additional_minutes": 5})
    assert res_delay.status_code == 401

    res_manual = client.post("/api/tickets/manual", json={"name": "Paciente Balcão", "service_name": "Consulta"})
    assert res_manual.status_code == 401

def test_07_cross_tenant_tickets_forbidden():
    """Garante que uma Empresa B não pode chamar nem atrasar a fila da Empresa A."""
    # Obter token da Empresa A (clinica-vida)
    res_a = client.post("/api/auth/login", json={"email": "atendimento@clinicavida.com.br", "password": "123456"})
    token_a = res_a.json()["access_token"]

    # Obter token da Empresa B (examelab)
    res_b = client.post("/api/auth/login", json={"email": "contato@examelab.com.br", "password": "123456"})
    token_b = res_b.json()["access_token"]

    # Empresa B tenta chamar a fila da clinica-vida
    res_cross_next = client.post(
        "/api/tickets/next?queue_id=clinica-vida",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_cross_next.status_code == 403
    assert "Acesso negado" in res_cross_next.json()["detail"]

    # Empresa B tenta aplicar delay na fila da clinica-vida
    res_cross_delay = client.post(
        "/api/tickets/delay",
        json={"queue_id": "clinica-vida", "additional_minutes": 10},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_cross_delay.status_code == 403

    # Empresa A chama sua própria fila: deve ter sucesso (200)
    res_own_next = client.post(
        "/api/tickets/next?queue_id=clinica-vida",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_own_next.status_code == 200
    assert "chamada com sucesso" in res_own_next.json()["message"]

def test_08_reception_protection_and_tenant_isolation():
    """Garante que rotas de recepção são protegidas e os dados não vazam entre empresas."""
    # 1. Sem token -> 401
    assert client.get("/api/reception/waiting-list").status_code == 401

    # Obter tokens
    res_a = client.post("/api/auth/login", json={"email": "atendimento@clinicavida.com.br", "password": "123456"})
    token_a = res_a.json()["access_token"]

    # Criar uma empresa isolada para o teste de recepção
    uniq = uuid.uuid4().hex[:6]
    reg_iso = client.post("/api/auth/register", json={
        "company_name": f"Hospital Isolado {uniq}",
        "admin_name": "Admin Isolado",
        "email": f"hospital_{uniq}@isolado.com",
        "password": "SenhaSecreta123"
    })
    token_iso = reg_iso.json()["access_token"]

    # 2. Listagem da empresa isolada deve estar vazia
    list_iso = client.get("/api/reception/waiting-list", headers={"Authorization": f"Bearer {token_iso}"}).json()
    assert len(list_iso) == 0

    # 3. Empresa isolada adiciona paciente na sua própria recepção
    add_res = client.post("/api/reception/waiting-list", json={
        "patient_name": f"Paciente Exclusivo {uniq}",
        "insurance_name": "Bradesco",
        "procedure": "Exame Cardiológico"
    }, headers={"Authorization": f"Bearer {token_iso}"})
    assert add_res.status_code == 200
    patient_iso_id = add_res.json()["id"]

    # 4. Listagem da empresa isolada agora possui 1 paciente
    list_iso_after = client.get("/api/reception/waiting-list", headers={"Authorization": f"Bearer {token_iso}"}).json()
    assert len(list_iso_after) == 1
    assert list_iso_after[0]["id"] == patient_iso_id

    # 5. clinica-vida NÃO vê esse paciente isolado
    list_a = client.get("/api/reception/waiting-list", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert not any(p["id"] == patient_iso_id for p in list_a)

    # 6. clinica-vida tenta alterar status do paciente da empresa isolada -> 404
    update_cross = client.put(
        f"/api/reception/waiting-list/{patient_iso_id}/status?status=authorized",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert update_cross.status_code == 404

def test_09_websocket_rooms_isolation():
    """Garante que eventos transmitidos pelo WebSocket são isolados por sala/empresa."""
    res_a = client.post("/api/auth/login", json={"email": "atendimento@clinicavida.com.br", "password": "123456"})
    token_a = res_a.json()["access_token"]

    # Conectar cliente 1 na sala da clinica-vida
    with client.websocket_connect("/ws?company_id=clinica-vida") as ws1:
        # Conectar cliente 2 na sala da examelab
        with client.websocket_connect("/ws?company_id=examelab") as ws2:
            # Emitir senha manual na clinica-vida
            res_manual = client.post(
                "/api/tickets/manual",
                json={"queue_id": "clinica-vida", "name": "Carlos Teste WS", "service_name": "Consulta"},
                headers={"Authorization": f"Bearer {token_a}"}
            )
            assert res_manual.status_code == 200

            # ws1 (clinica-vida) DEVE receber a mensagem
            msg1 = ws1.receive_json()
            assert msg1["type"] == "TICKET_ADDED"
            assert msg1["companyId"] == "clinica-vida"
            assert msg1["ticket"]["name"] == "Carlos Teste WS"

            # ws2 (examelab) NÃO deve receber a mensagem da clinica-vida
            ws2.send_json({"type": "ping"})
            msg2 = ws2.receive_json()
            assert msg2["type"] == "pong" # Não recebeu o evento da clinica-vida!
