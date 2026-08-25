from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.team import Team
from models.user import User
from models.project import Project
from models.notification import Notification
from models.chat import ChatRoom, RoomMember
from schemas.team import TeamCreate, TeamResponse, TeamUpdate
from core.security import require_manager_or_admin, get_current_user
from typing import List

router = APIRouter(
    prefix="/teams",
    tags=["Teams"]
)

def sync_team_removal_from_project_chats(team_id: int, remaining_member_ids: list, db: Session):
    """
    Remove utilizadores de TODAS as salas de chat (Gerais e Subchats) dos projetos 
    ligados a esta equipa caso deixem de pertencer a qualquer equipa do projeto.
    """
    projects = db.query(Project).filter(
        (Project.teams.any(Team.id == team_id)) |
        (Project.team_id == team_id)
    ).all()

    for proj in projects:
        allowed_user_ids = set()
        teams = getattr(proj, "teams", []) or []
        
        # Se for modelo legado com team_id único
        if not teams and getattr(proj, "team_id", None):
            t_obj = db.query(Team).filter(Team.id == proj.team_id).first()
            if t_obj:
                teams = [t_obj]

        for t in teams:
            if t.id == team_id:
                allowed_user_ids.update(remaining_member_ids)
            else:
                if getattr(t, "leader_id", None): allowed_user_ids.add(t.leader_id)
                if getattr(t, "manager_id", None): allowed_user_ids.add(t.manager_id)
                if getattr(t, "owner_id", None): allowed_user_ids.add(t.owner_id)
                if hasattr(t, "members"): allowed_user_ids.update([m.id for m in t.members if hasattr(m, "id")])
                if hasattr(t, "users"): allowed_user_ids.update([u.id for u in t.users if hasattr(u, "id")])

        # Remove utilizadores sem permissão de todas as salas deste projeto
        project_rooms = db.query(ChatRoom).filter(ChatRoom.project_id == proj.id).all()
        for room in project_rooms:
            db.query(RoomMember).filter(
                RoomMember.room_id == room.id,
                ~RoomMember.user_id.in_(allowed_user_ids)
            ).delete(synchronize_session=False)

    db.commit()

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
    
    members_to_add = [current_user]
    if team.member_ids:
        users = db.query(User).filter(User.id.in_(team.member_ids)).all()
        members_to_add = users
        
    owner = db.query(User).filter(User.id == owner_id).first()
    if owner and owner not in members_to_add:
        members_to_add.append(owner)
        
    db_team.members = members_to_add
    
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    
    for member in db_team.members:
        notif = Notification(
            user_id=member.id,
            message=f"Foste integrado na nova equipa: {db_team.name}"
        )
        db.add(notif)
    db.commit()

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
    
    old_member_ids = {m.id for m in team.members}

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
    
    # Sincroniza e remove utilizadores excluídos das salas de chat dos projetos
    sync_team_removal_from_project_chats(
        team_id=team_id,
        remaining_member_ids=[m.id for m in team.members],
        db=db
    )

    new_member_ids = {m.id for m in team.members}
    added_member_ids = new_member_ids - old_member_ids

    for member_id in added_member_ids:
        if member_id != current_user.id:
            notif = Notification(
                user_id=member_id,
                message=f"Foste adicionado à equipa: {team.name}"
            )
            db.add(notif)
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
    
    # Remove membros desta equipa de todos os chats dos projetos antes de apagar
    sync_team_removal_from_project_chats(
        team_id=team_id,
        remaining_member_ids=[],
        db=db
    )

    projects = db.query(Project).filter(Project.team_id == team.id).all()
    for p in projects:
        p.team_id = None
    
    db.delete(team)
    db.commit()
    return None