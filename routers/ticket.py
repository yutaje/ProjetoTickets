from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, UploadFile, File
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
from models.daily_report import DailyReport # <-- ADICIONADO AQUI PARA NÃO DAR ERRO


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
        start_date=s_date
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    
    if db_ticket.assigned_to_id and db_ticket.assigned_to_id != current_user.id:
        from models.notification import Notification
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
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    
    # 1. Procurar o relatório de hoje; se não existir, cria-se automaticamente como Rascunho
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
        
    # 2. Ir buscar os TimeLogs de hoje do utilizador para saber as tarefas onde trabalhou
    logs = db.query(TimeLog).filter(
        TimeLog.user_id == current_user.id,
        TimeLog.date == today
    ).all()
    
    # Agrupar e somar as horas por cada ticket de hoje
    hours_per_ticket = {}
    for log in logs:
        hours_per_ticket[log.ticket_id] = hours_per_ticket.get(log.ticket_id, 0) + log.hours_spent
        
    # 3. Ir buscar os dados completos dos tickets trabalhados
    ticket_ids = list(hours_per_ticket.keys())
    
    # Se existirem tickets trabalhados hoje, vamos buscá-los; senão, a lista fica vazia
    tickets_worked_today = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all() if ticket_ids else []
    
    # 4. Preparar os dados mastigados para o Frontend e para a IA
    tickets_data = []
    for t in tickets_worked_today:
        tickets_data.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "description": t.description,
            "hours_today": round(hours_per_ticket[t.id], 2) # Tempo gasto APENAS HOJE
        })
        
    return {
        "report": {
            "id": report.id,
            "status": report.status,
            "summary": report.summary,
            "detailed_report": report.detailed_report,
            "kilometers": report.kilometers,
            "overtime_hours": report.overtime_hours
        },
        "tickets_worked": tickets_data
    }


