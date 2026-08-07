from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.project import Project
from models.ticket import Ticket 
from models.user import User
from schemas.project import ProjectCreate, ProjectResponse
from core.security import get_current_user, require_manager_or_admin
from typing import List

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    # 1. Cria o projeto
    db_project = Project(
        name=project.name,
        description=project.description,
        team_id=project.team_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    if project.ticket_ids:
        db.query(Ticket).filter(Ticket.id.in_(project.ticket_ids)).update(
            {"project_id": db_project.id}, synchronize_session=False
        )
        db.commit()

    return db_project

@router.get("/", response_model=List[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = db.query(Project).all()
    return projects

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, 
    project_update: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    db_proj = db.query(Project).filter(Project.id == project_id).first()
    if not db_proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    #atualiza a info do proj
    db_proj.name = project_update.name
    db_proj.description = project_update.description
    db_proj.team_id = project_update.team_id
    db.commit()
    
    # 2. Atualizar as tarefas: as que já não estão na lista perdem o projeto (ficam a Null)
    current_tickets = db.query(Ticket).filter(Ticket.project_id == project_id).all()
    for t in current_tickets:
        if project_update.ticket_ids is not None and t.id not in project_update.ticket_ids:
            t.project_id = None  # Remove do projeto
            
    if project_update.ticket_ids:
        db.query(Ticket).filter(Ticket.id.in_(project_update.ticket_ids)).update(
            {"project_id": project_id}, synchronize_session=False
        )
    
    db.commit()
    db.refresh(db_proj)
    return db_proj

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    db_proj = db.query(Project).filter(Project.id == project_id).first()
    if not db_proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    db.delete(db_proj)
    db.commit()
    return None