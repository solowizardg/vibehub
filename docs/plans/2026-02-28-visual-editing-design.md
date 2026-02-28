# 可视化点击编辑设计文档

**日期**: 2026-02-28
**功能**: 点击选中 + AI 自然语言修改组件
**状态**: 设计完成，待实现

---

## 1. 概述

### 1.1 目标
让不懂技术的用户能够通过点击预览界面中的组件，使用自然语言描述修改需求，由 AI 自动完成代码修改。

### 1.2 用户流程

```
1. 点击"编辑模式"按钮进入编辑状态
   ↓
2. 在预览界面 hover 组件，显示组件名称浮层
   ↓
3. 点击选中组件
   ↓
4. 左侧聊天输入框自动带入：`修改 [组件名] 组件：`
   ↓
5. 用户继续输入修改要求，如"把标题改成蓝色，字号加大"
   ↓
6. 发送消息 → AI 只修改该组件 → 热刷新预览
```

### 1.3 核心原则
- **零代码**: 用户无需查看或编辑代码
- **精准定位**: AI 只修改选中的组件，不影响其他部分
- **即时反馈**: 修改后通过 HMR 立即刷新预览
- **上下文感知**: AI 知道组件名称、文件路径和代码内容

---

## 2. 数据流图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户操作流程                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  用户点击                    hover 显示                    点击选中
  "编辑模式"                   组件名称                      组件
     │                          │                            │
     ▼                          ▼                            ▼
┌─────────┐              ┌─────────────┐              ┌─────────────┐
│ 进入编辑 │              │  overlay.js │              │ postMessage │
│  状态   │              │  显示浮层   │              │ 发送选中信息 │
└────┬────┘              └─────────────┘              └──────┬──────┘
     │                                                       │
     │               ┌─────────────────────┐                 │
     └──────────────►│   PreviewIframe     │◄────────────────┘
                     │   (React组件)        │
                     └──────────┬──────────┘
                                │
                                │ 1. 接收 element_selected 消息
                                │ 2. 解析 {component, file, code}
                                │ 3. 调用 onElementSelect 回调
                                ▼
                     ┌─────────────────────┐
                     │     ChatPage        │
                     │   (路由组件)         │
                     └──────────┬──────────┘
                                │
                                │ 设置 selectedElement 状态
                                ▼
                     ┌─────────────────────┐
                     │     ChatInput       │
                     │   (输入组件)         │
                     │                     │
                     │ 输入框自动填充：      │
                     │ "修改 HeroSection    │
                     │  组件："             │
                     └──────────┬──────────┘
                                │
                                │ 用户输入修改要求
                                │ 点击发送
                                ▼
                     ┌─────────────────────┐
                     │     useChat Hook    │
                     │                     │
                     │ 构建 context 消息：  │
                     │ - 组件名称           │
                     │ - 文件路径           │
                     │ - 当前代码           │
                     │ - 用户修改要求       │
                     └──────────┬──────────┘
                                │
                                │ WebSocket
                                │ modify_component 消息
                                ▼
                     ┌─────────────────────┐
                     │   WebSocket Handler │
                     │   (backend/api/     │
                     │    websocket.py)    │
                     └──────────┬──────────┘
                                │
                                │ 调用 AI 修改
                                ▼
                     ┌─────────────────────┐
                     │  AI Component Modify│
                     │  (backend/agent/    │
                     │   nodes/...)        │
                     │                     │
                     │ Prompt: 只修改指定  │
                     │ 组件，保持其他不变  │
                     └──────────┬──────────┘
                                │
                                │ 生成修改后的代码
                                ▼
                     ┌─────────────────────┐
                     │  Sandbox Execution  │
                     │  (E2B 沙箱)         │
                     │                     │
                     │ - 写入文件          │
                     │ - HMR 热刷新        │
                     └─────────────────────┘
```

---

## 3. WebSocket API 定义

### 3.1 新增 Client → Server 消息

#### `element_selected`
用户点击选中组件时发送。

```typescript
{
  type: 'element_selected';
  component: string;      // 组件名，如 "HeroSection"
  filePath: string;       // 文件路径，如 "src/components/HeroSection.tsx"
  elementId?: string;     // DOM 元素 ID (可选)
}
```

#### `modify_component`
用户要求修改组件时发送（复用现有的 `user_suggestion`，增加 context）。

```typescript
{
  type: 'user_suggestion';
  message: string;        // 用户输入的修改要求
  context?: {
    targetComponent: string;    // 目标组件名
    filePath: string;           // 文件路径
    currentCode: string;        // 当前代码内容
  };
}
```

### 3.2 新增 Server → Client 消息

#### `element_select_ack`
确认收到选中事件，可附带代码内容。

```typescript
{
  type: 'element_select_ack';
  component: string;
  filePath: string;
  codeSnippet: string;    // 组件代码片段（前端展示用）
}
```

### 3.3 更新 TypeScript 类型定义

```typescript
// frontend/src/types/websocket.ts

