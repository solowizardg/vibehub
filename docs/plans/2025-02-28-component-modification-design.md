# VibeHub 组件级自然语言修改功能设计文档

**日期**: 2025-02-28
**功能**: 点击选中组件 + AI 自然语言修改
**状态**: 已实现

---

## 1. 背景与目标

### 1.1 问题背景
在 VibeHub 的 AI 代码生成流程中，用户经常需要对已生成的特定组件进行微调，例如：
- "把这个按钮改成红色"
- "在 Header 添加一个 Logo"
- "修改 Footer 的版权文字"

传统的解决方案是重新运行完整的代码生成流水线（LangGraph），这会导致：
1. **效率低下** - 为一个小修改重新生成整个项目
2. **状态丢失** - 用户之前的修改可能被覆盖
3. **成本高** - 消耗更多 LLM Token 和计算资源

### 1.2 设计目标
实现一个**单文件组件修改**功能，允许用户：
1. 在预览界面中**点击选中**任意组件（Hold Alt + Click）
2. 用**自然语言描述**想要的修改
3. 系统仅修改该组件对应的文件，**不触发完整生成流程**
4. 修改后的代码**自动修复缺失的 import**

---

## 2. 架构设计

### 2.1 整体流程

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   用户操作       │     │   前端处理       │     │   后端处理       │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ 1. Hold Alt     │────▶│ 1. postMessage  │────▶│ 1. 接收消息      │
│    + Click      │     │    发送选中信息  │     │    component_   │
│    组件          │     │                 │     │    selected      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
┌─────────────────┐     ┌─────────────────┐            │
│   沙箱更新       │◄────│   文件写入       │◄───────────┤
│                 │     │                 │            │
│ 4. 热更新        │     │ 3. 单文件修改    │            │
│    预览          │     │    (bypass      │            │
│                 │     │     LangGraph)  │            │
└─────────────────┘     └─────────────────┘            │
                                                       │
┌─────────────────┐                                    │
│   用户发送修改   │────────────────────────────────────┘
│   指令          │     2. user_suggestion
│  "改红色"        │        (带 context)
└─────────────────┘
```

### 2.2 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 触发方式 | Alt + Click | 与正常点击导航区分，避免冲突 |
| 通信方式 | postMessage | 沙箱 iframe 与父窗口安全通信 |
| 修改粒度 | 单文件 | 最小化影响范围，避免级联错误 |
| Import 修复 | 后端自动处理 | 不依赖 AI 生成正确 import |
| 代码提取 | 多层回退策略 | 适应 LLM 各种输出格式 |

---

## 3. 核心模块设计

### 3.1 前端：组件选择与通信

**文件**: `frontend/src/components/preview/preview-iframe.tsx`

```typescript
// 初始化 overlay 时启用编辑模式
iframe.contentWindow.postMessage({
  type: 'set_edit_mode',
  enabled: true,
  requireModifierKey: true  // 必须按 Alt 才能选择
}, '*');

// 接收选中事件
window.addEventListener('message', (e) => {
  if (e.data?.type === 'element_selected') {
    onElementSelect?.(e.data);  // { component, filePath, elementId }
  }
});
```

**文件**: `frontend/static/overlay.js`

```javascript
// 只在 Alt 键按下时显示高亮和响应点击
function handleClick(event) {
  if (requireModifierKey && !isModifierKeyPressed) {
    return;  // 允许正常导航行为
  }
  event.preventDefault();
  // 发送选中消息到父窗口
  window.parent.postMessage({
    type: 'element_selected',
    component, filePath, elementId
  }, '*');
}
```

### 3.2 后端：单文件修改处理

**文件**: `backend/api/websocket.py`

核心函数 `_handle_component_modification`:

```python
async def _handle_component_modification(session_id, message, context):
    """
    处理单文件组件修改，bypass LangGraph 流水线
    """
    # 1. 构建针对性 prompt
    prompt = f"""
    Component: {component}
    File: {file_path}
    Current code: {current_code}
    User request: {message}
    """

    # 2. 调用 LLM (轻量级模型，temperature 0.2)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    response = await llm.ainvoke(prompt)

    # 3. 多层策略提取代码
    new_content = _extract_code_from_response(response.content, file_path)

    # 4. 自动修复缺失 import
    new_content = _fix_missing_imports(new_content, file_path)

    # 5. 写入数据库和沙箱
    await upsert_file(db, session_id, file_path, new_content)
    await sandbox_manager.write_files(session_id, {file_path: new_content})
