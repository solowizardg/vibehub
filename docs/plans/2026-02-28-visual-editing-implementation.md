# 可视化点击编辑实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现点击预览界面组件，在聊天框中自动带入组件名称，通过自然语言让 AI 修改组件代码。

**Architecture:** 通过 data-* 属性标记组件，overlay.js 脚本处理点击事件，postMessage 与父窗口通信，将选中信息带入聊天输入框。

**Tech Stack:** React, TypeScript, WebSocket, Monaco Editor, E2B Sandbox

---

## 前置条件

- 确保 `frontend/src/types/websocket.ts` 存在
- 确保 `backend/agent/prompts.py` 存在
- 确保 `backend/api/websocket.py` 存在

---

## Task 1: 更新 WebSocket 类型定义

**Files:**
- Modify: `frontend/src/types/websocket.ts`

**Step 1: 添加 ElementSelectionContext 类型**

在文件末尾（`export type ClientMessage` 之前）添加：

```typescript
export interface ElementSelectionContext {
	component: string;
	filePath: string;
	codeSnippet: string;
}
```

**Step 2: 更新 ClientMessage 类型**

找到 `export type ClientMessage`，在 union 中添加新消息类型：

```typescript
export type ClientMessage =
	| { type: 'session_init'; query?: string; template?: string; read_only?: boolean; rebuild_sandbox?: boolean }
	| { type: 'generate_all'; query?: string; template?: string; read_only?: boolean }
	| { type: 'user_suggestion'; message: string; context?: ElementSelectionContext }
	| { type: 'stop_generation' }
	| { type: 'file_edit'; filePath: string; fileContents: string }
	| { type: 'select_blueprint_variant'; variantId: string }
	| { type: 'element_selected'; component: string; filePath: string; elementId?: string };
```

**Step 3: 更新 ServerMessage 类型**

找到 `export type ServerMessage`，在 union 中添加：

```typescript
export type ServerMessage =
	// ... 现有类型 ...
	| { type: 'element_select_ack'; component: string; filePath: string; codeSnippet: string };
```

**Step 4: Commit**

```bash
git add frontend/src/types/websocket.ts
git commit -m "feat: add element selection types for visual editing"
```

---

## Task 2: 更新 Backend Prompts 添加 data-* 属性规则

**Files:**
- Modify: `backend/agent/prompts.py`

**Step 1: 找到 PHASE_IMPLEMENTATION_SYSTEM_PROMPT**

搜索 `PHASE_IMPLEMENTATION_SYSTEM_PROMPT` 常量。

**Step 2: 在 Rules 部分添加新规则**

在 Rules 列表末尾（`Do NOT add comments that just narrate what code does` 之后）添加：

```python
PHASE_IMPLEMENTATION_SYSTEM_PROMPT = """You are an expert full-stack developer...

Rules:
- ... 现有规则 ...
- Do NOT add comments that just narrate what code does
- For EVERY exported React component, add data-vhub-* attributes to the root element:
  * data-vhub-component: The exact component name (e.g., "HeroSection")
  * data-vhub-file: The file path relative to project root (e.g., "src/components/HeroSection.tsx")
  Example: <div data-vhub-component="HeroSection" data-vhub-file="src/components/HeroSection.tsx">
"""
```

**Step 3: Commit**

```bash
git add backend/agent/prompts.py
git commit -m "feat: add data-vhub-* attribute rules to prompts"
```

---

## Task 3: 创建 Overlay.js 脚本

**Files:**
- Create: `frontend/static/overlay.js`

**Step 1: 创建目录（如果不存在）**

```bash
mkdir -p frontend/static
```

**Step 2: 创建 overlay.js 文件**

