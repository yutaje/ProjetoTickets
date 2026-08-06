from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from core.security import get_current_user
from database import get_db
from models.ticket import Ticket
from models.comment import Comment
from schemas.ticket import TicketCreate, TicketUpdate, TicketResponse
from schemas.comment import CommentCreate, CommentResponse


router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get("/", response_model=List[TicketResponse])
def get_tickets(db: Session = Depends(get_db)):
    return db.query(Ticket).all()


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status=ticket.status,
        project_id=ticket.project_id,
        estimated_hours=ticket.estimated_hours,
        due_date=ticket.due_date  # <-- Grava na BD
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


@router.put("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    ticket_update: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    update_data = ticket_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ticket, key, value)

    db.commit()
    db.refresh(db_ticket)
    return db_ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    
    db.delete(db_ticket)
    db.commit()
    return None


#comments do ticket
@router.post("/{ticket_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(ticket_id: int, comment: CommentCreate, author_id: int, db: Session = Depends(get_db)):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    
    db_comment = Comment(text=comment.text, ticket_id=ticket_id, author_id=author_id)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


@router.get("/{ticket_id}/comments", response_model=List[CommentResponse])
def get_ticket_comments(ticket_id: int, db: Session = Depends(get_db)):
    return db.query(Comment).filter(Comment.ticket_id == ticket_id).all()


@router.get("/me/stats")
def get_ticket_stats(db: Session = Depends(get_db)):
    total_tickets = db.query(Ticket).count()
    to_do = db.query(Ticket).filter(Ticket.status == "To Do").count()
    in_progress = db.query(Ticket).filter(Ticket.status == "In Progress").count()
    done = db.query(Ticket).filter(Ticket.status == "Done").count()
    
    return {
        "total_tickets": total_tickets,
        "to_do": to_do,
        "in_progress": in_progress,
        "done": done
    }