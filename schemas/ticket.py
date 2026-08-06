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
    estimated_hours: Optional[float] = 0.0
    tracked_hours: Optional[float] = 0.0


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[datetime] = None
    project_id: Optional[int] = None
    assigned_to: Optional[int] = None
    estimated_hours: Optional[float] = None
    tracked_hours: Optional[float] = None


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