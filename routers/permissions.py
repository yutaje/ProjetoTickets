from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.role_permission import RolePermission
from models.user import User
from core.security import get_current_user, check_permission
from pydantic import BaseModel

router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"]
)

class PermissionUpdate(BaseModel):
    role: str
    module: str
    can_view: bool
    can_create: bool
    can_edit: bool
    can_delete: bool
    can_approve: bool

@router.get("/")
def get_all_permissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    permissions = db.query(RolePermission).all()
    
    # Descobre os cargos reais na tabela de users e os módulos existentes
    existing_roles = [r[0] for r in db.query(User.role.distinct()).filter(User.role.isnot(None)).all()]
    existing_modules = [p.module for p in permissions] or [
        "can_create_tasks", "can_assign_teams", "can_use_timers", 
        "can_approve_reports", "can_use_ai", "can_delete_records"
    ]
    
    configured_pairs = {(p.role, p.module) for p in permissions}
    
    # Cria automaticamente na BD as permissões para cargos novos que ainda não lá estavam
    added = False
    for role in existing_roles:
        for mod in set(existing_modules):
            if (role, mod) not in configured_pairs:
                new_perm = RolePermission(
                    role=role, module=mod, 
                    can_view=False, can_create=False, 
                    can_edit=False, can_delete=False, can_approve=False
                )
                db.add(new_perm)
                added = True
                
    if added:
        db.commit()
        permissions = db.query(RolePermission).all()
        
    return permissions

@router.put("/")
def update_permission(
    data: PermissionUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(check_permission("can_delete_records"))
):
    perm = db.query(RolePermission).filter(
        RolePermission.role == data.role, 
        RolePermission.module == data.module
    ).first()
    
    if not perm:
        perm = RolePermission(role=data.role, module=data.module)
        db.add(perm)
        
    perm.can_view = data.can_view
    perm.can_create = data.can_create
    perm.can_edit = data.can_edit
    perm.can_delete = data.can_delete
    perm.can_approve = data.can_approve
    
    db.commit()
    return {"success": True, "message": "Permissões atualizadas com sucesso!"}