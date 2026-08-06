import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secreta")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais (Token inválido ou expirado)",
        headers={"Authorization": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
        
    return user

def require_manager_or_admin(current_user: User = Depends(get_current_user)):
    # IMPRIME NO TERMINAL DO BACKEND O QUE ESTÁ A VIR DA BD
    print(f"--- DEBUG PERMISSÕES ---")
    print(f"Utilizador: {current_user.email}")
    print(f"Role exata na BD: '{current_user.role}' (Tipo: {type(current_user.role)})")
    
    user_role = str(current_user.role).strip().capitalize()
    
    if user_role not in ["Manager", "Admin"]:
        print(f"BLOQUEADO! Role normalizada '{user_role}' não é Manager nem Admin.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso negado. A tua role detetada foi: '{current_user.role}'"
        )
    
    print(f"AUTORIZADO!")
    return current_user

def require_admin(current_user: User = Depends(get_current_user)):
    user_role = str(current_user.role).strip().capitalize()
    if user_role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito exclusivamente a Admins."
        )
    return current_user