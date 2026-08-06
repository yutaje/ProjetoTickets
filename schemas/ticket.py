from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TicketBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "To Do"
    priority: str = "Média"
    deadline: Optional[datetime] = None
    project_id: int
    assigned_to: Optional[int] = None

class TicketCreate(TicketBase):
    pass

class TicketResponse(TicketBase):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str                       
    deadline: Optional[datetime]        
    project_id: int
    assigned_to: Optional[int]

    class Config:
        from_attributes = True