```javascript
/**
 * Visual Editing Overlay Script
 * Injected into sandbox preview for element selection
 */
(function() {
	'use strict';

	let isEditMode = false;
	let hoveredElement = null;
	let tooltip = null;
	let highlightOverlay = null;

	// Create tooltip element
	function createTooltip() {
		if (tooltip) return;
		tooltip = document.createElement('div');
		tooltip.style.cssText = `
			position: fixed;
			background: #2563eb;
			color: white;
			padding: 4px 8px;
			border-radius: 4px;
			font-size: 12px;
			font-family: system-ui, -apple-system, sans-serif;
			pointer-events: none;
			z-index: 999999;
			white-space: nowrap;
			box-shadow: 0 2px 4px rgba(0,0,0,0.2);
		`;
		document.body.appendChild(tooltip);
	}

	// Create highlight overlay
	function createHighlightOverlay() {
		if (highlightOverlay) return;
		highlightOverlay = document.createElement('div');
		highlightOverlay.style.cssText = `
			position: fixed;
			border: 2px solid #2563eb;
			background: rgba(37, 99, 235, 0.1);
			pointer-events: none;
			z-index: 999998;
			transition: all 0.15s ease;
		`;
		document.body.appendChild(highlightOverlay);
	}

	// Show tooltip for element
	function showTooltip(element) {
		if (!tooltip) createTooltip();
		if (!highlightOverlay) createHighlightOverlay();

		const componentName = element.dataset.vhubComponent || 'Unknown';
		const rect = element.getBoundingClientRect();

		// Update tooltip
		tooltip.textContent = componentName;
		tooltip.style.left = `${rect.left}px`;
		tooltip.style.top = `${rect.top - 28}px`;
		tooltip.style.display = 'block';

		// Update highlight
		highlightOverlay.style.left = `${rect.left}px`;
		highlightOverlay.style.top = `${rect.top}px`;
		highlightOverlay.style.width = `${rect.width}px`;
		highlightOverlay.style.height = `${rect.height}px`;
		highlightOverlay.style.display = 'block';
	}

	// Hide tooltip
	function hideTooltip() {
		if (tooltip) tooltip.style.display = 'none';
		if (highlightOverlay) highlightOverlay.style.display = 'none';
	}

	// Get closest element with data-vhub-component
	function getComponentElement(target) {
		return target.closest('[data-vhub-component]');
	}

	// Handle mouseover
	document.addEventListener('mouseover', (e) => {
		if (!isEditMode) return;
		const componentEl = getComponentElement(e.target);
		if (componentEl && componentEl !== hoveredElement) {
			hoveredElement = componentEl;
			showTooltip(componentEl);
		}
	});

	// Handle mouseout
	document.addEventListener('mouseout', (e) => {
		if (!isEditMode) return;
		const relatedTarget = e.relatedTarget;
		if (hoveredElement && !hoveredElement.contains(relatedTarget)) {
			hoveredElement = null;
			hideTooltip();
		}
	});

	// Handle click
	document.addEventListener('click', (e) => {
		if (!isEditMode) return;
		const componentEl = getComponentElement(e.target);
		if (componentEl) {
			e.preventDefault();
			e.stopPropagation();

			const data = {
				type: 'element_selected',
				component: componentEl.dataset.vhubComponent,
				filePath: componentEl.dataset.vhubFile,
				elementId: componentEl.dataset.vhubId
			};

			// Send to parent window
			if (window.parent !== window) {
				window.parent.postMessage(data, '*');
			}

			// Visual feedback
			highlightOverlay.style.borderColor = '#10b981';
			setTimeout(() => {
				highlightOverlay.style.borderColor = '#2563eb';
			}, 300);
		}
	}, true);

	// Listen for messages from parent
	window.addEventListener('message', (e) => {
		if (e.data?.type === 'set_edit_mode') {
			isEditMode = e.data.enabled;
			document.body.style.cursor = isEditMode ? 'pointer' : '';
			if (!isEditMode) {
				hideTooltip();
				hoveredElement = null;
			}
		}
	});

	// Notify parent that overlay is ready
	if (window.parent !== window) {
		window.parent.postMessage({ type: 'overlay_ready' }, '*');
	}

	console.log('[VibeHub Overlay] Initialized');
})();
```

