from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.deps import get_current_company
from app.models.company import Company
from app.models.queue import Queue
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Autentica uma empresa por e-mail e senha com hash bcrypt e retorna um JWT válido."""
    normalized_email = payload.email.strip().lower()
    company = db.query(Company).filter(func.lower(Company.email) == normalized_email).first()

    # Validação rigorosa de credenciais sem fallback silencioso
    if not company or not company.hashed_password or not verify_password(payload.password, company.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos"
        )

    # Geração do JWT real assinado
    token_payload = {
        "sub": company.id,
        "email": company.email,
        "companyName": company.company_name
    }
    access_token = create_access_token(token_payload)

    user_info = {
        "id": company.id,
        "name": company.attendant_name,
        "email": company.email or payload.email,
        "companyName": company.company_name,
        "unitName": company.unit_name,
        "category": company.category,
        "room": company.room
    }

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_info
    )

@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Cadastra uma nova empresa, armazena a senha com hash bcrypt e gera fila inicial."""
    normalized_email = payload.email.strip().lower()
    existing = db.query(Company).filter(func.lower(Company.email) == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe uma conta cadastrada com este e-mail"
        )

    if not payload.password or len(payload.password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter no mínimo 4 caracteres"
        )

    company_id = payload.company_name.lower().replace(" ", "-").replace("/", "-") + "-" + uuid.uuid4().hex[:4]
    hashed_pwd = get_password_hash(payload.password)

    new_company = Company(
        id=company_id,
        company_name=payload.company_name,
        unit_name=payload.unit_name or "Unidade Principal",
        category=payload.category or "Clínica",
        attendant_name=payload.attendant_name or payload.admin_name,
        email=normalized_email,
        hashed_password=hashed_pwd,
        phone=payload.phone,
        room="Consultório 01"
    )
    db.add(new_company)

    # Cria automaticamente a primeira fila da empresa
    queue_name = payload.queue_name or "Triagem e Atendimento Geral"
    new_queue = Queue(
        id=company_id,
        company_id=company_id,
        name=queue_name,
        attendant_name=new_company.attendant_name,
        room=new_company.room,
        initial_wait_min=20,
        current_waiting=0
    )
    db.add(new_queue)
    db.commit()
    db.refresh(new_company)

    # Gera token de acesso imediato para conveniência no onboarding
    access_token = create_access_token({
        "sub": new_company.id,
        "email": new_company.email,
        "companyName": new_company.company_name
    })

    return {
        "message": "Empresa cadastrada com sucesso",
        "access_token": access_token,
        "token_type": "bearer",
        "company": {
            "id": new_company.id,
            "companyName": new_company.company_name,
            "unitName": new_company.unit_name,
            "category": new_company.category,
            "attendantName": new_company.attendant_name,
            "email": new_company.email,
            "room": new_company.room
        }
    }

@router.get("/me")
def get_me(current_company: Company = Depends(get_current_company)):
    """Retorna os dados da empresa autenticada via token JWT."""
    return {
        "id": current_company.id,
        "name": current_company.attendant_name,
        "email": current_company.email,
        "companyName": current_company.company_name,
        "unitName": current_company.unit_name,
        "category": current_company.category,
        "room": current_company.room
    }