```

### 3.3 代码提取：多层回退策略

**函数**: `_extract_code_from_response`

| 策略 | 匹配模式 | 适用场景 |
|------|---------|---------|
| 1. 标准格式 | `===FILE: path===...===END_FILE===` | AI 按指令格式输出 |
| 2. 通用文件 | `===FILE: (any)===...===END_FILE===` | AI 使用不同路径 |
| 3. Markdown | \`\`\`tsx\n...\`\`\` | AI 使用代码块 |
| 4. 启发式 | 包含 export/import/function 的代码块 | AI 只输出代码 |
| 5. 原始代码 | 以 import/export 开头 | AI 直接输出代码 |

**代码清理**: `_clean_code_content`

- 移除中文解释性文字（"这里是...", "修改后的..."）
- 移除英文解释（"Here is...", "This is..."）
- 使用单词边界 `\b` 避免误匹配合法代码

### 3.4 Import 自动修复

**函数**: `_fix_missing_imports`

**检测逻辑**:
1. **解析现有 import** - 提取已导入的名称
2. **扫描 JSX 组件** - `<ComponentName>` → 大写字母开头
3. **扫描 hooks** - `useSomething(` → use 前缀
4. **扫描工具函数** - `cn(...)`, `cva(...)`

**映射表**:

```python
LUCIDE_ICONS = {'Cpu', 'Menu', 'X', ...}  # 70+ 图标
NEXTJS_IMPORTS = {
    'Link': 'next/link',
    'Image': 'next/image',
    'useRouter': 'next/navigation',
}
REACT_IMPORTS = {'useState', 'useEffect', ...}
UTILITY_FUNCTIONS = {
    'cn': '@/lib/utils',
    'cva': 'class-variance-authority',
}
```

**生成规则**:
- 相同来源的导入合并: `import { A, B } from 'lucide-react'`
- 按来源分组: React、lucide-react、next/* 分开
- 保持字母顺序: 便于阅读

---

## 4. 健壮性考虑

### 4.1 已处理的边界情况

| 场景 | 处理方案 |
|------|---------|
| LLM 输出格式混乱 | 5 层回退策略提取代码 |
| LLM 忘记写 import | 后端自动检测并添加 |
| 图标与组件同名 | `UTILITY_FUNCTIONS` 与 `LUCIDE_ICONS` 分离 |
| 用户按错键 | Alt 修饰键避免误触发 |
| 代码中包含中文注释 | 使用单词边界避免误清理 |

### 4.2 局限性

1. **用户自定义组件冲突** - 如果用户定义了 `Menu` 组件，会被误认为 lucide 图标
2. **复杂类型导入** - `import type { ... }` 和 `import * as` 处理不完善
3. **动态组件** - `const Icon = dynamic(() => import(...))` 无法检测

### 4.3 未来改进

- 使用 AST (如 `@babel/parser`) 替代正则，更精准分析代码
- 添加用户自定义 import 映射配置
- 支持多文件同时修改（如组件 + 样式文件）

---

## 5. 测试验证

### 5.1 功能测试用例

| 用例 | 输入 | 预期结果 |
|------|------|---------|
| 修改按钮颜色 | 选中 Button，输入"改成红色" | 仅 Button.tsx 修改，添加 bg-red-500 |
| 添加图标 | 选中 Header，输入"添加 Menu 图标" | 自动添加 `import { Menu } from 'lucide-react'` |
| 使用 hooks | 输入"添加 useState" | 自动添加 `import { useState } from 'react'` |
| 代码污染 | LLM 返回 "Here is the code: \`\`\`tsx\n..." | 成功提取代码，无解释文字 |

### 5.2 性能指标

| 指标 | 完整生成 | 单文件修改 | 提升 |
|------|---------|-----------|------|
| 响应时间 | 30-60s | 3-8s | 5-10x |
| Token 消耗 | 高（多轮对话） | 低（单次调用） | ~10x |
| 文件变更数 | 多个文件 | 单个文件 | 精准控制 |

---

## 6. 相关文件

**后端**:
- `backend/api/websocket.py` - WebSocket 处理、单文件修改逻辑
- `backend/agent/nodes/sandbox_execution.py` - TypeCheck 命令修复

**前端**:
- `frontend/src/components/preview/preview-iframe.tsx` - Iframe 通信
- `frontend/src/components/preview/page-navigator.tsx` - 页面切换
- `frontend/static/overlay.js` - 组件选择高亮

**模板**:
- `e2b-templates/nextjs/` - Next.js 项目模板

---

## 7. 总结

本功能通过**点击选择 + 自然语言 + 单文件修改**的组合，为用户提供了一种快速、精准的 AI 代码编辑方式。核心创新点：

1. **Bypass LangGraph** - 直接调用 LLM，无需完整流水线
2. **多层代码提取** - 适应各种 LLM 输出格式
3. **自动 import 修复** - 后端代码级修复，不依赖 AI

这显著提升了用户体验，使得微调 AI 生成的代码变得像聊天一样简单。
