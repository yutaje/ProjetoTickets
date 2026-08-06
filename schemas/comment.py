from pydantic import BaseModel
from datetime import datetime


class CommentCreate(BaseModel):
    text: str


class CommentResponse(BaseModel):
    id: int
    text: str
    created_at: datetime
    ticket_id: int
    author_id: int

    class Config:
        from_attributes = True