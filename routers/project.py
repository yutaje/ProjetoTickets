from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.project import Project, project_teams
from models.ticket import Ticket
from models.team import Team
from models.user import User
from models.chat import ChatRoom, RoomMember
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from core.security import get_current_user

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)

def sync_project_chat_members(project: Project, db: Session):
    if not project or not project.id:
        return

    # 1. Procura ou cria o canal Geral do Projeto
    general_room = db.query(ChatRoom).filter(
        ChatRoom.project_id == project.id,
        ChatRoom.is_general == True
    ).first()

    if not general_room:
        general_room = ChatRoom(
            name=f"# Geral - {project.name}",
            type="project",
            project_id=project.id,
            is_general=True
        )
        db.add(general_room)
        db.commit()
        db.refresh(general_room)
    else:
        general_room.name = f"# Geral - {project.name}"
        db.commit()

    # 2. Extrai todos os membros das equipas associadas ao projeto
    all_member_ids = []
    teams = getattr(project, "teams", []) or []
    
    for t in teams:
        if getattr(t, "leader_id", None):
            all_member_ids.append(t.leader_id)
        if getattr(t, "manager_id", None):
            all_member_ids.append(t.manager_id)
        if getattr(t, "owner_id", None):
            all_member_ids.append(t.owner_id)
        if hasattr(t, "members"):
            all_member_ids.extend([m.id for m in t.members if hasattr(m, "id")])
        if hasattr(t, "users"):
            all_member_ids.extend([u.id for u in t.users if hasattr(u, "id")])

    all_member_ids = list(set(all_member_ids))

    # 3. Sincroniza participantes na tabela room_members
    current_members = db.query(RoomMember).filter(RoomMember.room_id == general_room.id).all()
    current_member_ids = [m.user_id for m in current_members]

    for uid in all_member_ids:
        if uid not in current_member_ids:
            db.add(RoomMember(room_id=general_room.id, user_id=uid))

    for m in current_members:
        if m.user_id not in all_member_ids:
            db.delete(m)

    db.commit()

def calculate_project_progress(project: Project, db: Session):
    tickets = db.query(Ticket).filter(Ticket.project_id == project.id).all()
    if not tickets:
        return 0.0, 0.0, 0.0

    # 1. Soma total das horas estimadas de todas as tarefas do projeto
    total_est_hours = sum(t.estimated_hours or 0.0 for t in tickets)
    
    # 2. Soma das horas reais gastas
    total_tracked_hours = sum(t.tracked_hours or 0.0 for t in tickets)

    # 3. Soma as horas estimadas APENAS das tarefas concluídas ("Done")
    completed_est_hours = sum(
        (t.estimated_hours or 0.0) for t in tickets 
        if t.status and t.status.lower() in ["done", "concluído", "concluido"]
    )

    # 4. Calcula a percentagem baseada no peso das horas estimadas das tarefas concluídas face ao total estimado
    if total_est_hours > 0:
        progress = round((completed_est_hours / total_est_hours) * 100, 1)
    else:
        done_tickets = [t for t in tickets if t.status and t.status.lower() in ["done", "concluído", "concluido"]]
        progress = round((len(done_tickets) / len(tickets)) * 100, 1) if len(tickets) > 0 else 0.0

    return min(progress, 100.0), round(total_est_hours, 2), round(total_tracked_hours, 2)

@router.get("/", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    role = getattr(current_user, "role", "Member").lower()
    
    if role in ["admin", "manager", "gestor de operações", "gestor de projeto", "gestor de projetos"]:
        projects = db.query(Project).all()
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
                
        projects = db.query(Project).filter(
            (Project.teams.any(Team.id.in_(led_team_ids))) |
            (Project.tickets.any(Ticket.team_id.in_(led_team_ids))) |
            (Project.tickets.any(Ticket.assigned_to_id.in_(team_member_ids)))
        ).distinct().all()
    else:
        user_team_ids = [t.id for t in getattr(current_user, "teams", [])] if hasattr(current_user, "teams") else []
        projects = db.query(Project).filter(
            (Project.teams.any(Team.id.in_(user_team_ids))) |
            (Project.tickets.any((Ticket.assigned_to_id == current_user.id) | (Ticket.creator_id == current_user.id)))
        ).distinct().all()

    results = []
    for proj in projects:
        progress, total_h, tracked_h = calculate_project_progress(proj, db)
        proj_teams = getattr(proj, "teams", []) or []
        
        results.append(ProjectResponse(
            id=proj.id,
            name=proj.name,
            description=proj.description,
            client_id=proj.client_id,
            due_date=getattr(proj, "due_date", None),
            teams=[{"id": t.id, "name": t.name} for t in proj_teams],
            team_ids=[t.id for t in proj_teams],
            progress_percentage=progress,
            total_estimated_hours=total_h,
            completed_estimated_hours=tracked_h
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
        client_id=project.client_id,
        due_date=project.due_date
    )

    target_team_ids = list(project.team_ids or [])
    if project.team_id and project.team_id not in target_team_ids:
        target_team_ids.append(project.team_id)

    if target_team_ids:
        teams_to_add = db.query(Team).filter(Team.id.in_(target_team_ids)).all()
        db_project.teams = teams_to_add

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    if project.ticket_ids:
        db.query(Ticket).filter(Ticket.id.in_(project.ticket_ids)).update(
            {"project_id": db_project.id}, synchronize_session=False
        )
        db.commit()

    # Criação e sincronização automática do chat geral com as equipas do projeto
    sync_project_chat_members(db_project, db)

    progress, total_h, tracked_h = calculate_project_progress(db_project, db)
    proj_teams = getattr(db_project, "teams", []) or []
    
    return ProjectResponse(
        id=db_project.id,
        name=db_project.name,
        description=db_project.description,
        client_id=db_project.client_id,
        due_date=getattr(db_project, "due_date", None),
        teams=[{"id": t.id, "name": t.name} for t in proj_teams],
        team_ids=[t.id for t in proj_teams],
        progress_percentage=progress,
        total_estimated_hours=total_h,
        completed_estimated_hours=tracked_h
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
    if project_update.due_date is not None:
        db_proj.due_date = project_update.due_date

    db_proj.client_id = project_update.client_id

    if project_update.team_ids is not None:
        teams_to_add = db.query(Team).filter(Team.id.in_(project_update.team_ids)).all()
        db_proj.teams = teams_to_add
    elif project_update.team_id is not None:
        teams_to_add = db.query(Team).filter(Team.id == project_update.team_id).all()
        db_proj.teams = teams_to_add

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

    # Sincroniza participantes do chat geral após atualização das equipas ou nome do projeto
    sync_project_chat_members(db_proj, db)

    progress, total_h, tracked_h = calculate_project_progress(db_proj, db)
    proj_teams = getattr(db_proj, "teams", []) or []
    
    return ProjectResponse(
        id=db_proj.id,
        name=db_proj.name,
        description=db_proj.description,
        client_id=db_proj.client_id,
        due_date=getattr(db_proj, "due_date", None),
        teams=[{"id": t.id, "name": t.name} for t in proj_teams],
        team_ids=[t.id for t in proj_teams],
        progress_percentage=progress,
        total_estimated_hours=total_h,
        completed_estimated_hours=tracked_h
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
    
    # Remove automaticamente salas de chat associadas a este projeto
    db.query(ChatRoom).filter(ChatRoom.project_id == project_id).delete(synchronize_session=False)

    db.delete(db_proj)
    db.commit()
    return None