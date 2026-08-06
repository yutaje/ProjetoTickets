from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.team import Team
from models.user import User
from schemas.team import TeamCreate, TeamResponse
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
    db_team = Team(
        name=team.name,
        description=team.description,
        owner_id=current_user.id
    )
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team

@router.get("/", response_model=List[TeamResponse])
def get_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    teams = db.query(Team).all()
    return teams