**Step 3: Commit**

```bash
git add frontend/static/overlay.js
git commit -m "feat: add overlay.js for visual element selection"
```

---

## Task 4: 更新 PreviewIframe 组件支持编辑模式

**Files:**
- Modify: `frontend/src/components/preview/preview-iframe.tsx`

**Step 1: 更新 Props 接口**

```typescript
interface PreviewIframeProps {
	url: string | null;
	isEditMode?: boolean;
	onElementSelect?: (info: {
		component: string;
		filePath: string;
		elementId?: string;
	}) => void;
}
```

**Step 2: 更新组件函数签名和内部逻辑**

```typescript
export function PreviewIframe({
	url,
	isEditMode = false,
	onElementSelect,
}: PreviewIframeProps) {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(false);
	const [retryKey, setRetryKey] = useState(0);
	const iframeRef = useRef<HTMLIFrameElement>(null);

	// Send edit mode changes to iframe
	useEffect(() => {
		const iframe = iframeRef.current;
		if (!iframe?.contentWindow) return;

		iframe.contentWindow.postMessage(
			{ type: 'set_edit_mode', enabled: isEditMode },
			'*'
		);
	}, [isEditMode]);

	// Listen for messages from iframe
	useEffect(() => {
		const handleMessage = (e: MessageEvent) => {
			if (e.data?.type === 'element_selected') {
				onElementSelect?.({
					component: e.data.component,
					filePath: e.data.filePath,
					elementId: e.data.elementId,
				});
			}
		};

		window.addEventListener('message', handleMessage);
		return () => window.removeEventListener('message', handleMessage);
	}, [onElementSelect]);

	// ... rest of component
}
```

**Step 3: 更新 iframe 元素添加 ref**

```typescript
<iframe
	ref={iframeRef}
	key={retryKey}
	src={url}
	// ... other props
/>
```

**Step 4: 提交**

```bash
git add frontend/src/components/preview/preview-iframe.tsx
git commit -m "feat: add edit mode support to PreviewIframe"
```

---

## Task 5: 更新 ChatInput 组件显示选中组件

**Files:**
- Modify: `frontend/src/components/chat/chat-input.tsx`

**Step 1: 更新 Props 接口**

```typescript
import { X } from 'lucide-react';

interface SelectedComponent {
	component: string;
	filePath: string;
}

interface ChatInputProps {
	onSend: (message: string) => void;
	onStop?: () => void;
	isGenerating?: boolean;
	disabled?: boolean;
	placeholder?: string;
	selectedComponent?: SelectedComponent | null;
	onClearSelection?: () => void;
}
```

**Step 2: 更新组件函数**

```typescript
export function ChatInput({
	onSend,
	onStop,
	isGenerating,
	disabled,
	placeholder,
	selectedComponent,
	onClearSelection,
}: ChatInputProps) {
	const [value, setValue] = useState('');
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	// Auto-prefix when component selected
	useEffect(() => {
		if (selectedComponent && !value.startsWith(`修改 ${selectedComponent.component}`)) {
			setValue(`修改 ${selectedComponent.component} 组件：`);
			// Focus textarea
			textareaRef.current?.focus();
		}
	}, [selectedComponent]);

	const handleSubmit = () => {
		const trimmed = value.trim();
		if (!trimmed || disabled) return;
		onSend(trimmed);
		setValue('');
		if (textareaRef.current) textareaRef.current.style.height = '36px';
	};

	// ... rest of component
}
```

**Step 3: 添加选中组件标签 UI**

在 return 语句中，textarea 上方添加标签：

```typescript
return (
	<div className="border-t border-border p-4 pb-5">
		{selectedComponent && (
			<div className="mb-2 flex items-center gap-2">
				<span className="inline-flex items-center gap-1 rounded-full bg-brand/10 px-2 py-0.5 text-xs text-brand">
					修改 {selectedComponent.component}
					<button
						onClick={onClearSelection}
						className="ml-1 rounded-full p-0.5 hover:bg-brand/20"
						title="取消选择"
					>
						<X size={12} />
					</button>
				</span>
			</div>
		)}
		<div className="flex items-end gap-2 rounded-xl border border-border bg-surface-secondary p-2">
			{/* textarea ... */}
		</div>
	</div>
);
```

