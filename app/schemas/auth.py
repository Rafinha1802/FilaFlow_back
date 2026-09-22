from pydantic import BaseModel, EmailStr
from typing import Optional

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class RegisterRequest(BaseModel):
    company_name: str
    admin_name: str
    email: str
    password: str
    cnpj: Optional[str] = None
    category: Optional[str] = "Clínica"
    unit_name: Optional[str] = "Unidade Jardins"
    phone: Optional[str] = None
    queue_name: Optional[str] = None
    attendant_name: Optional[str] = None
