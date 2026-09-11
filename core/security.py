import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.role_permission import RolePermission
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

def verify_dynamic_permission(db: Session, current_user: User, module_key: str) -> bool:
    """
    Lê estritamente da base de dados o estado da permissão para o cargo atual,
    garantindo que o Administrador tem sempre acesso total (bypass).
    """
    user_role = str(getattr(current_user, "role", "Member")).strip().capitalize()
    
    # Bypass absoluto para Administradores
    if user_role == "Admin":
        return True
    
    perm = db.query(RolePermission).filter(
        RolePermission.role == user_role,
        RolePermission.module == module_key
    ).first()
    
    return bool(perm.can_view) if perm else False

def require_manager_or_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_role = str(getattr(current_user, "role", "Member")).strip().capitalize()
    
    if user_role == "Admin":
        return current_user
        
    has_mgmt_perm = verify_dynamic_permission(db, current_user, "can_approve_reports")
    
    if not has_mgmt_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso negado. O cargo '{user_role}' não tem permissões de gestão ativas na base de dados."
        )
    return current_user

def require_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_role = str(getattr(current_user, "role", "Member")).strip().capitalize()
    
    if user_role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito. Sem permissões de administração ativas na base de dados."
        )
    return current_user

def check_permission(module_key: str):
    """
    Dependency para validar dinamicamente se o cargo do utilizador atual 
    tem permissão ativa. Administradores têm bypass automático.
    """
    def permission_dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        user_role = str(getattr(current_user, "role", "Member")).strip().capitalize()
        
        # Bypass absoluto para Administradores
        if user_role == "Admin":
            return current_user
        
        perm = db.query(RolePermission).filter(
            RolePermission.role == user_role,
            RolePermission.module == module_key
        ).first()
        
        has_access = bool(perm.can_view) if perm else False
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. O teu cargo ('{user_role}') não tem esta permissão ativa nas definições da empresa."
            )
            
        return current_user
    return permission_dependency