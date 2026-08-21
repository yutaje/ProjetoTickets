from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class FeedbackRequestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    ticket_id: Optional[int] = None
    project_id: Optional[int] = None
    target_user_ids: Optional[List[int]] = [] # IDs dos utilizadores a quem se pede feedback
    deadline: datetime

class FeedbackResponseCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class FeedbackResponseOut(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class FeedbackRequestOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    ticket_id: Optional[int] = None
    project_id: Optional[int] = None
    deadline: datetime
    created_at: datetime
    created_by_name: Optional[str] = None
    has_responded: Optional[bool] = False
    average_rating: Optional[float] = 0.0
    responses: List[FeedbackResponseOut] = []

    class Config:
        from_attributes = True