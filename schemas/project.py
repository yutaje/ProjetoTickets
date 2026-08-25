from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class TeamSimpleResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    team_id: Optional[int] = None
    team_ids: Optional[List[int]] = []
    client_id: Optional[int] = None
    due_date: Optional[date] = None
    ticket_ids: Optional[List[int]] = [] 

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[int] = None
    team_ids: Optional[List[int]] = None
    client_id: Optional[int] = None  
    due_date: Optional[date] = None
    ticket_ids: Optional[List[int]] = []

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    team_id: Optional[int] = None
    client_id: Optional[int] = None 
    due_date: Optional[date] = None
    teams: List[TeamSimpleResponse] = []
    team_ids: List[int] = []
    progress_percentage: Optional[float] = 0.0
    total_estimated_hours: Optional[float] = 0.0
    completed_estimated_hours: Optional[float] = 0.0

    class Config:
        from_attributes = True