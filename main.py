from fastapi import FastAPI
from database import Base, engine
from models.user import User
from models.project import Project
from models.ticket import Ticket
from routers import user, project, ticket, auth




#cria as tabelas na bd
Base.metadata.create_all(bind=engine)


app = FastAPI(title="FlowPulse API")


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(project.router)
app.include_router(ticket.router)
app.include_router(auth.router)

@app.get("/")
def home():
    return {"mensagem": "O backend do FlowPulse está oficialmente online, bro!"}