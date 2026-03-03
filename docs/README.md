# VibeHub 文档目录

本文档目录包含项目的设计文档、架构说明和实现细节。

## 文档索引

### 架构设计

| 文档 | 描述 |
|-----|------|
| [ai-code-quality.md](ai-code-quality.md) | AI 代码生成质量改进 - 实现文档 |
| [ai-code-quality-plan.md](ai-code-quality-plan.md) | AI 代码生成质量改进 - 完整方案设计 |
| [model-switching.md](model-switching.md) | LLM 模型切换方案 |
| [visual-editor-enhancement-plan.md](visual-editor-enhancement-plan.md) | 可视化编辑增强方案（预览/编辑模式、增量修改） |

### 待添加文档

- `architecture.md` - 系统架构详细说明
- `websocket-protocol.md` - WebSocket 通信协议规范
- `template-system.md` - 模板系统使用指南
- `deployment.md` - 部署指南

## 文档维护规范

1. **新增功能必须更新文档**
   - 修改 `CLAUDE.md` 添加概述
   - 在 `docs/` 下创建详细文档
   - 更新本文档索引

2. **文档格式**
   - 使用 Markdown 格式
   - 包含标题、概述、详细说明
   - 重要配置加代码块

3. **版本记录**
   - 在文档顶部标注日期
   - 重大修改记录变更历史
