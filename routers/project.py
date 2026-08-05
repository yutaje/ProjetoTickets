from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.project import Project
from models.user import User
from schemas.project import ProjectCreate, ProjectResponse
from core.security import get_current_user, require_manager
from typing import List

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)

#criar um proj
@router.post("/", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    db_project = Project(
        name=project.name,
        description=project.description
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

#listar os projs
@router.get("/", response_model=List[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = db.query(Project).all()
    return projects