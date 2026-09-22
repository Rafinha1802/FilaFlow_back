from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.company import Company

security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)

def get_current_company(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Company:
    """Valida o token JWT Bearer e retorna a Company autenticada.
    Lança HTTP 401 se o token estiver ausente, inválido ou a empresa não existir."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    company_id: Optional[str] = payload.get("sub")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado: identificador de empresa ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empresa associada ao token não encontrada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return company

def get_optional_company(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db)
) -> Optional[Company]:
    """Retorna a Company se um token válido for fornecido, ou None se for anônimo."""
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        if not payload or not payload.get("sub"):
            return None
        return db.query(Company).filter(Company.id == payload["sub"]).first()
    except Exception:
        return None
