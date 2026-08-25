from pydantic import BaseModel, EmailStr
from typing import Optional, List

class ProjectSimpleResponse(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
        from_attributes = True

class ClientBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None

class ClientCreate(ClientBase):
    project_ids: Optional[List[int]] = []

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    project_ids: Optional[List[int]] = None

class ClientResponse(ClientBase):
    id: int
    projects: List[ProjectSimpleResponse] = []
    project_ids: List[int] = []

    class Config:
        orm_mode = True
        from_attributes = True