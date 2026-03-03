# AI 代码生成质量改进

本文档描述 2025-03-02 实施的 AI 代码生成准确性改进方案。

## 问题背景

原始代码生成流程中，TypeScript 错误（如缺少 `cn()` 导入、Framer Motion 类型错误、Next.js 缺少 `"use client"`）只能在沙箱执行阶段被发现，修复代价高且容易无限循环。

## 解决方案

### 1. 多层防御体系

```
┌─────────────────────────────────────────────────────────────────┐
│  第一层：Prompt工程优化（新增）                                  │
│  - 8个 CRITICAL RULES                                            │
│  - 动态 Few-shot 示例注入                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  第二层：生成时静态验证（新增 pre_validation 节点）              │
│  - 快速 TypeScript 检查（不依赖 tsc）                           │
│  - 模板特定规则（Next.js 检查 "use client"）                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  第三层：沙箱执行验证（原有）                                    │
│  - 完整构建测试                                                 │
│  - 自动修复机制                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. 关键文件

| 文件 | 描述 |
|-----|------|
| `backend/agent/nodes/pre_validation.py` | 预验证节点，快速检查 TypeScript 错误 |
| `backend/agent/few_shot_examples.py` | Few-shot 示例库，按模板分类 |
| `backend/agent/prompts.py` | 增强的 Prompt，含 CRITICAL RULES |
| `backend/agent/graph.py` | 更新后的状态机，含重试限制 |

### 3. 无限循环防护

- **每 phase 最大预验证重试**: 2 次 (`MAX_PRE_VALIDATION_ATTEMPTS`)
- **LangGraph 最大递归深度**: 100 步 (`MAX_GRAPH_RECURSION_LIMIT`)

### 4. 模板特定规则

| 规则 | React Vite | Next.js |
|-----|-----------|---------|
| 缺少 `cn()` 导入 | ✅ 检查 | ✅ 检查 |
| Framer Motion 类型错误 | ✅ 检查 | ✅ 检查 |
| 缺少 `"use client"` | ❌ 不检查 | ✅ 检查 |
| 浏览器 API 检查 | ❌ 不检查 | ✅ 检查 |

## 配置说明

### 添加新的验证规则

在 `backend/agent/nodes/pre_validation.py` 中：

1. **通用规则**（所有模板）：添加到 `TS_ERROR_PATTERNS`
2. **模板特定规则**：添加到 `TEMPLATE_SPECIFIC_OVERRIDES[template_name]`

示例：
```python
TS_ERROR_PATTERNS["my_new_rule"] = {
    "pattern": re.compile(r"..."),
    "check_func": lambda content: ...,
    "message": "错误描述",
    "fix_hint": "修复建议",
    "severity": "error",  # or "warning"
}
```

### 添加 Few-shot 示例

在 `backend/agent/few_shot_examples.py` 中：

```python
FEW_SHOT_EXAMPLES["react-vite"]["example_key"] = {
    "description": "示例描述",
    "keywords": ["keyword1", "keyword2"],
    "context": "使用场景",
    "example": "代码示例",
}
```

## 效果评估

| 指标 | 改进前 | 目标 |
|-----|-------|------|
| 每次生成平均错误数 | 2.5个 | 0.8个 |
| 沙箱修复平均轮数 | 1.8轮 | 0.5轮 |
| 构建失败率 | ~15% | ~5% |

## 后续改进方向

1. **代码审查节点** - 使用 LLM 进行生成后代码审查
2. **依赖自动修复** - 自动检测并添加缺失的 npm 依赖
3. **智能重试策略** - 根据错误类型选择不同的修复策略
