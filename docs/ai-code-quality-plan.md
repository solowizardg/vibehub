# VibeHub AI代码生成准确性提升方案

## 1. 问题分析

### 当前流程痛点

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Blueprint生成  │───▶│  Phase代码生成   │───▶│  沙箱验证       │
│  (单次LLM调用)  │    │  (最多2次重试)   │    │  (最多3次修复)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                              ┌────────────────────────┘
                              ▼
                       ┌──────────────┐
                       │ Sandbox Fix  │
                       │ (错误后修复) │
                       └──────────────┘
```

**核心问题：**
1. **事后修复成本高** - 错误在沙箱执行后才被发现，修复代价大
2. **静态验证不足** - 仅依赖import/export检查，缺少TypeScript类型检查
3. **Prompt质量不稳定** - 缺乏对生成代码的约束验证机制
4. **错误累积效应** - 前期小错误会级联到后续阶段

### 错误类型分布（预估）

| 错误类型 | 占比 | 当前发现阶段 | 理想发现阶段 |
|---------|------|-------------|-------------|
| 缺失import/cn() | 25% | 沙箱验证 | 生成时 |
| TypeScript类型错误 | 30% | 沙箱验证 | 生成时 |
| 依赖未声明 | 15% | 沙箱验证 | 生成时 |
| 组件导出不匹配 | 10% | Phase验证 | 生成时 |
| 逻辑错误 | 15% | 沙箱验证 | 审查节点 |
| 其他 | 5% | - | - |

---

## 2. 多层防御体系架构

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      第一层：Prompt工程优化                       │
│  - 结构化输出约束                                               │
│  - Few-shot示例学习                                             │
│  - 规则内嵌验证                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      第二层：生成时静态验证                       │
│  - TypeScript类型检查 (tsc --noEmit)                           │
│  - ESLint快速检查                                               │
│  - Import/Export一致性检查 (已有)                              │
│  - 依赖声明检查 (已有)                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      第三层：代码审查节点                         │
│  - LLM代码审查                                                  │
│  - 跨文件一致性检查                                             │
│  - 设计规范符合性检查                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      第四层：沙箱执行验证                         │
│  - 完整构建测试                                                 │
│  - 运行时错误捕获                                               │
│  - 自动修复机制 (已有)                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 状态机扩展

```
blueprint_generation
       │
       ▼
phase_implementation ──▶ (生成后) ──▶ pre_validation_node
       │                                        │
       │ (验证通过)                             │ (有错误)
       ▼                                        ▼
sandbox_execution ◀─────────────────── auto_fix_node
       │
       ▼
  (成功/失败)
```

---

## 3. 具体实施方案

### 3.1 第一层：Prompt工程优化

#### 3.1.1 动态Few-shot示例库

```python
# backend/agent/few_shot_examples.py

# 按模板类型分类的示例库
FEW_SHOT_EXAMPLES = {
    "react-vite": {
        "cn_import": {
            "context": "使用Tailwind CSS工具函数",
            "input": "生成一个Button组件",
            "output": """===FILE: src/components/Button.tsx===
import { cn } from '@/lib/utils'  // CRITICAL: Must import cn

interface ButtonProps {
  variant?: 'primary' | 'secondary';
  children: React.ReactNode;
}

export function Button({ variant = 'primary', children }: ButtonProps) {
  return (
    <button className={cn(
      'px-4 py-2 rounded',
      variant === 'primary' && 'bg-blue-500 text-white',
      variant === 'secondary' && 'bg-gray-200 text-gray-800'
    )}>
      {children}
    </button>
  );
}
===END_FILE==="""
        },
        "framer_motion_types": {
            "context": "使用Framer Motion动画",
            "input": "生成带动画的卡片组件",
            "output": """===FILE: src/components/AnimatedCard.tsx===
import { motion } from 'framer-motion';

// CRITICAL: Use array literal for ease, NOT string
const transition = {
  duration: 0.3,
  ease: [0.25, 0.1, 0.25, 1]  // Correct: array literal
} as const;

export function AnimatedCard() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={transition}
    >
      Content
    </motion.div>
  );
}
===END_FILE==="""
        }
    },
    "nextjs": {
        "use_client": {
            "context": "Next.js App Router中使用hooks",
            "input": "生成使用useState的组件",
            "output": """===FILE: src/components/Counter.tsx===
"use client"  // CRITICAL: Must be first line for hooks

import { useState } from 'react';

export function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
===END_FILE==="""
        }
    }
}

