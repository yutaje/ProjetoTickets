import os
import re
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
from models.notification import Notification
from models.typology import Typology
import models.feedback  # 🆕 Importa os modelos de Feedback para criação automática das tabelas
from schemas.user import UserResponse 
from routers import audit, notification, report, user, project, ticket, auth, team, client, chat, feedback  # 🆕 Importa o router de feedback
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.responses import StreamingResponse
import io

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FlowPulse API")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

origins = ["http://localhost:3000", "http://localhost:5173", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SECRET_KEY") 

def check_and_send_reminders():
    db = SessionLocal()
    try:
        hoje = date.today()
        users = db.query(User).filter(User.role != 'Admin').all()
        for u in users:
            report = db.query(DailyReport).filter(DailyReport.user_id == u.id, DailyReport.date == hoje).first()
            if not report or report.status in ["Rascunho", "Pendente"]:
                msg = "⚠️ Fim do dia! Não te esqueças de preencher e submeter o teu Relatório Diário."
                exists = db.query(Notification).filter(Notification.user_id == u.id, Notification.message == msg).first()
                if not exists:
                    db.add(Notification(user_id=u.id, message=msg))
        db.commit()
    except Exception as e:
        print("Erro ao processar lembretes de relatórios:", e)
    finally:
        db.close()

# 🆕 Rotina de verificação automática para lembretes de Feedback (30 min antes)
def check_feedback_deadlines_job():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        reminder_start = now + timedelta(minutes=25)
        reminder_end = now + timedelta(minutes=35)

        impending_requests = db.query(models.feedback.FeedbackRequest).filter(
            models.feedback.FeedbackRequest.deadline >= reminder_start,
            models.feedback.FeedbackRequest.deadline <= reminder_end
        ).all()

        for req in impending_requests:
            all_users = db.query(User).all()
            for u in all_users:
                has_resp = db.query(models.feedback.FeedbackResponse).filter(
                    models.feedback.FeedbackResponse.request_id == req.id,
                    models.feedback.FeedbackResponse.user_id == u.id
                ).first()

                if not has_resp:
                    msg = f"⏳ LEMBRETE: Faltam 30 minutos para terminar o prazo do feedback '{req.title}'!"
                    exists = db.query(Notification).filter(
                        Notification.user_id == u.id,
                        Notification.message == msg
                    ).first()

                    if not exists:
                        db.add(Notification(user_id=u.id, message=msg))
        db.commit()
    except Exception as e:
        print("Erro ao processar lembretes de feedback:", e)
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(check_and_send_reminders, 'cron', hour=17, minute=30)
scheduler.add_job(check_feedback_deadlines_job, 'interval', minutes=5)  # 🆕 Corre a cada 5 min à procura de feedbacks a expirar
scheduler.start()

@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.method in ["POST", "PUT", "DELETE"]:
        
        path = request.url.path
        
        if path.startswith("/tickets/"):
            return response

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
                            user_id = int(sub)
                        else:
                            user = db.query(User).filter(User.email == str(sub)).first()
                            if user:
                                user_id = user.id
                except: pass
            
            ticket_id = None
            match = re.search(r'/tickets/(\d+)', path)
            if match:
                ticket_id = int(match.group(1))

            new_log = AuditLog(
                user_id=user_id,
                action=request.method,
                details=f"Rota: {path} | Status: {response.status_code}",
                ticket_id=ticket_id 
            )
            db.add(new_log)
            db.commit()
        except Exception as e:
            print(f"Erro no log: {e}")
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
app.include_router(feedback.router)  # 🆕 Registo do router de Feedback

@app.get("/")
def home():
    return {"mensagem": "O backend do FlowPulse está oficialmente online, bro!"}

@app.get("/users/")
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).all()

@app.get("/admin/users-reports")
def get_admin_users_reports(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if getattr(current_user, "role", "Member") != "Admin":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    users = db.query(User).all()
    result = []
    for u in users:
        reports = db.query(DailyReport).filter(DailyReport.user_id == u.id, DailyReport.status != "Rascunho").order_by(DailyReport.date.desc()).all()
        reports_data = []
        for r in reports:
            logs = db.query(TimeLog).filter(TimeLog.user_id == u.id, TimeLog.date == r.date).all()
            ticket_ids = [l.ticket_id for l in logs]
            tickets = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all() if ticket_ids else []
            reports_data.append({
                "id": r.id, "date": str(r.date), "status": r.status,
                "summary": r.summary, "detailed_report": r.detailed_report,
                "kilometers": r.kilometers, "overtime_hours": r.overtime_hours,
                "tickets": [{"id": t.id, "title": t.title} for t in tickets]
            })
        result.append({"user_id": u.id, "name": u.name or u.email, "reports": reports_data})
    return result