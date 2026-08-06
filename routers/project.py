from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.project import Project
from models.user import User
from schemas.project import ProjectCreate, ProjectResponse
from core.security import get_current_user, require_manager_or_admin
from typing import List

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)

# Criar um projeto (Permitido a Managers e Admins)
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    db_project = Project(
        name=project.name,
        description=project.description
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

# Listar os projetos (Disponível para todos os autenticados)
@router.get("/", response_model=List[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = db.query(Project).all()
    return projects