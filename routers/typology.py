from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.typology import Typology

router = APIRouter(prefix="/typologies", tags=["Tipologias"])

@router.get("/")
def get_typologies(db: Session = Depends(get_db)):
    return db.query(Typology).filter(Typology.is_active == True).all()

@router.post("/")
def create_typology(data: dict, db: Session = Depends(get_db)):
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="O nome da tipologia é obrigatório.")
    
    existing = db.query(Typology).filter(Typology.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Essa tipologia já existe.")
        
    typology = Typology(name=name)
    db.add(typology)
    db.commit()
    db.refresh(typology)
    return typology