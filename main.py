from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.security import get_current_user
from core.security import get_current_user
from database import Base, engine, get_db
from models.user import User
from models.project import Project
from models.ticket import Ticket
from routers import audit, notification, report, user, project, ticket, auth, team
from models.comment import Comment
from models.worklog import WorkLog
from sqlalchemy.orm import Session


Base.metadata.create_all(bind=engine)


app = FastAPI(title="FlowPulse API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(project.router)
app.include_router(ticket.router)
app.include_router(team.router)
app.include_router(notification.router)  
app.include_router(report.router)
app.include_router(audit.router)


@app.get("/")
def home():
    return {"mensagem": "O backend do FlowPulse está oficialmente online, bro!"}


from models.user import User
from schemas.user import UserResponse # ou o teu schema correspondente
from typing import List

@app.get("/users/")
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).all()