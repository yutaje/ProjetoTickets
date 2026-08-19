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
    role = getattr(current_user, "role", "Member").lower()
    query = db.query(AuditLog)
    
    # Restrições de visualização por nível de perfil:
    # - Programador / Member: Consulta apenas os seus próprios logs
    # - Admin / Manager / Coordenador: Regras correspondentes ou acesso global
    if role in ["member", "programador", "técnico"]:
        query = query.filter(AuditLog.user_id == current_user.id)
    elif role in ["coordenador de equipa", "manager"]:
        # Poderá filtrar por equipa se necessário, por agora vê as operações geridas
        pass
    elif role == "admin":
        pass # Admin vê tudo
    else:
        if role != "admin":
            query = query.filter(AuditLog.user_id == current_user.id)

    logs = query.order_by(AuditLog.created_at.desc()).limit(100).all()
    
    lista_logs = []
    for log in logs:
        lista_logs.append({
            "id": log.id,
            "user_id": log.user_id,
            "project_id": getattr(log, "project_id", None),
            "ticket_id": getattr(log, "ticket_id", None),
            "action": log.action,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None
        })
        
    return lista_logs