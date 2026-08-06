from pydantic import BaseModel
from typing import Optional
from datetime import date


class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "Média"
    status: str = "To Do"
    project_id: int
    estimated_hours: Optional[float] = 0.0
    due_date: Optional[date] = None  


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[int] = None
    estimated_hours: Optional[float] = None
    tracked_hours: Optional[float] = None
    due_date: Optional[date] = None 


class TicketResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    estimated_hours: Optional[float] = 0.0
    tracked_hours: Optional[float] = 0.0
    due_date: Optional[date] = None  
    project_id: int

    class Config:
        orm_mode = True