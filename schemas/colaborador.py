from typing import Optional
from pydantic import BaseModel, EmailStr


class Colaborador(BaseModel):
    matricula: str
    nome: str
    setor: Optional[str] = ""
    email: str
    arquivo_pdf: Optional[str] = None

