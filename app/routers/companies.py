from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.company import Company
from app.schemas.company import CompanyResponse

router = APIRouter(prefix="/api/companies", tags=["Companies"])

@router.get("", response_model=List[CompanyResponse])
def get_companies(category: Optional[str] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Company)
    if category:
        query = query.filter(Company.category.ilike(f"%{category}%"))
    if search:
        query = query.filter(Company.company_name.ilike(f"%{search}%"))
    return query.all()

@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return company