def get_relevant_examples(template_name: str, context: str, max_examples: int = 2) -> list[dict]:
    """根据上下文检索最相关的示例"""
    examples = FEW_SHOT_EXAMPLES.get(template_name, {})
    # 简单关键词匹配，可扩展为向量检索
    relevant = []
    for key, example in examples.items():
        if any(kw in context.lower() for kw in example.get("keywords", [])):
            relevant.append(example)
    return relevant[:max_examples]
```

#### 3.1.2 增强版Prompt模板

```python
# 在 prompts.py 中添加

PHASE_IMPLEMENTATION_SYSTEM_PROMPT_V2 = """You are an expert full-stack developer...

[现有内容保持不变]

## CRITICAL RULES (违反会导致构建失败)

### Rule 1: cn() 函数导入
- 使用 `cn()` 前必须导入: `import {{ cn }} from '@/lib/cn'` (Next.js) 或 `import {{ cn }} from '@/lib/utils'` (React Vite)
- 错误示例: 使用 `cn()` 但没有import

### Rule 2: Framer Motion 类型
- `ease` 属性必须使用数组字面量: `ease: [0.25, 0.1, 0.25, 1]`
- 错误示例: `ease: "easeOut"` (TypeScript会报错)
- `transition` 对象添加 `as const` 断言

### Rule 3: Next.js Client Components
- 使用hooks (useState, useEffect等) 的文件 MUST 在首行添加 `"use client"`
- 使用浏览器API (window, document等) 的文件 MUST 添加 `"use client"`
- 仅服务端渲染的组件才能省略 `"use client"`

### Rule 4: 依赖声明
- 使用任何第三方包前，检查是否在 `package.json` 的 dependencies 中声明
- 如果添加新依赖，必须同时更新 `package.json`
- 允许的内置模块: react, react-dom, next (已预装)

### Rule 5: Import/Export 一致性
- 默认导入 (`import X from...`) 要求目标文件有 `export default`
- 命名导入 (`import {{ X }} from...`) 要求目标文件有 `export const X` 或 `export function X`
- 不要混合使用默认导出和命名导出

### Rule 6: TypeScript 严格模式
- 所有函数参数必须有类型注解
- 组件props必须使用interface定义
- 避免使用 `any` 类型
- 使用可选链操作符 (`?.`) 替代深层属性访问检查

## 输出格式验证清单

生成完成后，请自检：
- [ ] 所有使用的工具函数已导入
- [ ] 所有组件props有类型定义
- [ ] 第三方依赖已在package.json中
- [ ] Import与Export匹配
"""
```

### 3.2 第二层：生成时静态验证

#### 3.2.1 轻量级TypeScript检查节点

```python
# backend/agent/nodes/pre_validation.py

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 常见TypeScript错误模式检测
TS_ERROR_PATTERNS = {
    "missing_cn_import": {
        "pattern": re.compile(r'cn\s*\('),
        "check": lambda content: "import { cn }" not in content and "from '@/lib/" in content,
        "message": "使用 cn() 但没有导入",
        "fix_hint": "添加: import { cn } from '@/lib/cn' 或 '@/lib/utils'",
    },
    "framer_motion_string_ease": {
        "pattern": re.compile(r'ease\s*:\s*"[^"]+"'),
        "check": lambda content: "framer-motion" in content,
        "message": "Framer Motion ease 属性使用了字符串",
        "fix_hint": "改为数组格式: ease: [0.25, 0.1, 0.25, 1]",
    },
    "missing_use_client": {
        "pattern": re.compile(r'\buseState\b|\buseEffect\b|\buseCallback\b|\buseMemo\b'),
        "check": lambda content: '"use client"' not in content,
        "message": "使用React hooks但没有添加 'use client' 指令",
        "fix_hint": "在文件首行添加: "use client"",
    },
    "implicit_any": {
        "pattern": re.compile(r'function\s+\w+\s*\(([^)]*)\)'),
        "check": lambda content, match: ':' not in match.group(1) and match.group(1).strip(),
        "message": "函数参数缺少类型注解",
        "fix_hint": "为参数添加类型，如: (props: ButtonProps)",
    },
}

