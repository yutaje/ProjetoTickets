from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

class SubTaskResponse(BaseModel):
    id: int
    ticket_id: int
    title: str
    is_completed: bool
    assigned_to_id: Optional[int] = None
    
    # 🆕 Campos para o fluxo de aprovação da subtarefa
    status: Optional[str] = "Pendente"
    is_approved: Optional[bool] = False
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True

class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "Média"
    status: Optional[str] = "To Do"
    project_id: Optional[int] = None
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    # Campo obrigatório e superior a zero
    estimated_hours: float = Field(..., gt=0, description="As horas estimadas são obrigatórias e devem ser superiores a 0.")
    due_date: Optional[date] = None
    start_date: Optional[date] = None
    task_type: Optional[str] = "Geral"
    
    creator_id: Optional[int] = None
    blocked_by_id: Optional[int] = None

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[int] = None
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    estimated_hours: Optional[float] = None
    tracked_hours: Optional[float] = None
    due_date: Optional[date] = None
    start_date: Optional[date] = None
    is_running: Optional[bool] = None
    session_hours: Optional[float] = None
    task_type: Optional[str] = None
    blocked_by_id: Optional[int] = None
    completed_at: Optional[datetime] = None  # 🆕 Adicionado para gerir a data de conclusão
    
    creator_id: Optional[int] = None

class TicketResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    project_id: Optional[int] = None
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    estimated_hours: float
    tracked_hours: float
    due_date: Optional[date] = None
    start_date: Optional[date] = None
    is_running: bool
    session_hours: Optional[float] = 0.0  
    final_description: Optional[str] = None
    attachment_path: Optional[str] = None
    attachment_url: Optional[str] = None
    task_type: Optional[str] = None
    completed_at: Optional[datetime] = None  # 🆕 Adicionado para devolver a data de conclusão ao frontend
    
    creator_id: Optional[int] = None

    # LISTA DE SUBTAREFAS
    sub_tasks: List[SubTaskResponse] = []

    class Config:
        from_attributes = True