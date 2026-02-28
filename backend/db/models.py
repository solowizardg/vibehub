import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), default="Untitled")
    blueprint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blueprint_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    blueprint_variants: Mapped[list | None] = mapped_column(JSON, nullable=True)
    selected_variant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    template_name: Mapped[str] = mapped_column(String(100), default="react-vite")
    preview_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sandbox_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    files: Mapped[list["GeneratedFile"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    phases: Mapped[list["Phase"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class GeneratedFile(Base):
    __tablename__ = "generated_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(500))
    file_contents: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(50), default="plaintext")
    phase_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped["Session"] = relationship(back_populates="files")


class Phase(Base):
    __tablename__ = "phases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"))
    phase_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped["Session"] = relationship(back_populates="phases")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped["Session"] = relationship(back_populates="messages")