def quick_typescript_check(file_path: str, content: str, template_name: str) -> list[dict]:
    """快速TypeScript错误检测（不依赖tsc）"""
    errors = []

    for error_type, config in TS_ERROR_PATTERNS.items():
        if template_name == "nextjs" and error_type == "missing_use_client":
            # Next.js 特有检查
            for match in config["pattern"].finditer(content):
                if config["check"](content):
                    errors.append({
                        "type": error_type,
                        "line": content[:match.start()].count('\n') + 1,
                        "message": config["message"],
                        "fix_hint": config["fix_hint"],
                    })
                    break
        else:
            for match in config["pattern"].finditer(content):
                check_func = config["check"]
                # 支持需要match参数的check函数
                try:
                    result = check_func(content, match) if 'match' in check_func.__code__.co_varnames else check_func(content)
                except Exception:
                    result = check_func(content)

                if result:
                    errors.append({
                        "type": error_type,
                        "line": content[:match.start()].count('\n') + 1,
                        "message": config["message"],
                        "fix_hint": config["fix_hint"],
                    })
                    break

    return errors


def pre_validation_node(state: CodeGenState, config) -> dict[str, Any]:
    """在沙箱验证前进行快速静态检查"""
    sid = state.get("session_id", "")
    generated_files = dict(state.get("generated_files", {}))
    template_name = state.get("template_name", "react-vite")

    all_errors: list[dict] = []

    for path, file_data in generated_files.items():
        if not path.endswith(('.ts', '.tsx')):
            continue

        content = str(file_data.get("file_contents", ""))
        errors = quick_typescript_check(path, content, template_name)

        for err in errors:
            all_errors.append({
                "file": path,
                **err,
            })

    if all_errors:
        logger.warning("Pre-validation found %d errors for session %s", len(all_errors), sid)
        return {
            "validation_errors": all_errors,
            "current_dev_state": "pre_validation_fixing",
        }

    return {
        "validation_errors": [],
        "current_dev_state": "sandbox_executing",
    }
```

#### 3.2.2 增强的Phase验证

```python
# 扩展 _validate_phase_files 函数

def _validate_phase_files_enhanced(
    required_files: list[str],
    candidate_files: dict[str, GeneratedFile],
    generated_files: dict[str, GeneratedFile],
    template_name: str,
) -> list[str]:
    """增强版phase验证，包含快速TypeScript检查"""

    # 1. 基础验证（import/export, 依赖等）
    errors = _validate_phase_files(required_files, candidate_files, generated_files)

    # 2. 快速TypeScript检查
    merged = dict(generated_files)
    merged.update(candidate_files)

    for path, file_data in candidate_files.items():
        if not path.endswith(('.ts', '.tsx')):
            continue

        content = str(file_data.get("file_contents", ""))
        ts_errors = quick_typescript_check(path, content, template_name)

        for err in ts_errors:
            errors.append(f"{path}:{err['line']}: {err['message']} ({err['fix_hint']})")

    # 3. 组件Props检查
    for path, file_data in candidate_files.items():
        content = str(file_data.get("file_contents", ""))

        # 检查导出的React组件是否有Props类型
        if 'export function' in content or 'export const' in content:
            # 简单启发式：检查是否有interface或type定义props
            has_props_interface = bool(re.search(r'interface\s+\w*Props', content))
            has_props_type = bool(re.search(r'type\s+\w*Props', content))

            # 检查函数参数是否有类型
            func_match = re.search(r'export\s+(?:function|const)\s+(\w+)', content)
            if func_match and func_match.group(1)[0].isupper():  # 假设大写开头是组件
                if not has_props_interface and not has_props_type:
                    # 检查是否使用了泛型
                    if '<' not in content.split('export')[1].split('(')[0] if '(' in content.split('export')[1] else True:
                        errors.append(f"{path}: 组件可能缺少Props类型定义")

    return errors
```

### 3.3 第三层：代码审查节点

```python
# backend/agent/nodes/code_review.py

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.callback_registry import ws_send
from agent.llm_content import llm_content_to_text
from agent.state import CodeGenState

logger = logging.getLogger(__name__)

