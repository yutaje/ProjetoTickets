from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models.ticket import Ticket
from models.user import User
from schemas.ticket import TicketCreate, TicketUpdate, TicketResponse
from core.security import get_current_user
from typing import List, Optional
from datetime import date
from models.worklog import WorkLog

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)

@router.get("/me/stats")
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    role = getattr(current_user, "role", "Member")
    
    if role not in ["Admin", "Manager"]:
        query = query.filter(Ticket.assigned_to_id == current_user.id)
        
    all_tickets = query.all()
    from datetime import date
    today = date.today()
    
    to_do = sum(1 for t in all_tickets if t.status and t.status.lower() in ['to do', 'a fazer'])
    in_progress = sum(1 for t in all_tickets if t.status and t.status.lower() in ['in progress', 'em progresso'])
    in_review = sum(1 for t in all_tickets if t.status and t.status.lower() in ['in review', 'em revisão', 'em revisao'])
    done = sum(1 for t in all_tickets if t.status and t.status.lower() in ['done', 'concluído', 'concluido'])
    
    # CORRIGIDO: Removido o .date() desnecessário que causava o crash
    overdue = sum(1 for t in all_tickets if t.due_date and t.due_date < today and t.status and t.status.lower() not in ['done', 'concluído', 'concluido'])
    due_today = sum(1 for t in all_tickets if t.due_date and t.due_date == today and t.status and t.status.lower() not in ['done', 'concluído', 'concluido'])

    # --- LÓGICA DAS HORAS DE HOJE ---
    from models.worklog import WorkLog
    today_logs = db.query(WorkLog).filter(
        WorkLog.user_id == current_user.id,
        WorkLog.log_date == today
    ).all()
    hours_today = sum(log.hours for log in today_logs)

    return {
        "user_id": current_user.id,
        "role": role,
        "total_tickets": len(all_tickets),
        "to_do": to_do,
        "in_progress": in_progress,
        "in_review": in_review,
        "done": done,
        "overdue": overdue,
        "due_today": due_today,
        "hours_today": round(hours_today, 2)
    }

@router.get("/active", response_model=List[TicketResponse])
def get_active_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # O filtro base é simplesmente tudo o que está a correr
    return db.query(Ticket).filter(Ticket.is_running == True).all()


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
        assigned_to_id=ticket.assigned_to_id,
        estimated_hours=ticket.estimated_hours,
        due_date=ticket.due_date
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@router.get("/", response_model=List[TicketResponse])
def get_tickets(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    role = getattr(current_user, "role", "Member")
    
    #filtrar automaticamente se o utilizador não for Admin ou Manager
    if role not in ["Admin", "Manager"]:
        query = query.filter(Ticket.assigned_to_id == current_user.id)
    
    if search:
        query = query.filter(Ticket.title.ilike(f"%{search}%"))
    if status:
        query = query.filter(Ticket.status == status)
        
    return query.all()

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
    
    # 1. Retiramos as "session_hours" do dicionário para não dar erro
    session_hours = update_data.pop("session_hours", None)
    
    # 2. Atualizamos os restantes campos normais da Tarefa (status, etc)
    for key, value in update_data.items():
        setattr(db_ticket, key, value)
        
    db.commit()
    
    # 3. Criamos o registo invisível se o valor for maior que 0 (mesmo que sejam 0.002 horas)
    if session_hours is not None and session_hours > 0:
        from models.worklog import WorkLog  
        from datetime import date

        print(f"--- A GUARDAR WORKLOG: User {current_user.id} trabalhou {session_hours}h ---")
        
        new_log = WorkLog(
            user_id=current_user.id,
            ticket_id=db_ticket.id,
            hours=session_hours,
            log_date=date.today()
        )
        db.add(new_log)
        db.commit()
        
    db.refresh(db_ticket)
    return db_ticket

@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    db.delete(db_ticket)
    db.commit()
    return None