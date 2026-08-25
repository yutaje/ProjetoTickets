from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.project import Project
from models.ticket import Ticket
from models.team import Team
from models.user import User
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from core.security import get_current_user

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)

def calculate_project_progress(project: Project, db: Session):
    tickets = db.query(Ticket).filter(Ticket.project_id == project.id).all()
    if not tickets:
        return 0.0, 0.0, 0.0

    total_est_hours = sum(t.estimated_hours or 0.0 for t in tickets)
    
    # Tarefas concluídas
    done_tickets = [t for t in tickets if t.status and t.status.lower() in ["done", "concluído", "concluido"]]
    done_est_hours = sum(t.estimated_hours or 0.0 for t in done_tickets)

    # Se existirem horas estimadas definidas, calcula pela soma das horas estimadas concluídas vs total
    if total_est_hours > 0:
        progress = round((done_est_hours / total_est_hours) * 100, 1)
    else:
        # Fallback para contagem unitária de tarefas caso ainda não haja estimativas
        progress = round((len(done_tickets) / len(tickets)) * 100, 1) if len(tickets) > 0 else 0.0

    return min(progress, 100.0), round(total_est_hours, 2), round(done_est_hours, 2)

@router.get("/", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    role = getattr(current_user, "role", "Member").lower()
    
    # 1. Admin, Gestor de Operações e Gestor de Projetos vêem TODOS os projetos
    if role in ["admin", "manager", "gestor de operações", "gestor de projeto", "gestor de projetos"]:
        projects = db.query(Project).all()
    # 2. Líder de Equipa: vê apenas projetos associados às tarefas da sua equipa
    elif "líder de equipa" in role or "lider de equipa" in role:
        led_teams = db.query(Team).filter(
            (getattr(Team, "leader_id", None) == current_user.id) |
            (getattr(Team, "manager_id", None) == current_user.id)
        ).all()
        led_team_ids = [t.id for t in led_teams]
        
        team_member_ids = []
        for t in led_teams:
            if hasattr(t, "members"):
                team_member_ids.extend([m.id for m in t.members])
            if hasattr(t, "users"):
                team_member_ids.extend([u.id for u in t.users])
                
        project_ids = db.query(Ticket.project_id).filter(
            (Ticket.team_id.in_(led_team_ids)) |
            (Ticket.assigned_to_id.in_(team_member_ids))
        ).distinct().all()
        
        valid_ids = [p[0] for p in project_ids if p[0] is not None]
        projects = db.query(Project).filter(Project.id.in_(valid_ids)).all()
    # 3. Técnico / Member: apenas projetos onde tem tarefas atribuídas ou criadas
    else:
        user_project_ids = db.query(Ticket.project_id).filter(
            (Ticket.assigned_to_id == current_user.id) |
            (Ticket.creator_id == current_user.id)
        ).distinct().all()
        
        valid_ids = [p[0] for p in user_project_ids if p[0] is not None]
        projects = db.query(Project).filter(Project.id.in_(valid_ids)).all()

    # Injeta os cálculos de progresso em cada projeto
    results = []
    for proj in projects:
        progress, total_h, done_h = calculate_project_progress(proj, db)
        results.append(ProjectResponse(
            id=proj.id,
            name=proj.name,
            description=proj.description,
            team_id=proj.team_id,
            client_id=proj.client_id,
            due_date=getattr(proj, "due_date", None),
            progress_percentage=progress,
            total_estimated_hours=total_h,
            completed_estimated_hours=done_h
        ))

    return results

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    if role not in ["admin", "manager", "gestor de operações", "gestor de projeto", "gestor de projetos"]:
        raise HTTPException(status_code=403, detail="Apenas Gestores de Projeto ou Administradores podem criar projetos.")

    db_project = Project(
        name=project.name,
        description=project.description,
        team_id=project.team_id,
        client_id=project.client_id,
        due_date=project.due_date
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    if project.ticket_ids:
        db.query(Ticket).filter(Ticket.id.in_(project.ticket_ids)).update(
            {"project_id": db_project.id}, synchronize_session=False
        )
        db.commit()

    progress, total_h, done_h = calculate_project_progress(db_project, db)
    return ProjectResponse(
        id=db_project.id,
        name=db_project.name,
        description=db_project.description,
        team_id=db_project.team_id,
        client_id=db_project.client_id,
        due_date=getattr(db_project, "due_date", None),
        progress_percentage=progress,
        total_estimated_hours=total_h,
        completed_estimated_hours=done_h
    )

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, 
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    db_proj = db.query(Project).filter(Project.id == project_id).first()
    if not db_proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    if role not in ["admin", "manager", "gestor de operações", "gestor de projeto", "gestor de projetos"]:
        raise HTTPException(status_code=403, detail="Acesso negado para editar este projeto.")
    
    if project_update.name is not None:
        db_proj.name = project_update.name
    if project_update.description is not None:
        db_proj.description = project_update.description
    
    if project_update.team_id is not None:
        db_proj.team_id = project_update.team_id
    else:
        db_proj.team_id = None

    if project_update.due_date is not None:
        db_proj.due_date = project_update.due_date

    db_proj.client_id = project_update.client_id
    db.commit()
    
    if project_update.ticket_ids is not None:
        current_tickets = db.query(Ticket).filter(Ticket.project_id == project_id).all()
        for t in current_tickets:
            if t.id not in project_update.ticket_ids:
                t.project_id = None
                
        if project_update.ticket_ids:
            db.query(Ticket).filter(Ticket.id.in_(project_update.ticket_ids)).update(
                {"project_id": project_id}, synchronize_session=False
            )
    
    db.commit()
    db.refresh(db_proj)

    progress, total_h, done_h = calculate_project_progress(db_proj, db)
    return ProjectResponse(
        id=db_proj.id,
        name=db_proj.name,
        description=db_proj.description,
        team_id=db_proj.team_id,
        client_id=db_proj.client_id,
        due_date=getattr(db_proj, "due_date", None),
        progress_percentage=progress,
        total_estimated_hours=total_h,
        completed_estimated_hours=done_h
    )

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    if role not in ["admin", "manager", "gestor de operações"]:
        raise HTTPException(status_code=403, detail="Apenas Administradores podem apagar projetos.")

    db_proj = db.query(Project).filter(Project.id == project_id).first()
    if not db_proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    db.query(Ticket).filter(Ticket.project_id == project_id).update(
        {"project_id": None}, synchronize_session=False
    )
    
    db.delete(db_proj)
    db.commit()
    return None