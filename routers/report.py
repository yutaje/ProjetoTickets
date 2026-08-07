from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
from database import get_db
from models.worklog import WorkLog
from models.user import User
from core.security import get_current_user

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)

@router.get("/export-csv")
def export_worklogs_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member")
    if role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Administradores podem exportar relatórios globais."
        )

    # Consulta que junta os utilizadores e soma todas as horas de cada um
    results = db.query(
        User.id,
        User.name,
        User.email,
        func.coalesce(func.sum(WorkLog.hours), 0).label("total_hours")
    ).outerjoin(WorkLog, User.id == WorkLog.user_id)\
     .group_by(User.id, User.name, User.email)\
     .all()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeçalho limpo com o resumo por utilizador
    writer.writerow(["ID Utilizador", "Nome", "Email", "Total de Horas Trabalhadas"])

    for row in results:
        writer.writerow([
            row.id,
            row.name or "Sem nome",
            row.email,
            round(row.total_hours, 2)
        ])

    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=relatorio_total_horas_utilizador.csv"}
    )