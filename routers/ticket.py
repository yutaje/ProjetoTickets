from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models.ticket import Ticket
from models.project import Project
from models.user import User
from models.comment import Comment
from schemas.ticket import TicketCreate, TicketResponse
from schemas.comment import CommentCreate, CommentResponse
from core.security import get_current_user, require_manager
from typing import List, Optional


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)


#criar um ticket (so admins)
@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket: TicketCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
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
        priority=ticket.priority,
        deadline=ticket.deadline,
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
    status: Optional[str] = Query(None, description="Filtrar por status (ex: To Do, In Progress)"),
    search: Optional[str] = Query(None, description="Pesquisar por palavra no título"),
    skip: int = Query(0, description="Quantos registos saltar (para paginação)"),
    limit: int = Query(20, description="Limite máximo de registos a devolver"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    
    if status:
        query = query.filter(Ticket.status == status)
        
    if search:
        query = query.filter(Ticket.title.contains(search))
        
    return query.offset(skip).limit(limit).all()

#lista apenas os tickets do user loggado 
@router.get("/me", response_model=List[TicketResponse])
def get_my_tickets(
    status: Optional[str] = Query(None, description="Filtrar por status (ex: To Do, In Progress)"),
    search: Optional[str] = Query(None, description="Pesquisar por palavra no título"),
    skip: int = Query(0, description="Quantos registos saltar (para paginação)"),
    limit: int = Query(20, description="Limite máximo de registos a devolver"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.assigned_to == current_user.id)
    
    if status:
        query = query.filter(Ticket.status == status)
        
    if search:
        query = query.filter(Ticket.title.contains(search))
        
    return query.offset(skip).limit(limit).all()

#estatisticas dos tickets do user loggado
@router.get("/me/stats")
def get_my_ticket_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total = db.query(Ticket).filter(Ticket.assigned_to == current_user.id).count()
    to_do = db.query(Ticket).filter(Ticket.assigned_to == current_user.id, Ticket.status == "To Do").count()
    in_progress = db.query(Ticket).filter(Ticket.assigned_to == current_user.id, Ticket.status == "In Progress").count()
    done = db.query(Ticket).filter(Ticket.assigned_to == current_user.id, Ticket.status == "Done").count()

    return {
        "total_tickets": total,
        "to_do": to_do,
        "in_progress": in_progress,
        "done": done
    }

#lista um ticket pelo ID
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
    
    if current_user.role == "Manager":
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
        db_ticket.project_id = ticket_update.project_id
        db_ticket.assigned_to = ticket_update.assigned_to
        db_ticket.status = ticket_update.status
        db_ticket.priority = ticket_update.priority
        db_ticket.deadline = ticket_update.deadline
    else:
        if db_ticket.assigned_to != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Acesso negado. Apenas podes atualizar os teus próprios tickets."
            )
        db_ticket.status = ticket_update.status

    db.commit()
    db.refresh(db_ticket)
    return db_ticket

# apagar um ticket
@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado!")
    
    db.delete(db_ticket)
    db.commit()
    return None

# adicionar um comentario a um ticket
@router.post("/{ticket_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment_to_ticket(
    ticket_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado!")
    
    new_comment = Comment(
        text=comment.text,
        ticket_id=ticket_id,
        author_id=current_user.id
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

# listar os comentarios de um ticket
@router.get("/{ticket_id}/comments", response_model=List[CommentResponse])
def get_ticket_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado!")
        
    comments = db.query(Comment).filter(Comment.ticket_id == ticket_id).all()
    return comments