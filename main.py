import os
import jwt
from fastapi import Depends, FastAPI, Request
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

@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    # 1. Deixa o pedido passar e ser processado (aqui o FastAPI faz a segurança real)
    response = await call_next(request)
    
    # 2. Só interceptamos as ações de modificação de dados
    if request.method in ["POST", "PUT", "DELETE"]:
        
        user_id = None
        auth_header = request.headers.get("Authorization")
        
        db = SessionLocal()
        try:
            # 3. Vamos cuscar o Token
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    # O CHEAT CODE: Lemos o token diretamente sem precisar da SECRET_KEY
                    # (Não há perigo porque o FastAPI já validou a entrada antes)
                    payload = jwt.decode(token, options={"verify_signature": False})
                    sub = payload.get("sub")
                    
                    if sub:
                        if str(sub).isdigit():
                            # Se o token guardou um número, é o ID!
                            user_id = int(sub)
                        else:
                            # Se o token guardou o Email, vamos à BD descobrir quem é!
                            user = db.query(User).filter(User.email == str(sub)).first()
                            if user:
                                user_id = user.id
                except Exception as e:
                    print(f"Aviso - O Porteiro não conseguiu ler o token: {e}")
            
            # 4. Gravar na tabela AuditLog
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

@app.get("/")
def home():
    return {"mensagem": "O backend do FlowPulse está oficialmente online, bro!"}

@app.get("/users/")
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).all()