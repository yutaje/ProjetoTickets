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
    role = getattr(current_user, "role", "Member")
    if role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a Administradores."
        )
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()