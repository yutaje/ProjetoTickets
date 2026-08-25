from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.client import Client
from models.project import Project
from models.user import User
from schemas.client import ClientCreate, ClientUpdate, ClientResponse
from core.security import get_current_user

router = APIRouter(
    prefix="/clients",
    tags=["Clients"]
)

@router.get("/", response_model=list[ClientResponse])
def get_clients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clients = db.query(Client).all()
    results = []
    for c in clients:
        proj_list = db.query(Project).filter(Project.client_id == c.id).all()
        results.append(ClientResponse(
            id=c.id,
            name=c.name,
            company=c.company,
            email=c.email,
            phone=c.phone,
            projects=[{"id": p.id, "name": p.name} for p in proj_list],
            project_ids=[p.id for p in proj_list]
        ))
    return results

@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not client_data.name or not client_data.name.strip():
        raise HTTPException(status_code=400, detail="O nome do cliente é obrigatório.")
    
    if not client_data.company or not client_data.company.strip():
        raise HTTPException(status_code=400, detail="A empresa do cliente é obrigatória.")
    
    db_client = Client(
        name=client_data.name.strip(),
        company=client_data.company.strip(),
        email=client_data.email.strip() if client_data.email else None,
        phone=client_data.phone.strip() if client_data.phone else None
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    if client_data.project_ids:
        db.query(Project).filter(Project.id.in_(client_data.project_ids)).update(
            {"client_id": db_client.id}, synchronize_session=False
        )
        db.commit()

    proj_list = db.query(Project).filter(Project.client_id == db_client.id).all()
    return ClientResponse(
        id=db_client.id,
        name=db_client.name,
        company=db_client.company,
        email=db_client.email,
        phone=db_client.phone,
        projects=[{"id": p.id, "name": p.name} for p in proj_list],
        project_ids=[p.id for p in proj_list]
    )

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    if role not in ["admin", "manager", "gestor de operações", "gestor de projeto", "gestor de projetos"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admins e Managers podem editar clientes."
        )
    
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    
    if client_update.name is not None:
        db_client.name = client_update.name
    if client_update.company is not None:
        db_client.company = client_update.company
    if client_update.email is not None:
        db_client.email = client_update.email
    if client_update.phone is not None:
        db_client.phone = client_update.phone

    db.commit()

    if client_update.project_ids is not None:
        db.query(Project).filter(
            Project.client_id == client_id,
            ~Project.id.in_(client_update.project_ids)
        ).update({"client_id": None}, synchronize_session=False)

        if client_update.project_ids:
            db.query(Project).filter(Project.id.in_(client_update.project_ids)).update(
                {"client_id": client_id}, synchronize_session=False
            )
        db.commit()

    db.refresh(db_client)
    proj_list = db.query(Project).filter(Project.client_id == db_client.id).all()
    return ClientResponse(
        id=db_client.id,
        name=db_client.name,
        company=db_client.company,
        email=db_client.email,
        phone=db_client.phone,
        projects=[{"id": p.id, "name": p.name} for p in proj_list],
        project_ids=[p.id for p in proj_list]
    )

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    if role not in ["admin", "manager", "gestor de operações"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admins e Managers podem apagar clientes."
        )
    
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    
    db.query(Project).filter(Project.client_id == client_id).update(
        {"client_id": None}, synchronize_session=False
    )
    
    db.delete(db_client)
    db.commit()
    return None