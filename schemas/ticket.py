from pydantic import BaseModel
from typing import Optional
from datetime import date

class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "Média"
    status: Optional[str] = "To Do" # No futuro, podemos mudar para "Pendente" no React
    project_id: Optional[int] = None
    client_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    estimated_hours: Optional[float] = 0.0
    due_date: Optional[date] = None
    start_date: Optional[date] = None
    task_type: Optional[str] = "Geral"
    
    # --- NOVA LINHA: Quem está a criar a tarefa ---
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
    
    # --- NOVA LINHA: Caso um Admin precise de transferir o dono da tarefa ---
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
    
    # --- NOVA LINHA: Para o React bloquear botões se o user não for o criador ---
    creator_id: Optional[int] = None

    class Config:
        from_attributes = True