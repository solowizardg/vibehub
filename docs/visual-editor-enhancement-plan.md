# 可视化编辑增强方案

## 功能概述

增强 VibeHub 的可视化编辑能力，支持：
1. **预览/编辑模式切换** - 预览模式正常交互，编辑模式选择组件
2. **选中组件带入聊天框** - 针对特定组件提需求
3. **增量修改/追加蓝图** - 站点搭建完成后继续迭代

---

## 1. 前端架构设计

### 1.1 状态扩展

```typescript
// types/websocket.ts
export type PreviewMode = 'preview' | 'edit';

export interface SelectedElement {
  tagName: string;
  component: string | null;
  filePath: string | null;
  className: string;
  id: string;
  textContent: string | null;
}

// hooks/use-chat.ts 扩展
interface UseChatState {
  previewMode: PreviewMode;           // 新增：当前预览模式
  selectedElement: SelectedElement | null;  // 现有
  elementContext: string | null;      // 新增：选中元素的格式化上下文
}
```

### 1.2 UI 组件设计

#### 模式切换组件 (PreviewModeSwitcher)

```typescript
// components/preview/preview-mode-switcher.tsx
interface PreviewModeSwitcherProps {
  mode: PreviewMode;
  onModeChange: (mode: PreviewMode) => void;
  disabled?: boolean;
}
```

**设计稿：**
```
┌─────────────────────────────────────────┐
│  🔍 Preview    ✏️ Edit              │
│  [预览模式]   [编辑模式]            │
└─────────────────────────────────────────┘
```

- Preview 模式：正常浏览，可以点击链接、按钮
- Edit 模式：点击选择组件，显示高亮框

#### 选中组件信息卡片 (SelectedElementCard)

```typescript
// components/chat/selected-element-card.tsx
interface SelectedElementCardProps {
  element: SelectedElement;
  onClear: () => void;
  onFocus: () => void;  // 高亮预览中的组件
}
```

**设计稿：**
```
┌─────────────────────────────────────────┐
│ 🎯 Selected Component                   │
│ ├─ Component: HeroSection               │
│ ├─ File: src/components/hero.tsx        │
│ └─ Text: "Welcome to..."               │
│ [❌ Clear]    [👁️ Focus in Preview]   │
└─────────────────────────────────────────┘
```

#### 增强版聊天输入 (EnhancedChatInput)

```typescript
// components/chat/enhanced-chat-input.tsx
interface EnhancedChatInputProps {
  onSend: (message: string, context?: { selectedElement?: SelectedElement }) => void;
  selectedElement: SelectedElement | null;
  onClearSelection: () => void;
  // ...其他props
}
```

**占位符动态变化：**
- 无选中：`"Ask a follow-up question..."`
- 有选中：`"Describe how to modify {ComponentName}..."`

---

## 2. 后端协议扩展

### 2.1 新增 WebSocket 消息类型

```typescript
// types/websocket.ts (server → client)
export type ServerMessage =
  | ...existing types
  | { type: 'incremental_build_started'; phase_count: number }
  | { type: 'incremental_build_completed'; modified_files: string[] };

// types/websocket.ts (client → server)
export type ClientMessage =
  | ...existing types
  | {
      type: 'incremental_build_request';
      query: string;
      selected_element?: SelectedElement;
      target_files?: string[];  // 可选：指定修改文件范围
    }
  | {
      type: 'append_blueprint';
      query: string;  // 追加的新需求
    };
```

### 2.2 增量构建流程

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户选中   │────▶│  发送增量请求   │────▶│  解析修改意图   │
│   组件     │     │  (携带上下文)   │     │  (LLM分析)     │
└─────────────┘     └─────────────────┘     └────────┬────────┘
                                                     │
                        ┌────────────────────────────┘
                        ▼
               ┌─────────────────┐
               │  生成增量蓝图    │
               │  (仅修改目标)   │
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │  执行增量phase  │
               │  (保留其他文件) │
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │  沙箱验证      │
               │  → 热更新预览  │
               └─────────────────┘
```

### 2.3 后端节点扩展

#### 增量蓝图生成节点 (incremental_blueprint_node)

```python
# agent/nodes/incremental_blueprint.py

async def incremental_blueprint_node(state: CodeGenState, config) -> dict[str, Any]:
    """
    生成增量修改蓝图。

    输入：
    - user_query: 用户的修改需求
    - selected_element: 选中的组件信息（可选）
    - existing_blueprint: 现有蓝图
    - existing_files: 现有文件

    输出：
    - 增量修改计划（只包含需要修改的文件）
    - 保留其他文件不变
    """
    pass
```

#### 追加蓝图节点 (append_blueprint_node)

```python
# agent/nodes/append_blueprint.py

async def append_blueprint_node(state: CodeGenState, config) -> dict[str, Any]:
    """
    在现有蓝图基础上追加新功能。

    输入：
    - user_query: 新功能需求
    - existing_blueprint: 现有蓝图

    输出：
    - 扩展后的蓝图（新增 phases）
    - 保留已完成 phases 不变
    """
    pass