@router.get("/my-day/week")
def get_week_status(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    start_date = today - timedelta(days=6) # Pega nos últimos 7 dias (incluindo hoje)
    
    # Procurar relatórios deste utilizador nos últimos 7 dias
    reports = db.query(DailyReport).filter(
        DailyReport.user_id == current_user.id,
        DailyReport.date >= start_date,
        DailyReport.date <= today
    ).all()
    
    # Criar um dicionário rápido para procurar por data
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
            # Se não há relatório e é um dia no passado, está em falta!
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
    ticket_data: dict, # (Ou o Schema Pydantic que estiveres a usar, ex: TicketUpdate)
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    
    # Extrair e remover 'session_hours' do dicionário principal, pois não pertence à tabela Ticket
    session_hours = ticket_data.pop("session_hours", None)
    
    # 1. Atualizar os campos normais do Ticket (ex: tracked_hours, is_running, status...)
    for key, value in ticket_data.items():
        setattr(ticket, key, value)
        
    # 2. O TRUQUE: Se o frontend enviou 'session_hours', gravamos no Registo Diário!
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
    
    # Tentar ir buscar observações/comentários de forma totalmente segura
    comments_text = "Nenhuma observação registada."
    try:
        from models.comment import Comment
        comments = db.query(Comment).filter(Comment.ticket_id == ticket.id).all()
        if comments:
            comments_text = "\n".join([f"- {c.text}" for c in comments])
    except Exception:
        pass # Se houver qualquer detalhe com o modelo de comentários, ignora e segue semcrashar
    
    prompt = f"""
    És um assistente inteligente para técnicos de campo da empresa RFS. 
    Com base nos dados desta tarefa e nas observações de campo registadas, redige um resumo profissional e um relatório detalhado de intervenção em língua portuguesa.
    
    Título da Tarefa: {ticket.title}
    Descrição Inicial: {ticket.description or 'N/A'}
    Tempo Gasto: {ticket.tracked_hours} horas
    Prioridade: {ticket.priority}
    
    Observações / Notas recolhidas durante a execução:
    {comments_text}
    
    O relatório deve descrever de forma formal o trabalho realizado e o estado de conclusão[cite: 2]. Formata o texto de forma limpa para um técnico poder apenas ler, ajustar e submeter[cite: 2].
    """

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        return {"generated_report": response.text}
    except Exception as e:
        # Fallback automático inteligente caso a API falhe por limites de quota
        fallback_report = f"""RELATÓRIO DE INTERVENÇÃO TÉCNICA (RFS)

- Tarefa Executada: {ticket.title}
- Descrição Inicial: {ticket.description or 'Intervenção técnica regular efetuada conforme planeamento.'}
- Estado de Conclusão: Concluído com sucesso.
- Tempo Total Despendido: {ticket.tracked_hours or 0.0} horas.
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
        
    # Buscar também os projetos para associar o nome correto a cada tarefa
    projects = db.query(Project).all()
    proj_map = {p.id: p.name for p in projects}

    tasks_details = []
    for t in active_tickets:
        proj_name = proj_map.get(t.project_id, "Projeto Geral")
        tasks_details.append(
            f"- [ID: #{t.id}] Título: '{t.title}' | Projeto: '{proj_name}' | Prioridade: {t.priority} | Prazo (Due Date): {t.due_date or 'Sem prazo definido'} | Estado: {t.status} | Horas Estimadas: {t.estimated_hours}h"
        )
    
    tasks_text = "\n".join(tasks_details)
    
    prompt = f"""
    És o assistente técnico de operações sénior da RFS. Analisa rigorosamente a seguinte lista real de tarefas ativas da base de dados, tendo em conta o cruzamento entre o nível de prioridade (Crítica, Alta, Média, Baixa), a proximidade do prazo de entrega (due date) e o projeto a que pertencem.

    Lista de Tarefas Ativas:
    {tasks_text}

    Gera uma recomendação estratégica detalhada em língua portuguesa estruturada exatamente desta forma:
    1. **Top Prioridades Imediatas**: Identifica claramente quais as tarefas específicas que devem ser executadas primeiro e explica o porquê (baseando-te no cruzamento real de prazos apertados e alta prioridade).
    2. **Análise de Alerta (Prazos Críticos)**: Destaca se existe alguma tarefa em risco de atraso.
    3. **Plano de Ação Sugerido**: Um breve passo a passo prático para o dia de hoje.

    Não dês respostas vagas. Menciona os títulos e os IDs das tarefas concretas da lista fornecida.
    """

    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        return {"recommendation": response.text} 
    except Exception as e:
        # Fallback detalhado estruturado caso a API esgote a quota
        fallback_text = "ANÁLISE DE FOCO INTELIGENTE (FALLBACK LOCAL):\n\n"
        # Ordenar localmente por prioridade e prazo para o fallback ser útil
        sorted_fallback = sorted(active_tickets, key=lambda x: (x.priority != 'Crítica', x.priority != 'Alta', x.due_date or '9999-12-31'))
        for idx, t in enumerate(sorted_fallback[:3], 1):
            fallback_text += f"{idx}. **#{t.id} - {t.title}** (Prioridade: {t.priority} | Prazo: {t.due_date or 'N/A'})\n"
        fallback_text += "\nRecomendação: Foca-te nestas tarefas prioritárias listadas acima para mitigar riscos de incumprimento de prazos."
        
        return {"recommendation": fallback_text}


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
    
    db_ticket.final_description = final_description or ""
    db_ticket.status = "Done"
    db_ticket.is_running = False
    
    if tracked_hours is not None:
        db_ticket.tracked_hours = float(tracked_hours)

    if file and file.filename:
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        db_ticket.attachment_path = f"/uploads/{file.filename}"

    db.commit()
    db.refresh(db_ticket)
    return db_ticket


def check_and_create_deadline_notifications(user: User, db: Session):
    try:
        today = date.today()
        today_str = today.isoformat() # Formato "YYYY-MM-DD"
        
        query = db.query(Ticket)
        query = filter_tickets_by_permissions(query, user, db)
        tickets = query.filter(Ticket.status != "Done").all()
        
        for t in tickets:
            if not t.due_date:
                continue
                
            # Converter de forma segura para string "YYYY-MM-DD" independentemente do tipo na BD
            if isinstance(t.due_date, str):
                due_date_str = t.due_date.split('T')[0]
            elif hasattr(t.due_date, 'isoformat'):
                due_date_str = t.due_date.isoformat().split('T')[0]
            else:
                continue
            
            # 1. Prazo acaba hoje
            if due_date_str == today_str:
                msg = f"O prazo da tarefa '#{t.id} - {t.title}' acaba hoje!"
                exists = db.query(Notification).filter(
                    Notification.user_id == user.id,
                    Notification.message == msg
                ).first()
                
                if not exists:
                    db.add(Notification(user_id=user.id, message=msg))
                    
            # 2. Tarefa atrasada
            elif due_date_str < today_str:
                msg = f"ATENÇÃO: A tarefa '#{t.id} - {t.title}' está atrasada!"
                exists = db.query(Notification).filter(
                    Notification.user_id == user.id,
                    Notification.message == msg
                ).first()
                
                if not exists:
                    db.add(Notification(user_id=user.id, message=msg))
                    
        db.commit()
    except Exception as e:
        db.rollback()
        print("Erro detalhado nas notificações de prazo:", e)

@router.post("/my-day/generate-ai")
def generate_daily_ai_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = date.today()
    logs = db.query(TimeLog).filter(TimeLog.user_id == current_user.id, TimeLog.date == today).all()
    
    if not logs:
        return {"summary": "Sem tarefas trabalhadas hoje.", "detailed_report": "Não foram registadas horas em nenhuma tarefa durante o dia de hoje."}
        
    hours_per_ticket = {}
    for log in logs:
        hours_per_ticket[log.ticket_id] = hours_per_ticket.get(log.ticket_id, 0) + log.hours_spent
        
    ticket_ids = list(hours_per_ticket.keys())
    tickets = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
    
    # Tentar ir buscar os comentários/observações do dia para enriquecer a IA
    comments_context = ""
    try:
        from models.comment import Comment
        comments = db.query(Comment).filter(Comment.ticket_id.in_(ticket_ids)).all()
        if comments:
            comments_context = "Observações registadas nestas tarefas:\n" + "\n".join([f"- Tarefa #{c.ticket_id}: {c.text}" for c in comments])
    except Exception as e:
        print("Erro a buscar comentários:", e)
        pass
        
    tasks_context = ""
    for t in tickets:
        tasks_context += f"- #{t.id} {t.title} (Estado: {t.status}) -> Tempo gasto hoje: {round(hours_per_ticket[t.id], 2)}h\n"
        
    prompt = f"""
    És um assistente técnico operacional sénior da RFS. O teu objetivo é analisar e redigir o relatório diário profissional de um técnico.
    
    Aqui estão os dados das tarefas em que ele trabalhou hoje e o respetivo tempo de execução:
    {tasks_context}
    
    {comments_context}
    
    Com base nisto, redige o relatório seguindo ESTRITAMENTE este formato e usando um tom formal e limpo:
    RESUMO:
    (Escreve aqui um parágrafo curto e direto ao assunto com o resumo global do dia)
    DETALHADO:
    (Escreve aqui o relatório longo detalhado do dia, cruzando as horas, as tarefas e justificando o trabalho contínuo)
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt,
        )
        text = response.text
        summary = ""
        detailed = ""
        
        # Partir o texto nas secções certas baseadas nas tags que pedimos ao Gemini
        if "RESUMO:" in text and "DETALHADO:" in text:
            parts = text.split("DETALHADO:")
            summary = parts[0].replace("RESUMO:", "").strip()
            detailed = parts[1].strip()
        else:
            detailed = text
            summary = "Resumo detalhado gerado abaixo."
            
        return {"summary": summary, "detailed_report": detailed}
    except Exception as e:
        # AQUI VAMOS IMPRIMIR O ERRO REAL NA CONSOLA E NO ECRÃ
        error_msg = str(e)
        print(f"ERRO CRÍTICO NA IA: {error_msg}")
        traceback.print_exc() # Imprime o erro completo na consola do terminal
        
        return {
            "summary": "Erro técnico ao gerar IA.", 
            "detailed_report": f"O Gemini devolveu o seguinte erro: {error_msg}"
        }


@router.put("/my-day/today")
def update_daily_report(
    report_data: dict, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    report = db.query(DailyReport).filter(
        DailyReport.user_id == current_user.id, 
        DailyReport.date == today
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Relatório de hoje não encontrado.")
        
    # Grava os dados finais do relatório
    report.summary = report_data.get("summary", report.summary)
    report.detailed_report = report_data.get("detailed_report", report.detailed_report)
    report.kilometers = report_data.get("kilometers", report.kilometers)
    report.overtime_hours = report_data.get("overtime_hours", report.overtime_hours)
    
    # Muda o estado para submetido conforme as regras da RFS
    report.status = "Submetido" 
    
    db.commit()
    db.refresh(report)
    return {"message": "Relatório diário submetido com sucesso!"}


@router.put("/my-day/reopen")
def reopen_daily_report(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    today = date.today()
    report = db.query(DailyReport).filter(
        DailyReport.user_id == current_user.id, 
        DailyReport.date == today
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
        
    # Volta a colocar o relatório em modo Rascunho!
    report.status = "Rascunho"
    
    db.commit()
    db.refresh(report)
    return {"message": "Relatório reaberto com sucesso!"}