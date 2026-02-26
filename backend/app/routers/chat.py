from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatMessageOut,
    ChatSessionCreateRequest,
    ChatSessionOut,
)
from ..services.chat_engine import ask_chat, create_chat_session, get_chat_session_messages, list_chat_sessions

router = APIRouter()


@router.post("/chat/sessions", response_model=ChatSessionOut)
def create_session(payload: ChatSessionCreateRequest, db: Session = Depends(get_db)):
    session = create_chat_session(db, title=payload.title)
    return ChatSessionOut.model_validate(session)


@router.get("/chat/sessions", response_model=list[ChatSessionOut])
def list_sessions(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    sessions = list_chat_sessions(db, limit=limit)
    return [ChatSessionOut.model_validate(session) for session in sessions]


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_session_messages(
    session_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        messages = get_chat_session_messages(db, session_id=session_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [ChatMessageOut(**message) for message in messages]


@router.post("/chat/ask", response_model=ChatAskResponse)
def ask_chat_route(payload: ChatAskRequest, db: Session = Depends(get_db)):
    try:
        result = ask_chat(
            db,
            session_id=payload.session_id,
            message=payload.message,
            debug=payload.debug,
            force_deterministic=payload.force_deterministic,
        )
    except ValueError as exc:
        detail = str(exc).lower()
        status_code = 404 if "não encontrada" in detail or "nao encontrada" in detail else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ChatAskResponse(**result)
