# VibeHub 可视化点击选中和 AI 自然语言修改功能 - 实现文档

## 概述

本实现为 VibeHub 添加了可视化点击选中和 AI 自然语言修改功能。用户可以在预览页面中点击任意元素，系统会高亮显示该元素并弹出 AI 修改输入框，用户可以用自然语言描述想要的修改，AI 会根据上下文精确修改对应组件代码。

## 实现原理

1. **元素追踪**: AI 生成的代码自动注入 `data-vhub-id` 和 `data-vhub-file` 属性
2. **沙箱注入**: overlay.js 脚本注入到预览页面，监听点击事件
3. **消息通信**: 通过 `postMessage` 在 iframe 和父窗口之间传递选中元素信息
4. **AI 修改**: 后端根据选中元素上下文，精确修改对应文件

## 修改的文件列表

### 1. 后端文件

#### `backend/agent/prompts.py`
- **修改内容**: 在 `PHASE_IMPLEMENTATION_SYSTEM_PROMPT` 中添加了 VibeHub 元素追踪规则
- **详细说明**:
  - 要求 AI 为每个 JSX 元素添加 `data-vhub-id` 和 `data-vhub-file` 属性
  - ID 格式: `componentName-elementType-index` (如 "hero-button-1")
  - 应用于按钮、链接、输入框、卡片、区块、标题、图片等可交互元素

#### `backend/agent/state.py`
- **修改内容**: 在 `CodeGenState` 中添加可视化编辑相关字段
- **新增字段**:
  - `target_file: str | None` - AI 编辑的目标文件
  - `selected_element_id: str | None` - 选中的元素 ID

#### `backend/agent/graph.py`
- **修改内容**: `run_codegen` 函数添加 `target_file` 参数
- **用途**: 支持针对特定文件的 AI 编辑

#### `backend/agent/nodes/sandbox_execution.py`
- **修改内容**: 添加 overlay 脚本注入逻辑
- **新增函数**:
  - `_inject_overlay_script()`: 将 overlay.js 脚本注入到 HTML 入口文件
  - 支持 Next.js (通过 Script 组件) 和 React Vite (直接注入 script 标签)

#### `backend/sandbox/e2b_backend.py`
- **修改内容**: `write_files` 方法添加 overlay 脚本写入
- **新增方法**:
  - `_write_overlay_script()`: 将 overlay.js 写入沙箱的 public 目录

#### `backend/api/websocket.py`
- **修改内容**: 添加 `element_selected` 和 `ai_edit_request` 消息处理
- **新增函数**:
  - `_run_ai_edit()`: 处理 AI 编辑请求，注入文件上下文到 prompt
- **消息处理**:
  - `element_selected`: 广播选中元素信息到所有连接
  - `ai_edit_request`: 启动 AI 编辑任务

### 2. 前端文件

#### `frontend/src/types/websocket.ts`
- **修改内容**: 扩展 WebSocket 消息类型
- **新增类型**:
  - `SelectedElement`: 选中元素的数据结构
  - `ClientMessage`: 添加 `element_selected` 和 `ai_edit_request` 消息
  - `ServerMessage`: 添加 `element_selected`, `ai_edit_started`, `ai_edit_completed` 消息

#### `frontend/src/hooks/use-chat.ts`
- **修改内容**: 添加可视化编辑状态管理
- **新增状态**:
  - `selectedElement`: 当前选中的元素
  - `selectionMode`: 是否处于选择模式
- **新增方法**:
  - `toggleSelectionMode()`: 切换选择模式
  - `selectElement()`: 选择元素并发送到服务器
  - `sendAiEditRequest()`: 发送 AI 编辑请求
  - `clearSelection()`: 清除选中状态

#### `frontend/src/components/preview/preview-iframe.tsx`
- **修改内容**: 重构以支持元素选择
- **新增功能**:
  - 监听来自 iframe 的 `postMessage` 消息
  - 处理 `VIBEHUB_OVERLAY_READY` 和 `VIBEHUB_ELEMENT_SELECTED` 事件
  - 根据 `selectionMode` 状态激活/停用 overlay
  - 显示选择模式提示浮层

#### `frontend/src/routes/chat.tsx`
- **修改内容**: 集成可视化编辑 UI
- **新增功能**:
  - "Select" 按钮用于切换选择模式
  - AI 编辑对话框（显示选中元素信息和输入框）
  - 处理元素选择和 AI 编辑请求

### 3. 静态资源

#### `static/overlay.js` (新增)
- **功能**: 注入到沙箱预览页面的脚本
- **主要功能**:
  - 监听鼠标移动，高亮显示可追踪元素
  - 监听点击事件，获取元素信息
  - 绘制高亮边框（蓝色悬停，绿色选中）
  - 通过 `postMessage` 向父窗口发送选中元素信息
  - 监听父窗口消息，支持激活/停用/清除选择

## 数据流

```
用户点击预览元素
    ↓
overlay.js 捕获点击事件
    ↓
提取 data-vhub-id 和 data-vhub-file
    ↓
postMessage 发送到父窗口
    ↓
preview-iframe.tsx 接收消息
    ↓
调用 selectElement() 更新状态
    ↓
WebSocket 发送 element_selected 到服务器
    ↓
服务器广播到所有客户端
    ↓
显示 AI 编辑对话框
    ↓
用户输入修改描述
    ↓
发送 ai_edit_request
    ↓
后端构建包含文件上下文的 prompt
    ↓
AI 生成修改后的代码
    ↓
更新沙箱文件并重新部署
```

## 技术细节

### data-* 属性规范

- `data-vhub-id`: 元素唯一标识，格式为 `componentName-elementType-index`
- `data-vhub-file`: 文件相对路径，如 `src/components/Hero.tsx`

### 消息协议

**iframe → Parent:**
- `VIBEHUB_OVERLAY_READY`: overlay 脚本加载完成
- `VIBEHUB_ELEMENT_SELECTED`: 元素被选中

**Parent → iframe:**
- `VIBEHUB_OVERLAY_ACTIVATE`: 激活选择模式
- `VIBEHUB_OVERLAY_DEACTIVATE`: 停用选择模式
- `VIBEHUB_CLEAR_SELECTION`: 清除选中状态

### 安全考虑

1. iframe 使用 `sandbox="allow-scripts allow-same-origin allow-forms allow-popups"`
2. postMessage 验证来源域名
3. 只在开发/预览模式注入 overlay 脚本

## 兼容性

- 支持 React Vite 和 Next.js 模板
- 支持现代浏览器（使用 ES6+ 语法）
- 不影响生产构建（data-* 属性只在开发模式注入）

## 后续优化建议

1. 支持多元素同时选择
2. 添加元素层级导航（父元素/子元素）
3. 支持样式实时预览（修改前预览效果）
4. 添加修改历史记录
5. 支持撤销/重做功能
