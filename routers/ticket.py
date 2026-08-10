from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models.ticket import Ticket
from models.user import User
from models.worklog import WorkLog
from models.project import Project
from models.team import Team
from schemas.ticket import TicketCreate, TicketUpdate, TicketResponse
from core.security import get_current_user
from typing import List, Optional
from datetime import date

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)

def filter_tickets_by_permissions(query, current_user: User, db: Session):
    role = getattr(current_user, "role", "Member")
    
    if role == "Admin":
        return query
        
    user_teams = db.query(Team.id).filter(
        (Team.owner_id == current_user.id) | 
        (Team.members.any(id=current_user.id))
    ).statement.correlate(None) # <--- Correção explícita do select
    
    user_projects = db.query(Project.id).filter(
        (Project.team_id.in_(user_teams)) | 
        (Project.team_id.is_(None))
    ).statement.correlate(None) # <--- Correção explícita do select
    
    return query.filter(
        (Ticket.assigned_to_id == current_user.id) | 
        (Ticket.project_id.in_(user_projects))
    )

@router.get("/me/stats")
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    query = filter_tickets_by_permissions(query, current_user, db)
    
    all_tickets = query.all()
    today = date.today()
    
    to_do = sum(1 for t in all_tickets if t.status and t.status.lower() in ['to do', 'a fazer'])
    in_progress = sum(1 for t in all_tickets if t.status and t.status.lower() in ['in progress', 'em progresso'])
    in_review = sum(1 for t in all_tickets if t.status and t.status.lower() in ['in review', 'em revisão', 'em revisao'])
    done = sum(1 for t in all_tickets if t.status and t.status.lower() in ['done', 'concluído', 'concluido'])
    
    overdue = sum(1 for t in all_tickets if t.due_date and t.due_date < today and t.status and t.status.lower() not in ['done', 'concluído', 'concluido'])
    due_today = sum(1 for t in all_tickets if t.due_date and t.due_date == today and t.status and t.status.lower() not in ['done', 'concluído', 'concluido'])

    today_logs = db.query(WorkLog).filter(
        WorkLog.user_id == current_user.id,
        WorkLog.log_date == today
    ).all()
    hours_today = sum(log.hours for log in today_logs)

    role = getattr(current_user, "role", "Member")

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
    query = db.query(Ticket).filter(Ticket.is_running == True)
    query = filter_tickets_by_permissions(query, current_user, db)
    return query.all()

@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Converter strings vazias em None para evitar erros na BD
    s_date = ticket.start_date if ticket.start_date else None
    d_date = ticket.due_date if ticket.due_date else None

    db_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status=ticket.status,
        project_id=ticket.project_id if ticket.project_id else None,
        client_id=ticket.client_id,
        assigned_to_id=ticket.assigned_to_id,
        estimated_hours=ticket.estimated_hours,
        due_date=d_date,
        start_date=s_date
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    
    if db_ticket.assigned_to_id and db_ticket.assigned_to_id != current_user.id:
        from models.notification import Notification
        notif = Notification(
            user_id=db_ticket.assigned_to_id,
            message=f"Foste atribuído a uma nova tarefa: {db_ticket.title}"
        )
        db.add(notif)
        db.commit()
        
    return db_ticket

@router.get("/", response_model=List[TicketResponse])
def get_tickets(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    query = filter_tickets_by_permissions(query, current_user, db)
    
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
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    db_ticket = query.first()
    
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou não tens permissão para editá-la.")
    
    old_assignee = db_ticket.assigned_to_id
    
    update_data = ticket_update.model_dump(exclude_unset=True)
    session_hours = update_data.pop("session_hours", None)
    
    # Garantir que se vier uma string vazia nas datas, passa a None
    if "start_date" in update_data and not update_data["start_date"]:
        update_data["start_date"] = None
    if "due_date" in update_data and not update_data["due_date"]:
        update_data["due_date"] = None
    
    for key, value in update_data.items():
        setattr(db_ticket, key, value)
        
    db.commit()
    
    new_assignee = db_ticket.assigned_to_id
    if new_assignee and new_assignee != old_assignee and new_assignee != current_user.id:
        from models.notification import Notification
        notif = Notification(
            user_id=new_assignee,
            message=f"Foste realocado para a tarefa: {db_ticket.title}"
        )
        db.add(notif)
        db.commit()
    
    if session_hours is not None and session_hours > 0:
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
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    db_ticket = query.first()
    
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou não tens permissão para apagá-la.")
    
    db.delete(db_ticket)
    db.commit()
    return None