from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models.feedback import FeedbackRequest, FeedbackResponse
from models.user import User
from models.ticket import Ticket
from models.project import Project
from models.notification import Notification
from schemas.feedback import FeedbackRequestCreate, FeedbackResponseCreate, FeedbackRequestOut, FeedbackResponseOut
from core.security import get_current_user
from typing import List
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"]
)

# 1. Criar Pedido de Feedback (Atribui estritamente ao responsável pela tarefa e exclui o gestor)
@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_feedback_request(
    data: FeedbackRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    if role not in ["admin", "manager", "gestor de operações"]:
        raise HTTPException(status_code=403, detail="Apenas gestores podem solicitar pedidos de feedback.")

    target_users = data.target_user_ids or []
    if data.ticket_id:
        ticket = db.query(Ticket).filter(Ticket.id == data.ticket_id).first()
        if ticket and ticket.assigned_to_id:
            target_users = [ticket.assigned_to_id]

    target_users = [uid for uid in target_users if uid != current_user.id]

    req = FeedbackRequest(
        title=data.title,
        description=data.description,
        ticket_id=data.ticket_id,
        project_id=data.project_id,
        created_by_id=current_user.id,
        deadline=data.deadline
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    deadline_str = data.deadline.strftime("%d/%m/%Y às %H:%M")
    
    for uid in target_users:
        db.add(Notification(
            user_id=uid,
            message=f"📋 Foi solicitado o teu feedback para a tarefa: '{data.title}'. Prazo: {deadline_str}"
        ))

    db.commit()
    return {"message": "Pedido de feedback criado e enviado ao responsável com sucesso!", "id": req.id}

# 2. Listar Pedidos de Feedback Pendentes estritamente para o Colaborador Responsável
@router.get("/my-pending", response_model=List[FeedbackRequestOut])
def get_my_pending_feedback_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.utcnow()
    all_requests = db.query(FeedbackRequest).filter(FeedbackRequest.deadline >= now).all()
    
    result = []
    for req in all_requests:
        # 🔒 FILTRA ESTRITAMENTE: O pedido só pertence ao utilizador se ele for o responsável pela tarefa associada
        if req.ticket_id:
            ticket = db.query(Ticket).filter(Ticket.id == req.ticket_id).first()
            if not ticket or ticket.assigned_to_id != current_user.id:
                continue # Salta este pedido se não for para este utilizador
        else:
            # Se não tiver ticket associado, verifica se está nos target_users ou se foi explicitamente direcionado
            continue

        user_response = db.query(FeedbackResponse).filter(
            FeedbackResponse.request_id == req.id,
            FeedbackResponse.user_id == current_user.id
        ).first()

        creator = db.query(User).filter(User.id == req.created_by_id).first()
        creator_name = creator.name if creator and creator.name else "Gestão"

        result.append(FeedbackRequestOut(
            id=req.id,
            title=req.title,
            description=req.description,
            ticket_id=req.ticket_id,
            project_id=req.project_id,
            deadline=req.deadline,
            created_at=req.created_at,
            created_by_name=creator_name,
            has_responded=bool(user_response),
            responses=[]
        ))

    return result

# 3. Submeter Resposta ao Feedback
@router.post("/requests/{request_id}/respond", status_code=status.HTTP_201_CREATED)
def submit_feedback_response(
    request_id: int,
    data: FeedbackResponseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req = db.query(FeedbackRequest).filter(FeedbackRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pedido de feedback não encontrado.")

    if datetime.utcnow() > req.deadline:
        raise HTTPException(status_code=400, detail="O prazo para submeter este feedback já expirou.")

    existing = db.query(FeedbackResponse).filter(
        FeedbackResponse.request_id == request_id,
        FeedbackResponse.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Já respondeste a este pedido de feedback.")

    resp = FeedbackResponse(
        request_id=request_id,
        user_id=current_user.id,
        rating=data.rating,
        comment=data.comment
    )
    db.add(resp)
    
    db.add(Notification(
        user_id=req.created_by_id,
        message=f"⭐ {current_user.name or current_user.email} respondeu ao pedido de feedback '{req.title}' com nota {data.rating}/5."
    ))

    db.commit()
    return {"message": "Feedback submetido com sucesso!"}

# 4. Listar Todos os Feedbacks com Respostas (Painel de Gestão)
@router.get("/summary", response_model=List[FeedbackRequestOut])
def get_feedback_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = getattr(current_user, "role", "Member").lower()
    if role not in ["admin", "manager", "gestor de operações"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    requests = db.query(FeedbackRequest).order_by(FeedbackRequest.created_at.desc()).all()
    result = []

    for req in requests:
        responses_out = []
        total_rating = 0

        for r in req.responses:
            u = db.query(User).filter(User.id == r.user_id).first()
            responses_out.append(FeedbackResponseOut(
                id=r.id,
                user_id=r.user_id,
                user_name=u.name if u and u.name else (u.email if u else "Anónimo"),
                rating=r.rating,
                comment=r.comment,
                created_at=r.created_at
            ))
            total_rating += r.rating

        avg = round(total_rating / len(req.responses), 1) if req.responses else 0.0
        creator = db.query(User).filter(User.id == req.created_by_id).first()

        result.append(FeedbackRequestOut(
            id=req.id,
            title=req.title,
            description=req.description,
            ticket_id=req.ticket_id,
            project_id=req.project_id,
            deadline=req.deadline,
            created_at=req.created_at,
            created_by_name=creator.name if creator and creator.name else "Gestão",
            has_responded=False,
            average_rating=avg,
            responses=responses_out
        ))

    return result

# 5. Listar Pedidos de Feedback filtrados por Tarefa (ticket_id)
@router.get("/requests", response_model=List[FeedbackRequestOut])
def get_feedback_requests_by_ticket(
    ticket_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(FeedbackRequest)
    if ticket_id is not None:
        query = query.filter(FeedbackRequest.ticket_id == ticket_id)
    
    requests = query.order_by(FeedbackRequest.created_at.desc()).all()
    result = []

    for req in requests:
        responses_out = []
        total_rating = 0

        for r in req.responses:
            u = db.query(User).filter(User.id == r.user_id).first()
            responses_out.append(FeedbackResponseOut(
                id=r.id,
                user_id=r.user_id,
                user_name=u.name if u and u.name else (u.email if u else "Anónimo"),
                rating=r.rating,
                comment=r.comment,
                created_at=r.created_at
            ))
            total_rating += r.rating

        avg = round(total_rating / len(req.responses), 1) if req.responses else 0.0
        creator = db.query(User).filter(User.id == req.created_by_id).first()

        user_response = db.query(FeedbackResponse).filter(
            FeedbackResponse.request_id == req.id,
            FeedbackResponse.user_id == current_user.id
        ).first()

        result.append(FeedbackRequestOut(
            id=req.id,
            title=req.title,
            description=req.description,
            ticket_id=req.ticket_id,
            project_id=req.project_id,
            deadline=req.deadline,
            created_at=req.created_at,
            created_by_name=creator.name if creator and creator.name else "Gestão",
            has_responded=bool(user_response),
            average_rating=avg,
            responses=responses_out
        ))

    return result

# 6. Rotina de Aviso Prévio (30 minutos antes do prazo)
@router.post("/check-reminders")
def check_feedback_reminders(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    reminder_window_start = now + timedelta(minutes=25)
    reminder_window_end = now + timedelta(minutes=35)

    impending_requests = db.query(FeedbackRequest).filter(
        FeedbackRequest.deadline >= reminder_window_start,
        FeedbackRequest.deadline <= reminder_window_end
    ).all()

    notified_count = 0
    for req in impending_requests:
        all_users = db.query(User).all()
        for u in all_users:
            has_resp = db.query(FeedbackResponse).filter(
                FeedbackResponse.request_id == req.id,
                FeedbackResponse.user_id == u.id
            ).first()

            if not has_resp:
                msg = f"⏳ LEMBRETE: Faltam 30 minutos para terminar o prazo do feedback '{req.title}'!"
                exists = db.query(Notification).filter(
                    Notification.user_id == u.id,
                    Notification.message == msg
                ).first()

                if not exists:
                    db.add(Notification(user_id=u.id, message=msg))
                    notified_count += 1

    db.commit()
    return {"reminders_sent": notified_count}