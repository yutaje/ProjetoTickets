import os
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
from database import Base, engine, get_db, SessionLocal
from core.security import get_current_user
from models.user import User
from models.project import Project
from models.ticket import Ticket
from models.comment import Comment
from models.worklog import WorkLog
from models.daily_report import DailyReport
from models.time_log import TimeLog
from models.audit_log import AuditLog
from schemas.user import UserResponse 
from routers import audit, notification, report, user, project, ticket, auth, team, client
from datetime import datetime, date
from apscheduler.schedulers.background import BackgroundScheduler
from models.daily_report import DailyReport
from models.notification import Notification
from routers import chat



Base.metadata.create_all(bind=engine)

app = FastAPI(title="FlowPulse API")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


origins = [
    "http://localhost:3000", 
    "http://localhost:5173", 
    "*" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)


SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SECRET_KEY") 
ALGORITHM = "HS256"


def check_and_send_reminders():
    db = SessionLocal()
    try:
        hoje = date.today()
        users = db.query(User).filter(User.role != 'Admin').all()
        
        for u in users:
            report = db.query(DailyReport).filter(
                DailyReport.user_id == u.id, 
                DailyReport.date == hoje
            ).first()
            
            if not report or report.status in ["Rascunho", "Pendente"]:
                msg = "⚠️ Fim do dia! Não te esqueças de preencher e submeter o teu Relatório Diário."
                
                exists = db.query(Notification).filter(
                    Notification.user_id == u.id, 
                    Notification.message == msg
                ).first()
                
                if not exists:
                    db.add(Notification(user_id=u.id, message=msg))
        
        db.commit()
        print("Lembretes de relatório diário processados com sucesso!")
    except Exception as e:
        print("Erro ao processar lembretes:", e)
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(check_and_send_reminders, 'cron', hour=17, minute=30)
scheduler.start()



@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    response = await call_next(request)
    
    if request.method in ["POST", "PUT", "DELETE"]:
        
        user_id = None
        auth_header = request.headers.get("Authorization")
        
        db = SessionLocal()
        try:
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = jwt.decode(token, options={"verify_signature": False})
                    sub = payload.get("sub")
                    
                    if sub:
                        if str(sub).isdigit():
                            # Se o token guardou um número, é o ID!
                            user_id = int(sub)
                        else:
                            user = db.query(User).filter(User.email == str(sub)).first()
                            if user:
                                user_id = user.id
                except Exception as e:
                    print(f"Aviso - O Porteiro não conseguiu ler o token: {e}")
            
            new_log = AuditLog(
                user_id=user_id,
                action=request.method,
                details=f"Rota: {request.url.path} | Status: {response.status_code}"
            )
            db.add(new_log)
            db.commit()
        except Exception as e:
            print(f"Erro ao gravar o log do sistema: {e}")
        finally:
            db.close()
            
    return response


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(project.router)
app.include_router(ticket.router)
app.include_router(team.router)
app.include_router(notification.router)  
app.include_router(report.router)
app.include_router(audit.router)
app.include_router(client.router)  
app.include_router(chat.router)




@app.get("/")
def home():
    return {"mensagem": "O backend do FlowPulse está oficialmente online, bro!"}

@app.get("/users/")
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).all()


@app.get("/admin/users-reports")
def get_admin_users_reports(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    role = getattr(current_user, "role", "Member")
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    
    users = db.query(User).all()
    result = []
    for u in users:
        # A MUDANÇA ESTÁ AQUI: Adicionado o filtro DailyReport.status != "Rascunho"
        reports = db.query(DailyReport).filter(
            DailyReport.user_id == u.id,
            DailyReport.status != "Rascunho" 
        ).order_by(DailyReport.date.desc()).all()
        
        reports_data = []
        
        for r in reports:
            tickets_info = []
            try:
                logs = db.query(TimeLog).filter(
                    TimeLog.user_id == u.id,
                    TimeLog.date == r.date
                ).all()
                
                ticket_ids = [l.ticket_id for l in logs]
                tickets = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all() if ticket_ids else []
                
                hours_map = {}
                for l in logs:
                    hours_map[l.ticket_id] = hours_map.get(l.ticket_id, 0) + l.hours_spent

                tickets_info = [{
                    "id": t.id,
                    "title": t.title,
                    "status": getattr(t, "status", "To Do"),
                    "hours_today": round(hours_map.get(t.id, 0), 2),
                    "start_date": str(r.date),
                    "due_date": str(r.date)
                } for t in tickets]
            except Exception as e:
                print(f"Erro a processar logs do relatório {r.id}: {e}")

            reports_data.append({
                "id": r.id,
                "date": r.date.isoformat() if hasattr(r.date, 'isoformat') else str(r.date),
                "status": r.status,
                "summary": r.summary,
                "detailed_report": r.detailed_report,
                "kilometers": r.kilometers,
                "overtime_hours": r.overtime_hours,
                "tickets": tickets_info,
                "rejection_reason": getattr(r, "rejection_reason", None)
            })
        
        result.append({
            "user_id": u.id,
            "name": u.name or u.email,
            "email": u.email,
            "reports": reports_data
        })
    return result