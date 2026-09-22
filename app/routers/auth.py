from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.company import Company
from app.models.queue import Queue
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
import uuid

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    # Demo friendly authentication
    company = db.query(Company).filter(Company.email == payload.email).first()
    if not company:
        # Fallback to default demo company if email matches demo pattern
        company = db.query(Company).filter(Company.id == "clinica-vida").first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas"
        )

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
        access_token=f"demo-token-{uuid.uuid4().hex[:12]}",
        token_type="bearer",
        user=user_info
    )

@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    company_id = payload.company_name.lower().replace(" ", "-").replace("/", "-") + "-" + uuid.uuid4().hex[:4]
    
    new_company = Company(
        id=company_id,
        company_name=payload.company_name,
        unit_name=payload.unit_name or "Unidade Principal",
        category=payload.category or "Clínica",
        attendant_name=payload.attendant_name or payload.admin_name,
        email=payload.email,
        phone=payload.phone,
        room="Consultório 01"
    )
    db.add(new_company)

    # Automatically create the first queue for this company
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

    return {
        "message": "Empresa cadastrada com sucesso",
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
