from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.audit_log import AuditLog
from models.user import User
from core.security import get_current_user

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"]
)

@router.get("/")
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Proteção: Apenas Admins podem aceder
    role = getattr(current_user, "role", "Member")
    if role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a Administradores."
        )
    
    # Limitar a 100 registos para não estourar a memória do servidor
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    
    # Formatar os dados para o Frontend ler sem problemas
    lista_logs = []
    for log in logs:
        lista_logs.append({
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None
        })
        
    return lista_logs