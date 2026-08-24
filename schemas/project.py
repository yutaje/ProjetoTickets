from pydantic import BaseModel, Field
from typing import Optional, List

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    team_id: Optional[int] = None
    client_id: Optional[int] = None
    ticket_ids: Optional[List[int]] = [] 

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[int] = None
    client_id: Optional[int] = None  
    ticket_ids: Optional[List[int]] = []

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    team_id: Optional[int] = None
    client_id: Optional[int] = None 

    class Config:
        from_attributes = True