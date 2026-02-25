from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    query: str
    template: str = "react-vite"


class CreateSessionResponse(BaseModel):
    session_id: str
    websocket_url: str


class SessionInfo(BaseModel):
    id: str
    title: str
    status: str
    template_name: str
    preview_url: str | None
    blueprint: dict | None = None
    created_at: str
    updated_at: str


class FileInfo(BaseModel):
    file_path: str
    file_contents: str
    language: str
    phase_index: int


class PhaseInfo(BaseModel):
    phase_index: int
    name: str
    description: str
    status: str
    files: list[str] | None


class MessageInfo(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: dict | None
    created_at: str


class SessionDetail(BaseModel):
    session: SessionInfo
    files: list[FileInfo]
    phases: list[PhaseInfo]
    messages: list[MessageInfo]
