from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.team import Team
from models.user import User
from models.project import Project
from schemas.team import TeamCreate, TeamResponse, TeamUpdate
from core.security import require_manager_or_admin, get_current_user
from typing import List

router = APIRouter(
    prefix="/teams",
    tags=["Teams"]
)

@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    team: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    owner_id = team.owner_id if team.owner_id else current_user.id
    
    db_team = Team(
        name=team.name,
        description=team.description,
        owner_id=owner_id
    )
    
    # Adicionar membros selecionados
    members_to_add = [current_user]
    if team.member_ids:
        users = db.query(User).filter(User.id.in_(team.member_ids)).all()
        members_to_add = users
        
    # Garantir que o líder está incluído nos membros
    owner = db.query(User).filter(User.id == owner_id).first()
    if owner and owner not in members_to_add:
        members_to_add.append(owner)
        
    db_team.members = members_to_add
    
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team

@router.get("/", response_model=List[TeamResponse])
def get_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Team).all()

@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    team_update: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Equipa não encontrada")
    
    if team_update.name is not None:
        team.name = team_update.name
    if team_update.description is not None:
        team.description = team_update.description
    if team_update.owner_id is not None:
        team.owner_id = team_update.owner_id
    
    if team_update.member_ids is not None:
        if len(team_update.member_ids) > 0:
            users = db.query(User).filter(User.id.in_(team_update.member_ids)).all()
            team.members = users
        else:
            team.members = []
        
    if team_update.project_ids is not None:
        all_projects = db.query(Project).all()
        for p in all_projects:
            if p.id in team_update.project_ids:
                p.team_id = team.id
            elif p.team_id == team.id:
                p.team_id = None

    db.commit()
    db.refresh(team)
    return team

@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Equipa não encontrada")
    
    projects = db.query(Project).filter(Project.team_id == team.id).all()
    for p in projects:
        p.team_id = None
    
    db.delete(team)
    db.commit()
    return None