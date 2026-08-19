from sqlalchemy import Column, Integer, String
from database import Base

class TaskType(Base):
    __tablename__ = "task_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)  #