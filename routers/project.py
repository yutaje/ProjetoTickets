from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.project import Project
from models.ticket import Ticket
from models.user import User
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from routers.auth import get_current_user

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)

@router.get("/", response_model=list[ProjectResponse])
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Project).all()

@router.post("/", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_project = Project(
        name=project.name,
        description=project.description,
        team_id=project.team_id,
        client_id=project.client_id
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

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, 
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_proj = db.query(Project).filter(Project.id == project_id).first()
    if not db_proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    if project_update.name is not None:
        db_proj.name = project_update.name
    if project_update.description is not None:
        db_proj.description = project_update.description
    
    if project_update.team_id is not None:
        db_proj.team_id = project_update.team_id
    else:
        db_proj.team_id = None

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
    return db_proj

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_proj = db.query(Project).filter(Project.id == project_id).first()
    if not db_proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    db.query(Ticket).filter(Ticket.project_id == project_id).update(
        {"project_id": None}, synchronize_session=False
    )
    
    db.delete(db_proj)
    db.commit()
    return None