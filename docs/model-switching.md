# 模型切换方案

## 概述

VibeHub 支持通过环境变量灵活切换 LLM 模型，无需修改代码即可更换模型。

## 当前支持的模型提供商

### 1. Google Gemini（默认）
```bash
GOOGLE_API_KEY="your-api-key"
GEMINI_MODEL="gemini-3-flash"  # 可切换为其他模型
```

**可用模型参考：**
- `gemini-3-flash` - 当前默认，快速响应
- `gemini-3.1-flash` - 如果 Google 发布了 3.1 版本
- `gemini-3.1-pro` - 更高质量的代码生成
- `gemini-2.5-flash` - langchain-google 支持的最新版本
- `gemini-2.5-pro` - 更强的代码能力

### 2. OpenRouter（备选）
```bash
OPENROUTER_API_KEY="your-api-key"
OPENROUTER_MODEL="moonshotai/kimi-k2.5"
```

**可用模型：**
- `moonshotai/kimi-k2.5` - 中文友好的长上下文模型
- `anthropic/claude-sonnet-4` - Claude 系列
- `openai/gpt-4o` - GPT-4o 系列

## 切换步骤

### 方法一：仅修改环境变量（推荐）

1. 编辑 `backend/.env`：
```bash
# 修改模型名称
GEMINI_MODEL="gemini-3.1-flash"  # 假设的新模型

# 或切换到 OpenRouter
# 清空 Google key，启用 OpenRouter
GOOGLE_API_KEY=""
OPENROUTER_API_KEY="sk-..."
OPENROUTER_MODEL="moonshotai/kimi-k2.5"
```

2. 重启后端服务：
```bash
uvicorn main:app --reload --port 8000
```

### 方法二：动态模型选择（高级）

如需在运行时动态选择模型，可修改 `graph.py`：

```python
# agent/graph.py
def get_llm(model_override: str = None) -> BaseChatModel:
    """Get LLM with optional model override."""
    gemini_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_model = model_override or os.getenv("GEMINI_MODEL", "gemini-3-flash")

    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=gemini_model,
            google_api_key=gemini_key,
            temperature=0.2,
        )
    # ... fallback to OpenRouter
```

## 模型能力对比

| 模型 | 代码能力 | 速度 | 中文支持 | 适合场景 |
|-----|---------|------|---------|---------|
| gemini-3-flash | ⭐⭐⭐ | ⚡⚡⚡ | ⭐⭐⭐ | 快速原型 |
| gemini-3.1-flash | ⭐⭐⭐⭐ | ⚡⚡⚡ | ⭐⭐⭐ | 更好的代码质量 |
| gemini-3.1-pro | ⭐⭐⭐⭐⭐ | ⚡⚡ | ⭐⭐⭐ | 复杂项目 |
| kimi-k2.5 | ⭐⭐⭐⭐ | ⚡⚡ | ⭐⭐⭐⭐⭐ | 中文需求 |
| claude-sonnet-4 | ⭐⭐⭐⭐⭐ | ⚡⚡ | ⭐⭐⭐ | 最高代码质量 |

## 注意事项

1. **模型名称验证**：确保模型名称与提供商 API 一致
2. **上下文长度**：不同模型的上下文窗口不同（32K-2M tokens）
3. **费率差异**：Pro 模型通常更贵但更精准
4. **LangChain 兼容性**：确保 `langchain-google-genai` 版本支持目标模型

## 故障排查

### 模型切换后报错
```bash
# 检查模型名称是否正确
python -c "from langchain_google_genai import ChatGoogleGenerativeAI; \
           llm = ChatGoogleGenerativeAI(model='gemini-3.1-flash'); \
           print(llm.invoke('test'))"
```

### 回滚到原模型
```bash
# 只需改回原来的模型名称
GEMINI_MODEL="gemini-3-flash"
```

## 未来扩展

计划支持更多模型提供商：
- [ ] Anthropic Claude（原生 API）
- [ ] OpenAI GPT-4o
- [ ] 本地模型（Ollama）
- [ ] Azure OpenAI
