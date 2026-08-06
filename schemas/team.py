from pydantic import BaseModel
from typing import Optional, List

class UserInTeam(BaseModel):
    id: int
    email: str
    name: Optional[str] = None

    class Config:
        from_attributes = True

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner_id: Optional[int] = None
    member_ids: Optional[List[int]] = None

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[int] = None
    member_ids: Optional[List[int]] = None
    project_ids: Optional[List[int]] = None

class TeamResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    members: List[UserInTeam] = []

    class Config:
        from_attributes = True