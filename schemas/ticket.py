from pydantic import BaseModel
from typing import Optional

class TicketBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "To Do"
    project_id: int
    assigned_to: Optional[int] = None

class TicketCreate(TicketBase):
    pass

class TicketResponse(TicketBase):
    id: int

    class Config:
        from_attributes = True