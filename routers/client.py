from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.client import Client
from models.user import User
from schemas.client import ClientCreate, ClientUpdate, ClientResponse
from core.security import get_current_user

router = APIRouter(
    prefix="/clients",
    tags=["Clients"]
)

@router.get("/", response_model=list[ClientResponse])
def get_clients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Client).all()

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_client(client_data: ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not client_data.name or not client_data.name.strip():
        raise HTTPException(status_code=400, detail="O nome do cliente é obrigatório.")
    
    if not client_data.company or not client_data.company.strip():
        raise HTTPException(status_code=400, detail="A empresa do cliente é obrigatória.")
    
    db_client = Client(**client_data.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member")
    if role not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admins e Managers podem editar clientes."
        )
    
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    
    update_data = client_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_client, key, value)
        
    db.commit()
    db.refresh(db_client)
    return db_client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member")
    if role not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admins e Managers podem apagar clientes."
        )
    
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    
    db.delete(db_client)
    db.commit()
    return None