```

---

## 3. 详细交互流程

### 3.1 模式切换

```typescript
// 用户点击 "Edit" 模式
function handleModeChange(mode: PreviewMode) {
  setPreviewMode(mode);

  // 发送消息到 iframe
  iframeRef.current?.contentWindow?.postMessage({
    type: mode === 'edit' ? 'VIBEHUB_ENABLE_SELECTION' : 'VIBEHUB_DISABLE_SELECTION'
  }, '*');

  // 更新 UI 状态
  if (mode === 'preview') {
    setSelectedElement(null);  // 清除选中
  }
}
```

### 3.2 组件选择流程

```typescript
// 用户点击组件
function handleElementSelect(element: SelectedElement) {
  setSelectedElement(element);

  // 格式化上下文
  const context = formatElementContext(element);
  setElementContext(context);

  // 可选：自动滚动聊天框到可见
  scrollChatToVisible();
}

function formatElementContext(el: SelectedElement): string {
  return `[Selected: ${el.component || el.tagName} in ${el.filePath || 'unknown'}]`;
}
```

### 3.3 发送消息（携带上下文）

```typescript
function handleSendMessage(userMessage: string) {
  const message = selectedElement
    ? `[Context: Modifying ${selectedElement.component} in ${selectedElement.filePath}]\n\n${userMessage}`
    : userMessage;

  ws.send({
    type: 'incremental_build_request',
    query: message,
    selected_element: selectedElement,
  });

  // 清空选中（可选，或保留以便连续修改）
  // setSelectedElement(null);
}
```

---

## 4. Prompt 工程

### 4.1 增量修改 Prompt

```python
INCREMENTAL_BUILD_SYSTEM_PROMPT = """You are making incremental changes to an existing project.

## Context
User has selected a component to modify:
- Component: {component_name}
- File: {file_path}
- Current content preview: {text_content}

## Rules
1. ONLY modify the selected component and its direct dependencies
2. Preserve all other files exactly as they are
3. Maintain consistency with existing design_blueprint
4. If the change affects multiple files, list all files to modify

## Output Format
Return ONLY the files that need to change:

===FILE: {target_file_path}===
(complete new file content)
===END_FILE===

Do not output files that don't need changes.
"""
```

### 4.2 追加蓝图 Prompt

```python
APPEND_BLUEPRINT_SYSTEM_PROMPT = """You are extending an existing project with new features.

## Existing Blueprint
{existing_blueprint}

## New Requirements
{user_query}

## Rules
1. Analyze existing phases and their completion status
2. Create NEW phases for the additional features
3. Do NOT modify completed phases
4. Ensure new phases follow the same design system

## Output Format
Return only the NEW phases to append:

{{
  "additional_phases": [
    {{
      "name": "Phase Name",
      "description": "...",
      "files": ["src/components/NewFeature.tsx"]
    }}
  ]
}}
"""
```

---

## 5. 实现步骤

### Phase 1: 前端基础（1天）

1. **类型定义**
   - 更新 `types/websocket.ts`
   - 添加 `PreviewMode` 类型
   - 扩展 `SelectedElement` 接口

2. **状态管理**
   - 扩展 `useChat` hook
   - 添加 `previewMode` 和 `elementContext`

3. **UI 组件**
   - 创建 `PreviewModeSwitcher`
   - 创建 `SelectedElementCard`
   - 修改 `ChatInput` 支持上下文显示

### Phase 2: 后端协议（1天）

1. **消息类型**
   - 添加 `incremental_build_request`
   - 添加 `append_blueprint`

2. **Graph 扩展**
   - 创建增量构建分支
   - 添加 `incremental_blueprint_node`
   - 添加 `append_blueprint_node`

3. **Prompt**
   - 编写增量修改 prompt
   - 编写追加蓝图 prompt

### Phase 3: 集成测试（1天）

1. **联调**
   - 前端选中 → 后端修改 → 预览更新
   - 增量修改只影响目标文件
   - 追加蓝图正确扩展

2. **边界情况**
   - 选中组件文件不存在
   - 修改导致依赖错误
   - 沙箱热更新验证

---

## 6. 文件变更清单

### 前端

| 文件 | 变更 |
|-----|------|
| `types/websocket.ts` | 添加消息类型 |
| `hooks/use-chat.ts` | 扩展状态管理 |
| `components/preview/preview-mode-switcher.tsx` | 新建 |
| `components/chat/selected-element-card.tsx` | 新建 |
| `components/chat/chat-input.tsx` | 增强 |
| `components/preview/preview-iframe.tsx` | 支持模式切换 |
| `routes/chat.tsx` | 集成新组件 |

### 后端

| 文件 | 变更 |
|-----|------|
| `agent/state.py` | 添加增量构建状态 |
| `agent/graph.py` | 添加新节点路由 |
| `agent/nodes/incremental_blueprint.py` | 新建 |
| `agent/nodes/append_blueprint.py` | 新建 |
| `agent/prompts.py` | 添加新 prompts |
| `api/websocket.py` | 处理新消息类型 |

---

## 7. 预期效果

| 功能 | 效果 |
|-----|------|
| 预览/编辑模式 | 用户可以正常浏览站点，需要修改时切换到编辑模式选择组件 |
| 选中带入聊天 | 针对特定组件提需求，减少沟通成本 |
| 增量修改 | 只修改需要的文件，保持其他代码稳定 |
| 追加蓝图 | 支持项目持续迭代，不断添加新功能 |