export interface ElementSelectionContext {
  component: string;
  filePath: string;
  codeSnippet: string;
}

export type ClientMessage =
  | // ... 现有消息类型
  | { type: 'element_selected'; component: string; filePath: string; elementId?: string }
  | { type: 'user_suggestion'; message: string; context?: ElementSelectionContext };

export type ServerMessage =
  | // ... 现有消息类型
  | { type: 'element_select_ack'; component: string; filePath: string; codeSnippet: string };
```

---

## 4. 组件接口

### 4.1 PreviewIframe 组件

```typescript
interface PreviewIframeProps {
  url: string | null;
  isEditMode: boolean;                    // 是否处于编辑模式
  onElementSelect?: (info: {
    component: string;
    filePath: string;
    codeSnippet: string;
  }) => void;
}
```

**职责**:
- 注入 `static/overlay.js` 脚本到 iframe
- 监听 `message` 事件接收选中信息
- 向后端请求代码片段（或从已有 files 状态获取）
- 调用 `onElementSelect` 回调

### 4.2 ChatInput 组件

```typescript
interface ChatInputProps {
  onSend: (message: string, context?: ElementSelectionContext) => void;
  onStop?: () => void;
  isGenerating: boolean;
  disabled?: boolean;
  placeholder?: string;
  // 新增
  selectedElement?: {
    component: string;
    filePath: string;
    codeSnippet: string;
  } | null;
  onClearSelection?: () => void;          // 清除选中状态
}
```

**职责**:
- 显示当前选中的组件标签（可删除）
- 输入框自动填充前缀 `修改 [组件名] 组件：`
- 发送时携带 context 信息

### 4.3 useChat Hook

```typescript
interface UseChatReturn {
  // ... 现有状态
  selectedElement: ElementSelectionContext | null;
  setSelectedElement: (element: ElementSelectionContext | null) => void;
  isEditMode: boolean;
  setIsEditMode: (enabled: boolean) => void;
}
```

**职责**:
- 管理编辑模式状态
- 管理选中元素状态
- 处理 `element_select_ack` 消息
- 构建带 context 的 `user_suggestion` 消息

---

## 5. 技术实现细节

### 5.1 模板组件标记 (Build Time)

在生成代码时，为每个组件的根元素添加 `data-*` 属性：

```tsx
// 生成的 HeroSection.tsx
export function HeroSection() {
  return (
    <section
      data-vhub-component="HeroSection"
      data-vhub-file="src/components/HeroSection.tsx"
      data-vhub-id="hero-section-001"
    >
      <h1>Welcome</h1>
    </section>
  );
}
```

**实现位置**: `backend/agent/nodes/phase_implementation.py`

**Prompt 修改**:
```
为每个导出的组件添加 data-* 属性：
- data-vhub-component: 组件名
- data-vhub-file: 文件路径
- data-vhub-id: 生成的唯一ID（可选）

示例：
<div data-vhub-component="HeroSection" data-vhub-file="src/components/HeroSection.tsx">
```

### 5.2 沙箱 Overlay 脚本 (Runtime)

创建 `static/overlay.js`，在沙箱页面加载时注入：

```javascript
// static/overlay.js
(function() {
  let isEditMode = false;
  let hoverElement = null;

  // 接收来自父窗口的消息
  window.addEventListener('message', (e) => {
    if (e.data.type === 'set_edit_mode') {
      isEditMode = e.data.enabled;
      document.body.style.cursor = isEditMode ? 'pointer' : '';
    }
  });

  // Hover 效果
  document.addEventListener('mouseover', (e) => {
    if (!isEditMode) return;
    const target = e.target.closest('[data-vhub-component]');
    if (target && target !== hoverElement) {
      hoverElement = target;
      showTooltip(target);
    }
  });

  // Click 选中
  document.addEventListener('click', (e) => {
    if (!isEditMode) return;
    const target = e.target.closest('[data-vhub-component]');
    if (target) {
      e.preventDefault();
      e.stopPropagation();
      window.parent.postMessage({
        type: 'element_selected',
        component: target.dataset.vhubComponent,
        filePath: target.dataset.vhubFile,
        elementId: target.dataset.vhubId
      }, '*');
    }
  });

  function showTooltip(element) {
    // 显示组件名称浮层
  }
})();
```

### 5.3 代码获取策略

当用户选中组件时，前端已有 `files` 状态包含所有文件内容，无需向后端请求：

```typescript
// useChat hook 中
const handleElementSelect = (info: { component: string; filePath: string }) => {
  // 从已有 files 状态中获取代码
  const file = files.find(f => f.filePath === info.filePath);
  if (file) {
    // 提取组件代码片段（可简化，发送整个文件内容）
    setSelectedElement({
      component: info.component,
      filePath: info.filePath,
      codeSnippet: file.fileContents
    });
  }
};
```

### 5.4 AI 修改 Prompt

```
用户想要修改组件 [COMPONENT_NAME]。

