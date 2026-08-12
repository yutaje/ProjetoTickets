from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, UploadFile, File, Form
import os
from sqlalchemy.orm import Session
from database import get_db
from models.ticket import Ticket
from models.user import User
from models.worklog import WorkLog
from models.project import Project
from models.team import Team
from schemas.ticket import TicketCreate, TicketUpdate, TicketResponse
from core.security import get_current_user
from typing import List, Optional
from datetime import date, timedelta
import shutil
from google import genai 
import traceback
from models.notification import Notification
from models.time_log import TimeLog
from models.daily_report import DailyReport
from models.comment import Comment
from datetime import date, timedelta, datetime

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)

def filter_tickets_by_permissions(query, current_user: User, db: Session):
    role = getattr(current_user, "role", "Member")
    
    if role == "Admin":
        return query
        
    user_teams = db.query(Team.id).filter(
        (Team.owner_id == current_user.id) | 
        (Team.members.any(id=current_user.id))
    ).statement.correlate(None)
    
    user_projects = db.query(Project.id).filter(
        (Project.team_id.in_(user_teams)) | 
        (Project.team_id.is_(None))
    ).statement.correlate(None)
    
    return query.filter(
        (Ticket.assigned_to_id == current_user.id) | 
        (Ticket.project_id.in_(user_projects))
    )


@router.get("/me/stats")
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    query = filter_tickets_by_permissions(query, current_user, db)
    
    all_tickets = query.all()
    today = date.today()
    
    to_do = sum(1 for t in all_tickets if t.status and t.status.lower() in ['to do', 'a fazer'])
    in_progress = sum(1 for t in all_tickets if t.status and t.status.lower() in ['in progress', 'em progresso'])
    in_review = sum(1 for t in all_tickets if t.status and t.status.lower() in ['in review', 'em revisão', 'em revisao'])
    done = sum(1 for t in all_tickets if t.status and t.status.lower() in ['done', 'concluído', 'concluido'])
    
    overdue = sum(1 for t in all_tickets if t.due_date and t.due_date < today and t.status and t.status.lower() not in ['done', 'concluído', 'concluido'])
    due_today = sum(1 for t in all_tickets if t.due_date and t.due_date == today and t.status and t.status.lower() not in ['done', 'concluído', 'concluido'])

    today_logs = db.query(TimeLog).filter(
        TimeLog.user_id == current_user.id,
        TimeLog.date == today
    ).all()
    hours_today = sum(log.hours_spent for log in today_logs)

    role = getattr(current_user, "role", "Member")

    return {
        "user_id": current_user.id,
        "role": role,
        "total_tickets": len(all_tickets),
        "to_do": to_do,
        "in_progress": in_progress,
        "in_review": in_review,
        "done": done,
        "overdue": overdue,
        "due_today": due_today,
        "hours_today": round(hours_today, 2)
    }

@router.get("/active", response_model=List[TicketResponse])
def get_active_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.is_running == True)
    query = filter_tickets_by_permissions(query, current_user, db)
    return query.all()

@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    s_date = ticket.start_date if ticket.start_date else None
    d_date = ticket.due_date if ticket.due_date else None

    db_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status=ticket.status,
        project_id=ticket.project_id if ticket.project_id else None,
        client_id=ticket.client_id,
        assigned_to_id=ticket.assigned_to_id,
        estimated_hours=ticket.estimated_hours,
        due_date=d_date,
        start_date=s_date,
        task_type=ticket.task_type if hasattr(ticket, 'task_type') else "Geral"
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    
    if db_ticket.assigned_to_id and db_ticket.assigned_to_id != current_user.id:
        notif = Notification(
            user_id=db_ticket.assigned_to_id,
            message=f"Foste atribuído a uma nova tarefa: {db_ticket.title}"
        )
        db.add(notif)
        db.commit()
        
    return db_ticket