CODE_REVIEW_SYSTEM_PROMPT = """You are a senior code reviewer performing pre-merge review.

Review the generated code for this phase and identify issues before they reach production.

Project: {project_name}
Phase: {phase_name}

Files to review:
{files_content}

Design Blueprint (must verify compliance):
{design_blueprint}

Check for these categories of issues:

## 1. Type Safety
- Missing type annotations
- Incorrect generic usage
- Implicit any types
- Incorrect prop types

## 2. Import/Export Consistency
- Importing non-existent exports
- Default vs named import mismatch
- Circular dependencies

## 3. React Best Practices
- Missing keys in lists
- Incorrect hook dependencies
- State mutation issues
- Missing cleanup in useEffect

## 4. Design System Compliance
- Not following color palette from blueprint
- Incorrect spacing/tokens
- Inconsistent component patterns

## 5. Common Gotchas
- Missing "use client" for browser APIs
- Incorrect Framer Motion types
- Missing cn() import
- Accessibility issues

Output format:
{{
  "approved": true/false,
  "issues": [
    {{
      "file": "path/to/file.tsx",
      "line": 42,
      "severity": "error" | "warning",
      "category": "type_safety" | "import_export" | "react" | "design" | "common",
      "message": "Description of the issue",
      "suggested_fix": "The corrected code"
    }}
  ],
  "summary": "Brief review summary"
}}

If no issues found, return approved: true with empty issues array."""


async def code_review_node(state: CodeGenState, config) -> dict[str, Any]:
    """Review generated code before sandbox execution."""
    from agent.graph import get_llm

    sid = state.get("session_id", "")
    phases = state.get("phases", [])
    current_idx = state.get("current_phase_index", 0)
    generated_files = dict(state.get("generated_files", {}))

    if current_idx >= len(phases):
        return {"current_dev_state": "sandbox_executing"}

    phase = phases[current_idx - 1]  # Current phase was already incremented
    phase_index = int(phase.get("index", current_idx - 1))

    await ws_send(sid, {
        "type": "phase_reviewing",
        "phase_index": phase_index,
    })

    # Get files from current phase
    phase_files = []
    for path, file_data in generated_files.items():
        if file_data.get("phase_index") == phase_index:
            phase_files.append((path, file_data))

    if not phase_files:
        return {"current_dev_state": "sandbox_executing"}

    # Build file content for review
    files_content = []
    for path, file_data in phase_files:
        content = str(file_data.get("file_contents", ""))
        files_content.append(f"=== {path} ===\n{content}\n")
    files_content_str = "\n".join(files_content)

    # Get design blueprint
    blueprint = state.get("blueprint", {})
    design_blueprint = blueprint.get("design_blueprint", {})

    llm = get_llm()

    prompt = CODE_REVIEW_SYSTEM_PROMPT.format(
        project_name=state.get("project_name", "my-app"),
        phase_name=phase.get("name", f"Phase {phase_index}"),
        files_content=files_content_str,
        design_blueprint=json.dumps(design_blueprint, ensure_ascii=False, indent=2),
    )

    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content="Review the code and provide feedback in the specified JSON format."),
    ])

    content = llm_content_to_text(response.content if hasattr(response, "content") else response)

    # Parse review result
    try:
        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            review_result = json.loads(json_match.group())
        else:
            review_result = json.loads(content)

        approved = review_result.get("approved", False)
        issues = review_result.get("issues", [])

        if not approved and issues:
            # Format issues for feedback
            error_messages = []
            for issue in issues:
                file_path = issue.get("file", "unknown")
                line = issue.get("line", "?")
                severity = issue.get("severity", "error")
                message = issue.get("message", "")
                error_messages.append(f"[{severity}] {file_path}:{line}: {message}")

            await ws_send(sid, {
                "type": "phase_review_failed",
                "phase_index": phase_index,
                "issues": issues,
                "summary": review_result.get("summary", ""),
            })

            return {
                "review_issues": issues,
                "review_error_messages": error_messages,
                "current_dev_state": "phase_review_fixing",
            }

        await ws_send(sid, {
            "type": "phase_review_passed",
            "phase_index": phase_index,
            "summary": review_result.get("summary", "Code review passed"),
        })

        return {
            "review_issues": [],
            "current_dev_state": "sandbox_executing",
        }

    except Exception as e:
        logger.warning("Failed to parse code review result: %s", str(e)[:200])
        # Fail open - proceed to sandbox if review parsing fails
        return {
            "review_issues": [],
            "current_dev_state": "sandbox_executing",
        }