文件路径: [FILE_PATH]

当前代码:
```tsx
[CODE_SNIPPET]
```

用户修改要求: [USER_MESSAGE]

请只修改这个组件的代码，保持：
1. 组件导出名称不变
2. 文件路径不变
3. 其他组件的引用关系不变
4. 保留 data-vhub-* 属性

输出完整的修改后文件内容。
```

---

## 6. 错误处理策略

| 错误场景 | 处理策略 | 用户反馈 |
|---------|---------|---------|
| 用户未选中组件就发送修改请求 | 作为普通聊天消息处理 | 无特殊反馈 |
| 选中的文件不存在于 files 状态 | 显示错误提示 | "无法找到该组件的代码，请刷新页面重试" |
| AI 修改失败 | 显示错误消息 | "修改失败：[错误原因]" |
| 修改后的代码语法错误 | 进入 sandbox_fix 流程 | 显示修复状态 |
| 用户点击非组件区域 | 忽略点击 | 无反馈 |
| 沙箱页面未加载完成 | 延迟注入 overlay.js | 无反馈 |

---

## 7. UI 设计

### 7.1 编辑模式切换

在预览面板右上角添加切换按钮：

```
┌────────────────────────────────────────┐
│  Preview                    [编辑模式]  │  <- 切换按钮
├────────────────────────────────────────┤
│                                        │
│         [预览内容区域]                   │
│                                        │
│         [HeroSection]                   │  <- hover 显示组件名
│                                        │
└────────────────────────────────────────┘
```

### 7.2 聊天输入框

```
┌────────────────────────────────────────┐
│  📝 修改 HeroSection 组件      [x]     │  <- 选中标签，可删除
├────────────────────────────────────────┤
│ 把标题改成蓝色，字号加大...              │
│                                        │
│                              [发送]     │
└────────────────────────────────────────┘
```

---

## 8. 实现检查清单

### 后端
- [ ] 更新 `backend/agent/prompts.py` - 添加 data-* 属性生成规则
- [ ] 更新 `backend/api/schemas.py` - 添加 ElementSelectionContext schema
- [ ] 更新 `backend/api/websocket.py` - 处理 `element_selected` 和带 context 的 `user_suggestion`
- [ ] 创建 `backend/agent/nodes/component_modify.py` - 组件修改节点（或复用现有节点）
- [ ] 更新 `backend/agent/graph.py` - 添加组件修改路由

### 前端
- [ ] 创建 `static/overlay.js` - 沙箱页面注入脚本
- [ ] 更新 `frontend/src/types/websocket.ts` - 添加新消息类型
- [ ] 更新 `frontend/src/components/preview/preview-iframe.tsx` - 添加编辑模式支持
- [ ] 更新 `frontend/src/components/chat/chat-input.tsx` - 显示选中组件标签
- [ ] 更新 `frontend/src/hooks/use-chat.ts` - 管理编辑模式和选中状态
- [ ] 更新 `frontend/src/routes/chat.tsx` - 连接各组件

---

## 9. 相关文件

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `backend/agent/prompts.py` | 修改 | 添加 data-vhub-* 属性生成规则 |
| `backend/api/websocket.py` | 修改 | 处理新消息类型 |
| `frontend/src/types/websocket.ts` | 修改 | 添加 TypeScript 类型 |
| `frontend/src/hooks/use-chat.ts` | 修改 | 添加编辑状态管理 |
| `static/overlay.js` | 新增 | 沙箱页面交互脚本 |
| `frontend/src/components/preview/preview-iframe.tsx` | 修改 | 添加编辑模式支持 |
| `frontend/src/components/chat/chat-input.tsx` | 修改 | 添加组件标签显示 |

---

## 10. 后续优化方向

1. **多元素选中**: 支持选中多个组件同时修改
2. **样式隔离修改**: 只修改 CSS，不改 JSX 结构
3. **修改历史**: 记录每次修改，支持撤销
4. **实时预览**: 修改过程中实时预览效果（无需等待 AI 完成）
5. **智能推荐**: 根据组件类型推荐常见修改选项