@router.get("/", response_model=List[TicketResponse])
def get_tickets(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_and_create_deadline_notifications(current_user, db)
    query = db.query(Ticket)
    query = filter_tickets_by_permissions(query, current_user, db)
    
    if search:
        query = query.filter(Ticket.title.ilike(f"%{search}%"))
    if status:
        query = query.filter(Ticket.status == status)
        
    return query.all()

@router.get("/my-day/today")
def get_or_create_daily_report(
    target_date: Optional[str] = Query(None), # <-- Novo parâmetro
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Se vier data no pedido, usa essa, senão usa a data de hoje
    if target_date:
        today = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        today = date.today()
    
    report = db.query(DailyReport).filter(
        DailyReport.user_id == current_user.id,
        DailyReport.date == today
    ).first()
    
    if not report:
        report = DailyReport(
            user_id=current_user.id, 
            date=today, 
            status="Rascunho"
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        
    logs = db.query(TimeLog).filter(
        TimeLog.user_id == current_user.id,
        TimeLog.date == today
    ).all()
    
    hours_per_ticket = {}
    for log in logs:
        hours_per_ticket[log.ticket_id] = hours_per_ticket.get(log.ticket_id, 0) + log.hours_spent
        
    ticket_ids = list(hours_per_ticket.keys())
    tickets_worked_today = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all() if ticket_ids else []
    
    tickets_data = []
    for t in tickets_worked_today:
        tickets_data.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "description": t.description,
            "hours_today": round(hours_per_ticket[t.id], 2)
        })
        
    return {
        "report": {
            "id": report.id,
            "status": report.status,
            "summary": report.summary,
            "detailed_report": report.detailed_report,
            "kilometers": report.kilometers,
            "overtime_hours": report.overtime_hours,
            "rejection_reason": getattr(report, "rejection_reason", None)
        },
        "tickets_worked": tickets_data
    }

@router.get("/my-day/week")
def get_week_status(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    start_date = today - timedelta(days=6)
    
    reports = db.query(DailyReport).filter(
        DailyReport.user_id == current_user.id,
        DailyReport.date >= start_date,
        DailyReport.date <= today
    ).all()
    
    report_dict = {r.date: r for r in reports}
    week_data = []
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    
    for i in range(7):
        current_d = start_date + timedelta(days=i)
        rep = report_dict.get(current_d)
        nome_dia = dias_semana[current_d.weekday()]
        
        if rep:
            status = rep.status
        else:
            status = "Em falta" if current_d < today else "Não iniciado"
            
        week_data.append({
            "date": current_d.isoformat(),
            "day_name": nome_dia,
            "day_num": current_d.day,
            "status": status
        })
        
    return week_data

@router.put("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    ticket_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    
    session_hours = ticket_data.pop("session_hours", None)
    
    for key, value in ticket_data.items():
        setattr(ticket, key, value)
        
    if session_hours and session_hours > 0:
        new_log = TimeLog(
            ticket_id=ticket.id,
            user_id=current_user.id,
            date=date.today(),
            hours_spent=session_hours
        )
        db.add(new_log)
        
    db.commit()
    db.refresh(ticket)
    return ticket

@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    db_ticket = query.first()
    
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou não tens permissão para apagá-la.")
    
    db.delete(db_ticket)
    db.commit()
    return None

@router.post("/{ticket_id}/generate-ai-report")
def generate_ai_report(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    ticket = query.first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    
    comments_text = "Nenhuma observação registada."
    try:
        comments = db.query(Comment).filter(Comment.ticket_id == ticket.id).all()
        if comments:
            comments_text = "\n".join([f"- {c.text}" for c in comments])
    except Exception:
        pass
    
    prompt = f"""
    És um assistente inteligente para técnicos de campo da empresa RFS. 
    Com base nos dados desta tarefa e nas observações de campo registadas, redige um resumo profissional e um relatório detalhado de intervenção em língua portuguesa.
    
    Título da Tarefa: {ticket.title}
    Descrição Inicial: {ticket.description or 'N/A'}
    Prioridade: {ticket.priority}
    
    Observações / Notas recolhidas durante a execução:
    {comments_text}
    """

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        return {"generated_report": response.text}
    except Exception as e:
        fallback_report = f"""RELATÓRIO DE INTERVENÇÃO TÉCNICA (RFS)

- Tarefa Executada: {ticket.title}
- Descrição Inicial: {ticket.description or 'Intervenção técnica regular efetuada conforme planeamento.'}
- Estado de Conclusão: Concluído com sucesso.
- Observações de Campo: {comments_text}"""
        
        return {"generated_report": fallback_report}

@router.get("/ai-focus-recommendation")
def get_ai_focus_recommendation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket)
    query = filter_tickets_by_permissions(query, current_user, db)
    active_tickets = query.filter(Ticket.status != "Done").all()
    
    if not active_tickets:
        return {"recommendation": "De momento não tens tarefas ativas para analisar. Excelente trabalho!"}
        
    projects = db.query(Project).all()
    proj_map = {p.id: p.name for p in projects}

    today = date.today()
    today_str = today.isoformat()

    priority_weights = {'Crítica': 4, 'Alta': 3, 'Média': 2, 'Baixa': 1}

    scored_tasks = []
    for t in active_tickets:
        proj_name = proj_map.get(t.project_id, "Projeto Geral")
        due_info = str(t.due_date).split('T')[0] if t.due_date else None
        
        # CÁLCULO MATEMÁTICO DE URGÊNCIA (Para a IA ponderar sem falhar)
        urgency_score = priority_weights.get(t.priority, 1) * 2  # Peso base da prioridade
        
        temporal_desc = "Sem prazo definido"
        if due_info:
            due_date_obj = date.fromisoformat(due_info)
            delta_days = (due_date_obj - today).days
            
            if delta_days < 0:
                # Atrasada: ganha pontos pelo atraso, mas penalizada se for prioridade Baixa
                urgency_score += abs(delta_days)
                temporal_desc = f"Atrasada por {abs(delta_days)} dia(s)"
            elif delta_days == 0:
                # Vence hoje: salto massivo de urgência
                urgency_score += 15
                temporal_desc = "Vence EXATAMENTE HOJE"
            else:
                temporal_desc = "No prazo futuro"

        scored_tasks.append({
            "id": t.id,
            "title": t.title,
            "project": proj_name,
            "priority": t.priority,
            "due_date": due_info or "Sem prazo",
            "temporal": temporal_desc,
            "score": urgency_score
        })

    # Ordena por pontuação matemática para a IA ver quem lidera
    scored_tasks.sort(key=lambda x: x["score"], reverse=True)

    tasks_text = "\n".join([
        f"- [ID: #{st['id']}] Título: '{st['title']}' | Projeto: '{st['project']}' | Prioridade: {st['priority']} | Prazo: {st['due_date']} ({st['temporal']}) | Score Calculado: {st['score']}"
        for st in scored_tasks
    ])
    
    prompt = f"""
    A data atual é {today_str}. És o gestor de operações sénior da RFS.
    Abaixo tens a lista de tarefas ativas ordenada pelo sistema com base num algoritmo de cruzamento entre prioridade e prazos (Score de Urgência).

    Analisa criticamente os dados, valida qual é a tarefa mais crítica para o técnico executar agora (por exemplo, ponderando se uma tarefa que acaba hoje com prioridade Crítica supera uma tarefa atrasada de prioridade Baixa), e redige uma recomendação de foco altamente profissional, direta e justificada.

    Tarefas ativas:
    {tasks_text}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        return {"recommendation": response.text} 
    except Exception as e:
        print(f"AVISO: IA de foco falhou. Erro: {str(e)}")
        top_task = scored_tasks[0]
        return {"recommendation": f"Análise Operacional Automática: Deves focar-te na tarefa #{top_task['id']} ('{top_task['title']}') devido ao cruzamento da sua prioridade ({top_task['priority']}) com o prazo ({top_task['due_date']})."}

@router.put("/{ticket_id}/complete", response_model=TicketResponse)
def complete_ticket(
    ticket_id: int,
    final_description: Optional[str] = Form(None),
    tracked_hours: Optional[float] = Form(0.0),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    db_ticket = query.first()
    
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    
    # 1. GRAVA A DESCRIÇÃO FINAL DIRETAMENTE
    db_ticket.final_description = final_description or ""
    db_ticket.status = "Done"
    db_ticket.is_running = False
    
    if tracked_hours is not None and tracked_hours > 0:
        new_log = TimeLog(
            ticket_id=db_ticket.id,
            user_id=current_user.id,
            date=date.today(),
            hours_spent=float(tracked_hours)
        )
        db.add(new_log)

    # 2. GRAVA O FICHEIRO NA COLUNA CORRETA (attachment_path)
    if file and file.filename:
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        db_ticket.attachment_path = f"uploads/{file.filename}"

    db.commit()
    db.refresh(db_ticket)
    return db_ticket

def check_and_create_deadline_notifications(user: User, db: Session):
    try:
        today = date.today()
        today_str = today.isoformat()
        query = db.query(Ticket)
        query = filter_tickets_by_permissions(query, user, db)
        tickets = query.filter(Ticket.status != "Done").all()
        
        for t in tickets:
            if not t.due_date:
                continue
            if isinstance(t.due_date, str):
                due_date_str = t.due_date.split('T')[0]
            elif hasattr(t.due_date, 'isoformat'):
                due_date_str = t.due_date.isoformat().split('T')[0]
            else:
                continue
            
            if due_date_str == today_str:
                msg = f"O prazo da tarefa '#{t.id} - {t.title}' acaba hoje!"
                exists = db.query(Notification).filter(Notification.user_id == user.id, Notification.message == msg).first()
                if not exists:
                    db.add(Notification(user_id=user.id, message=msg))
            elif due_date_str < today_str:
                msg = f"ATENÇÃO: A tarefa '#{t.id} - {t.title}' está atrasada!"
                exists = db.query(Notification).filter(Notification.user_id == user.id, Notification.message == msg).first()
                if not exists:
                    db.add(Notification(user_id=user.id, message=msg))
                    
        db.commit()
    except Exception as e:
        db.rollback()

@router.post("/my-day/generate-ai")
def generate_daily_ai_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = date.today()
    logs = db.query(TimeLog).filter(TimeLog.user_id == current_user.id, TimeLog.date == today).all()
    
    if not logs:
        return {
            "summary": "Sem tarefas registadas hoje.", 
            "detailed_report": "Não foram contabilizadas horas em nenhuma tarefa no dia de hoje."
        }
        
    hours_per_ticket = {}
    for log in logs:
        hours_per_ticket[log.ticket_id] = hours_per_ticket.get(log.ticket_id, 0) + log.hours_spent
        
    ticket_ids = list(hours_per_ticket.keys())
    tickets = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
    
    tasks_info = []
    for t in tickets:
        tasks_info.append(f"- Tarefa #{t.id}: {t.title} (Estado: {t.status}, Descrição: {t.description or 'N/A'}) - Tempo hoje: {hours_per_ticket[t.id]}h")
    
    tasks_text = "\n".join(tasks_info)
    
    prompt = f"""
    És um assistente técnico inteligente da RFS. Com base nas seguintes tarefas executadas pelo técnico no dia de hoje, gera:
    1. Um "summary" (um resumo curto e profissional de uma linha do dia).
    2. Um "detailed_report" (um relatório detalhado estruturado com as intervenções efetuadas).
    
    Tarefas de hoje:
    {tasks_text}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        text_result = response.text
        
        return {
            "summary": text_result[:150] + "...", 
            "detailed_report": text_result
        }
    except Exception as e:
        print(f"AVISO: IA falhou, a usar relatório padrão. Erro: {str(e)}")
        
        # Fallback automático estruturado para nunca deixar o técnico pendurado
        fallback_summary = f"Executadas {len(tickets)} intervenções técnicas planeadas para o dia de hoje."
        fallback_details = "RELATÓRIO DE ATIVIDADE DIÁRIA (RFS)\n\nIntervenções efetuadas:\n" + "\n".join(tasks_info)
        
        return {
            "summary": fallback_summary,
            "detailed_report": fallback_details
        }

@router.put("/my-day/today")
def update_daily_report(
    target_date: Optional[str] = Query(None),
    summary: Optional[str] = Form(None),
    detailed_report: Optional[str] = Form(None),
    kilometers: Optional[float] = Form(0.0),
    overtime_hours: Optional[float] = Form(0.0),
    pending_work: Optional[str] = Form(None),
    incidents: Optional[str] = Form(None),
    materials: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None), # <- O nosso ficheiro!
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if target_date:
        today = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        today = date.today()
        
    report = db.query(DailyReport).filter(DailyReport.user_id == current_user.id, DailyReport.date == today).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
        
    # Atualizar campos de texto
    report.summary = summary
    report.detailed_report = detailed_report
    report.kilometers = kilometers
    report.overtime_hours = overtime_hours
    # (Se tiveres estes campos no model, atualiza-os também)
    if hasattr(report, 'pending_work'): report.pending_work = pending_work
    if hasattr(report, 'incidents'): report.incidents = incidents
    if hasattr(report, 'materials'): report.materials = materials

    # Guardar a imagem se ela for enviada
    if file and file.filename:
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        report.image_path = f"uploads/{file.filename}"

    report.status = "Submetido" 
    report.rejection_reason = None
    
    db.commit()
    db.refresh(report)
    return {"message": "Relatório submetido com sucesso!"}

@router.put("/my-day/reopen")
def reopen_daily_report(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    report = db.query(DailyReport).filter(DailyReport.user_id == current_user.id, DailyReport.date == today).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
        
    report.status = "Rascunho"
    db.commit()
    db.refresh(report)
    return {"message": "Relatório reaberto com sucesso!"}


@router.put("/admin/reports/{report_id}/status")
def update_report_status_admin(
    report_id: int,
    status_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member")
    if role != "Admin":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
        
    report = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
        
    new_status = status_data.get("status")
    reason = status_data.get("rejection_reason") 

    if new_status == "Recusado":
        report.status = "Rascunho"
        report.rejection_reason = reason 
        
        
        data_formatada = report.date.strftime("%d/%m/%Y") if hasattr(report.date, 'strftime') else str(report.date)
        
        notif_msg = f"O teu relatório do dia {data_formatada} foi recusado. Motivo: {reason}"
        nova_notificacao = Notification(user_id=report.user_id, message=notif_msg)
        db.add(nova_notificacao)
        # ------------------------------
        
    else:
        report.status = new_status
        if new_status == "Validado":
            report.rejection_reason = None 
            
    db.commit()
    db.refresh(report)
    return {"message": "Estado atualizado com sucesso!"}


@router.get("/{ticket_id}/comments")
def get_ticket_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    ticket = query.first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
        
    comments = db.query(Comment).filter(Comment.ticket_id == ticket_id).all()
    
    enriched_comments = []
    for c in comments:
        author = db.query(User).filter(User.id == c.author_id).first()
        author_name = author.name if author and author.name else (author.email if author else "Colaborador")
        
        enriched_comments.append({
            "id": c.id,
            "text": c.text,
            "author_id": c.author_id,
            "author_name": author_name,
            "created_at": getattr(c, "created_at", None)
        })
        
    return enriched_comments

@router.post("/{ticket_id}/comments")
def create_ticket_comment(
    ticket_id: int,
    comment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Ticket).filter(Ticket.id == ticket_id)
    query = filter_tickets_by_permissions(query, current_user, db)
    ticket = query.first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
        
    new_comment = Comment(
        text=comment_data.get("text"),
        ticket_id=ticket_id,
        author_id=current_user.id
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


