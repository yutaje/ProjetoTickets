from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "Média"
    status: Optional[str] = "To Do"
    project_id: int
    assigned_to_id: Optional[int] = None
    estimated_hours: Optional[float] = 0.0
    due_date: Optional[datetime] = None

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    estimated_hours: Optional[float] = None
    tracked_hours: Optional[float] = None
    due_date: Optional[datetime] = None

class TicketResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    project_id: int
    assigned_to_id: Optional[int] = None
    estimated_hours: float
    tracked_hours: float
    due_date: Optional[datetime] = None

    class Config:
        from_attributes = True