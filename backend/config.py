from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, override=False)


class Settings(BaseSettings):
    e2b_api_key: str = ""
    e2b_template_nextjs: str = ""
    e2b_template_react_vite: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-3-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "moonshotai/kimi-k2.5"
    database_url: str = "sqlite+aiosqlite:///./vibehub.db"
    frontend_url: str = "http://localhost:5173"
    debug: bool = True
    langchain_tracing_v2: str = "false"
    langchain_api_key: str = ""
    langchain_project: str = "vibehub"

    # 实验性功能开关 (Experimental Features)
    feat_realtime_editor: bool = False  # 实时代码编辑和热更新
    feat_multi_blueprint: bool = False  # 多方案生成对比
    feat_cms_strapi: bool = False       # Strapi CMS 对接
    feat_deploy_vercel: bool = False    # 一键部署到 Vercel
    feat_visual_editing: bool = False   # 可视化点击编辑

    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
