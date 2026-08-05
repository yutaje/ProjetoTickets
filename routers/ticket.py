from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db

from models.ticket import Ticket
from models.project import Project
from models.user import User
from schemas.ticket import TicketCreate, TicketResponse
from core.security import get_current_user
from typing import List

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)

# criar um ticket
@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket: TicketCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == ticket.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado!")
    
    if ticket.assigned_to:
        user = db.query(User).filter(User.id == ticket.assigned_to).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilizador atribuído não encontrado!")

    db_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        project_id=ticket.project_id,
        assigned_to=ticket.assigned_to
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

#listar todos os tickets
@router.get("/", response_model=List[TicketResponse])
def get_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tickets = db.query(Ticket).all()
    return tickets

# lista um ticket específico pelo id
@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado!")
    return ticket

#atualizar um ticket
@router.put("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    ticket_update: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado!")
    
    if ticket_update.project_id != db_ticket.project_id:
        project = db.query(Project).filter(Project.id == ticket_update.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado!")
            
    if ticket_update.assigned_to and ticket_update.assigned_to != db_ticket.assigned_to:
        user = db.query(User).filter(User.id == ticket_update.assigned_to).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilizador atribuído não encontrado!")

    db_ticket.title = ticket_update.title
    db_ticket.description = ticket_update.description
    db_ticket.status = ticket_update.status
    db_ticket.project_id = ticket_update.project_id
    db_ticket.assigned_to = ticket_update.assigned_to

    db.commit()
    db.refresh(db_ticket)
    return db_ticket

# apagar um ticket
@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado!")
    
    db.delete(db_ticket)
    db.commit()
    return None