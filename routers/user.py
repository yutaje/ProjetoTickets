from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from schemas.user import UserCreate, UserResponse
from passlib.context import CryptContext

#config das encriptações das pass
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    #verifica se o mail já existe na bd
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Este email já está registado!")
    
    #encripta a pass antes de guardar na bd
    hashed_password = pwd_context.hash(user.password)
    
    db_user = User(
        name=user.name, 
        email=user.email, 
        hashed_password=hashed_password, 
        role=user.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user