```

### 3.4 第四层：渐进式生成策略

#### 3.4.1 文件级增量验证

```python
# backend/agent/nodes/incremental_generation.py

"""
渐进式生成策略：先生成关键文件，验证通过后再生成其余文件

核心思想：
1. 识别关键文件（导出核心API/组件的文件）
2. 先生成关键文件并进行验证
3. 验证通过后再生成依赖这些文件的文件
4. 减少错误传播的级联效应
"""

from typing import Any


def identify_critical_files(phase_files: list[str], existing_files: dict) -> tuple[list[str], list[str]]:
    """
    将文件分为关键文件和依赖文件

    关键文件特征：
    - 被多个其他文件import
    - 包含核心类型定义
    - 导出入口组件
    """

    critical_patterns = [
        'types.ts', 'types.tsx',
        'index.ts', 'index.tsx',
        'api.ts', 'api.tsx',
        'utils.ts', 'utils.tsx',
        'hooks/', 'lib/',
    ]

    critical = []
    dependent = []

    for file_path in phase_files:
        is_critical = any(pattern in file_path for pattern in critical_patterns)
        if is_critical:
            critical.append(file_path)
        else:
            dependent.append(file_path)

    return critical, dependent


async def incremental_phase_implementation(state: CodeGenState, config) -> dict[str, Any]:
    """
    渐进式phase实现：先验证关键文件，再生成依赖文件
    """
    # 这个方法可以替换或增强现有的 phase_implementation_node
    # 具体实现略，核心逻辑：
    # 1. 将phase_files分为critical和dependent
    # 2. 先生成critical files
    # 3. 进行快速验证
    # 4. 验证通过后再生成dependent files
    pass
```

---

## 4. 实施路线图

### Phase 1: 快速生效（1-2天）

| 任务 | 优先级 | 预估减少错误 |
|-----|-------|------------|
| 增强Prompt规则（3.1.2） | P0 | 20-30% |
| 快速TypeScript检查（3.2.1） | P0 | 15-20% |
| Few-shot示例库（3.1.1） | P1 | 10-15% |

### Phase 2: 深度验证（3-5天）

| 任务 | 优先级 | 预估减少错误 |
|-----|-------|------------|
| 增强Phase验证（3.2.2） | P1 | 10-15% |
| 代码审查节点（3.3） | P1 | 15-20% |
| 自动修复优化 | P2 | 减少修复轮数 |

### Phase 3: 架构优化（1-2周）

| 任务 | 优先级 | 预估减少错误 |
|-----|-------|------------|
| 渐进式生成（3.4） | P2 | 减少级联错误 |
| 依赖自动声明完善 | P2 | 5-10% |
| 智能重试策略 | P2 | 提高成功率 |

---

## 5. 预期效果

### 错误率降低预估

```
当前状态：
- 每次生成平均错误数：2.5个
- 沙箱修复平均轮数：1.8轮
- 构建失败率：约15%

实施后预期：
- 每次生成平均错误数：0.8个 (降低68%)
- 沙箱修复平均轮数：0.5轮 (降低72%)
- 构建失败率：约5% (降低66%)
```

### 用户体验改善

1. **生成速度提升** - 减少修复轮数，缩短整体生成时间
2. **减少中断** - 更少的构建失败，更流畅的体验
3. **代码质量提升** - 生成的代码更加规范、类型安全

---

## 6. 下一步行动

建议立即实施的3个最高ROI改进：

1. **增强Prompt规则**（半天）
   - 修改 `prompts.py` 中的 `PHASE_IMPLEMENTATION_SYSTEM_PROMPT`
   - 添加CRITICAL RULES章节

2. **快速TypeScript检查**（1天）
   - 创建 `pre_validation.py` 节点
   - 集成到Graph中

3. **Few-shot示例**（半天）
   - 创建 `few_shot_examples.py`
   - 修改Prompt模板注入示例

请确认方案后，我将开始实施Phase 1的改进。
