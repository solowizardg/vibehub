from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import GeneratedFile, Message, Phase, Session


async def create_session(db: AsyncSession, title: str, template_name: str = "react-vite") -> Session:
    session = Session(title=title, template_name=template_name)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    stmt = (
        select(Session)
        .options(selectinload(Session.files), selectinload(Session.phases), selectinload(Session.messages))
        .where(Session.id == session_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession) -> list[Session]:
    stmt = select(Session).order_by(Session.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_session(db: AsyncSession, session_id: str, **kwargs) -> Session | None:
    session = await get_session(db, session_id)
    if not session:
        return None
    for key, value in kwargs.items():
        if hasattr(session, key):
            setattr(session, key, value)
    await db.commit()
    await db.refresh(session)
    return session


async def patch_session(db: AsyncSession, session_id: str, **kwargs) -> bool:
    if not kwargs:
        return True
    stmt = (
        update(Session)
        .where(Session.id == session_id)
        .values(**kwargs)
    )
    result = await db.execute(stmt)
    await db.commit()
    return (result.rowcount or 0) > 0


async def add_file(db: AsyncSession, session_id: str, file_path: str, file_contents: str, language: str = "plaintext", phase_index: int = 0) -> GeneratedFile:
    f = GeneratedFile(session_id=session_id, file_path=file_path, file_contents=file_contents, language=language, phase_index=phase_index)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f


async def upsert_file(db: AsyncSession, session_id: str, file_path: str, file_contents: str, language: str = "plaintext", phase_index: int = 0) -> GeneratedFile:
    stmt = select(GeneratedFile).where(GeneratedFile.session_id == session_id, GeneratedFile.file_path == file_path)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.file_contents = file_contents
        existing.language = language
        existing.phase_index = phase_index
        await db.commit()
        await db.refresh(existing)
        return existing
    return await add_file(db, session_id, file_path, file_contents, language, phase_index)


async def get_phase(db: AsyncSession, session_id: str, phase_index: int) -> Phase | None:
    stmt = select(Phase).where(Phase.session_id == session_id, Phase.phase_index == phase_index)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def add_phase(
    db: AsyncSession,
    session_id: str,
    phase_index: int,
    name: str,
    description: str = "",
    status: str = "pending",
    files: list | None = None,
) -> Phase:
    phase = Phase(
        session_id=session_id,
        phase_index=phase_index,
        name=name,
        description=description,
        status=status,
        files=files,
    )
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return phase


async def upsert_phase(
    db: AsyncSession,
    session_id: str,
    phase_index: int,
    name: str,
    description: str = "",
    status: str = "pending",
    files: list | None = None,
) -> Phase:
    existing = await get_phase(db, session_id, phase_index)
    if existing:
        existing.name = name
        existing.description = description
        existing.status = status
        existing.files = files
        await db.commit()
        await db.refresh(existing)
        return existing
    return await add_phase(
        db,
        session_id=session_id,
        phase_index=phase_index,
        name=name,
        description=description,
        status=status,
        files=files,
    )


async def add_message(db: AsyncSession, session_id: str, role: str, content: str, tool_calls: dict | None = None) -> Message:
    msg = Message(session_id=session_id, role=role, content=content, tool_calls=tool_calls)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