**Step 4: 提交**

```bash
git add frontend/src/components/chat/chat-input.tsx
git commit -m "feat: show selected component tag in ChatInput"
```

---

## Task 6: 更新 useChat Hook 管理编辑状态

**Files:**
- Modify: `frontend/src/hooks/use-chat.ts`

**Step 1: 添加新状态**

在 hook 顶部添加：

```typescript
const [isEditMode, setIsEditMode] = useState(false);
const [selectedElement, setSelectedElement] = useState<{
	component: string;
	filePath: string;
	codeSnippet: string;
} | null>(null);
```

**Step 2: 添加选中处理函数**

```typescript
const handleElementSelect = useCallback((info: {
	component: string;
	filePath: string;
	elementId?: string;
}) => {
	// Find file content from files state
	const file = files.find(f => f.filePath === info.filePath);
	if (file) {
		setSelectedElement({
			component: info.component,
			filePath: info.filePath,
			codeSnippet: file.fileContents,
		});
		// Auto-switch to chat tab could be added here
	}
}, [files]);

const clearElementSelection = useCallback(() => {
	setSelectedElement(null);
}, []);
```

**Step 3: 修改 sendMessage 处理带 context 的消息**

```typescript
const sendMessage = useCallback((message: string) => {
	if (!wsRef.current || connectionState !== 'connected') return;

	const payload: ClientMessage = selectedElement
		? {
				type: 'user_suggestion',
				message,
				context: {
					component: selectedElement.component,
					filePath: selectedElement.filePath,
					codeSnippet: selectedElement.codeSnippet,
				},
			}
		: {
				type: 'user_suggestion',
				message,
			};

	wsRef.current.send(JSON.stringify(payload));

	// Clear selection after sending
	setSelectedElement(null);
}, [connectionState, selectedElement]);
```

**Step 4: 更新返回值**

```typescript
return {
	// ... existing return values
	isEditMode,
	setIsEditMode,
	selectedElement,
	setSelectedElement,
	clearElementSelection,
};
```

**Step 5: 提交**

```bash
git add frontend/src/hooks/use-chat.ts
git commit -m "feat: add visual editing state management to useChat hook"
```

---

## Task 7: 更新 Chat 页面整合所有组件

**Files:**
- Modify: `frontend/src/routes/chat.tsx`

**Step 1: 从 useChat 解构新状态**

```typescript
const {
	messages,
	files,
	blueprint,
	isGenerating,
	previewUrl,
	connectionState,
	sendMessage,
	stopGeneration,
	initSession,
	// Add these:
	isEditMode,
	setIsEditMode,
	selectedElement,
	handleElementSelect,
	clearElementSelection,
} = useChat(chatId, { readOnly });
```

**Step 2: 添加编辑模式按钮到预览 Tab**

在 PreviewIframe 上方添加编辑模式切换按钮：

```typescript
{activeTab === 'preview' && (
	<>
		<div className="flex items-center justify-between border-b border-border px-3 py-1.5">
			<span className="text-xs text-text-secondary">
				{isEditMode ? '点击组件以在聊天框中修改' : '预览模式'}
			</span>
			<button
				onClick={() => setIsEditMode(!isEditMode)}
				className={cn(
					'rounded px-2 py-1 text-xs font-medium transition-colors',
					isEditMode
						? 'bg-brand text-white'
						: 'bg-surface-tertiary text-text-secondary hover:text-text-primary'
				)}
			>
				{isEditMode ? '退出编辑' : '编辑模式'}
			</button>
		</div>
		<PreviewIframe
			url={previewUrl}
			isEditMode={isEditMode}
			onElementSelect={handleElementSelect}
		/>
	</>
)}
```

