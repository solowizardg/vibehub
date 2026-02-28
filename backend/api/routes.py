from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    FileInfo,
    MessageInfo,
    PhaseInfo,
    SessionDetail,
    SessionInfo,
)
from db.crud import create_session, get_session, list_sessions
from db.database import get_db

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_new_session(req: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = await create_session(db, title=req.query[:100], template_name=req.template, user_query=req.query)
    return CreateSessionResponse(
        session_id=session.id,
        websocket_url=f"/ws/{session.id}",
    )


@router.get("/sessions", response_model=list[SessionInfo])
async def get_all_sessions(db: AsyncSession = Depends(get_db)):
    sessions = await list_sessions(db)
    return [
        SessionInfo(
            id=s.id,
            title=s.title,
            status=s.status,
            template_name=s.template_name,
            preview_url=s.preview_url,
            blueprint=s.blueprint,
            blueprint_markdown=s.blueprint_markdown,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(
        session=SessionInfo(
            id=session.id,
            title=session.title,
            status=session.status,
            template_name=session.template_name,
            preview_url=session.preview_url,
            blueprint=session.blueprint,
            blueprint_markdown=session.blueprint_markdown,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
        ),
        files=[
            FileInfo(
                file_path=f.file_path,
                file_contents=f.file_contents,
                language=f.language,
                phase_index=f.phase_index,
            )
            for f in session.files
        ],
        phases=[
            PhaseInfo(
                phase_index=p.phase_index,
                name=p.name,
                description=p.description,
                status=p.status,
                files=p.files,
            )
            for p in session.phases
        ],
        messages=[
            MessageInfo(
                id=m.id,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                created_at=m.created_at.isoformat(),
            )
            for m in session.messages
        ],
    )