**Step 3: 更新 ChatInput 传递选中组件**

```typescript
<ChatInput
	onSend={sendMessage}
	onStop={stopGeneration}
	isGenerating={isGenerating}
	disabled={readOnly}
	placeholder={
		readOnly
			? 'History project is read-only...'
			: isGenerating
				? 'Send a suggestion...'
				: selectedElement
					? `Describe changes for ${selectedElement.component}...`
					: 'Ask a follow-up question...'
	}
	selectedComponent={selectedElement}
	onClearSelection={clearElementSelection}
/>
```

**Step 4: 提交**

```bash
git add frontend/src/routes/chat.tsx
git commit -m "feat: integrate visual editing into Chat page"
```

---

## Task 8: 更新 Backend WebSocket 处理带 Context 的消息

**Files:**
- Modify: `backend/api/websocket.py`

**Step 1: 找到 handle_user_suggestion 函数**

搜索处理 `user_suggestion` 消息类型的代码。

**Step 2: 修改处理逻辑支持 context**

```python
async def handle_user_suggestion(sid: str, payload: dict):
    message = payload.get("message", "")
    context = payload.get("context")  # Element selection context

    # Build enhanced message with context
    if context:
        enhanced_message = f"""Modify component: {context['component']}

File: {context['filePath']}

Current code:
```tsx
{context['codeSnippet']}
```

User request: {message}"""
    else:
        enhanced_message = message

    # Pass enhanced_message to AI instead of raw message
    # ... rest of existing logic
```

**Step 3: 添加 element_selected 处理（可选）**

如果需要后端确认：

```python
async def handle_element_selected(sid: str, payload: dict):
    component = payload.get("component")
    file_path = payload.get("filePath")

    # Optionally fetch code from session files
    # Send acknowledgement
    await ws_send(sid, {
        "type": "element_select_ack",
        "component": component,
        "filePath": file_path,
        "codeSnippet": "..."  # Could fetch actual code here
    })
```

**Step 4: 在消息分发中添加处理**

```python
elif msg_type == "element_selected":
    await handle_element_selected(sid, data)
elif msg_type == "user_suggestion":
    await handle_user_suggestion(sid, data)
```

**Step 5: 提交**

```bash
git add backend/api/websocket.py
git commit -m "feat: handle element selection context in WebSocket"
```

---

## Task 9: 验证 TypeScript 编译

**Step 1: 运行类型检查**

```bash
cd frontend
npm run build 2>&1 | head -50
```

**Expected:** No TypeScript errors

**Step 2: 修复任何类型错误**

如果出现错误，根据错误信息修复。

**Step 3: 提交修复**

```bash
git add -A
git commit -m "fix: resolve TypeScript type errors"
```

---

## Task 10: 功能验证清单

### 手动测试步骤：

1. **启动前后端**
   ```bash
   # Terminal 1
   cd frontend && npm run dev

   # Terminal 2
   cd backend && uvicorn main:app --reload
   ```

2. **创建新会话**
   - 访问 http://localhost:5173
   - 输入描述生成一个简单应用

3. **测试编辑模式**
   - 切换到 Preview 标签
   - 点击"编辑模式"按钮
   - 悬停在组件上，确认显示组件名称
   - 点击组件，确认左侧聊天框自动填充

4. **测试 AI 修改**
   - 在填充后的输入框添加修改描述
   - 发送消息
   - 确认 AI 只修改选中的组件
   - 确认预览自动刷新

5. **测试清除选择**
   - 点击组件标签的 X 按钮
   - 确认输入框清空

---

## 总结

实现完成后，用户可以通过以下方式使用：

1. 在 Preview 标签点击"编辑模式"
2. 悬停查看组件名称
3. 点击选中组件
4. 在左侧聊天框输入修改要求
5. AI 只修改该组件并刷新预览

所有修改通过现有 WebSocket 通道传输，无需新增后端节点。
