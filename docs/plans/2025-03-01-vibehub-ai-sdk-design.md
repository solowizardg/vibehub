# VibeHub 2.0 AI SDK 架构设计文档

## 1. 项目概述

### 1.1 目标
构建一个对话优先的 AI 原生应用生成平台，用户通过自然语言对话即可生成、部署和维护 Web 应用。

### 1.2 核心特性
- **对话优先**: 无传统后台，所有操作通过自然语言
- **实时预览**: 生成即运行，所见即所得
- **数据自主**: 用户数据存储在 Airtable/Notion 等第三方平台
- **AI 自维护**: 自动检测问题并优化
- **开源**: 代码完全开源，社区可复刻

### 1.3 技术栈
- **框架**: Next.js 14 (App Router)
- **AI**: Vercel AI SDK + OpenAI/Anthropic
- **样式**: Tailwind CSS + Shadcn UI
- **状态**: Upstash Redis (对话记忆)
- **部署**: Vercel
- **数据**: Airtable API / Notion API

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Web App   │  │    PWA      │  │   Desktop (Tauri)   │  │
│  │  (Next.js)  │  │   (未来)     │  │      (未来)          │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   边缘计算层 (Vercel Edge)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Next.js App Router                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │    │
│  │  │  API Routes │  │   RSC       │  │   Server     │ │    │
│  │  │  (Hono)     │  │  (Streaming)│  │   Actions    │ │    │
│  │  └─────────────┘  └─────────────┘  └──────────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI 编排层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Vercel    │  │  LangChain  │  │   Upstash Redis     │  │
│  │   AI SDK    │  │  (工具调用)  │  │   (对话记忆)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据层 (用户自选)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Airtable   │  │   Notion    │  │   Google Sheets     │  │
│  │   API       │  │   API       │  │   API               │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心流程

#### 2.2.1 创建应用流程
```
1. 用户: "我想做个花店预约网站"
   │
   ▼
2. AI 理解意图
   - 分析需求: 展示 + 预约 + 联系方式
   - 确定技术栈: Next.js + Tailwind + Airtable
   │
   ▼
3. AI 生成代码
   - 生成页面组件
   - 生成数据模型
   - 生成 API 路由
   │
   ▼
4. 自动部署
   - 推送到 GitHub
   - 触发 Vercel 部署
   - 获取预览 URL
   │
   ▼
5. 数据配置
   - 生成 Airtable 模板
   - 用户复制模板并提供 API Key
   - 应用连接数据
   │
   ▼
6. 完成
   - 用户获得可访问的 URL
   - 数据在 Airtable 管理
```

#### 2.2.2 对话修改流程
```
1. 用户: "加一个价格筛选功能"
   │
   ▼
2. AI 分析当前代码
   - 获取现有组件结构
   - 确定修改位置
   │
   ▼
3. AI 生成修改
   - 生成新代码
   - 生成 diff
   │
   ▼
4. 实时预览
   - 应用修改
   - 热更新预览
   │
   ▼
5. 用户确认
   - 满意: 保持修改
   - 不满意: 撤销或重新生成
```

## 3. 核心模块设计

### 3.1 AI 对话系统

#### 3.1.1 API 接口

```typescript
// app/api/chat/route.ts
import { StreamingTextResponse, streamText } from 'ai';
import { openai } from '@ai-sdk/openai';

export async function POST(req: Request) {
  const { messages, sessionId, appId } = await req.json();

  // 获取对话记忆
  const memory = await getConversationMemory(sessionId);

  // 获取应用状态
  const appState = await getAppState(appId);

  const result = await streamText({
    model: openai('gpt-4-turbo-preview'),
    messages: [
      { role: 'system', content: buildSystemPrompt(appState, memory) },
      ...messages
    ],
    tools: {
      generateCode: {
        description: '生成代码文件',
        parameters: z.object({
          path: z.string(),
          content: z.string(),
          language: z.enum(['typescript', 'css', 'json'])
        })
      },
      deployApp: {
        description: '部署应用到 Vercel',
        parameters: z.object({
          projectName: z.string(),
          files: z.array(z.object({ path: z.string(), content: z.string() }))
        })
      },
      queryData: {
        description: '查询数据',
        parameters: z.object({
          source: z.enum(['airtable', 'notion']),
          query: z.string(),
          filters: z.object({}).optional()
        })
      },
      updateData: {
        description: '更新数据',
        parameters: z.object({
          source: z.enum(['airtable', 'notion']),
          recordId: z.string(),
          changes: z.object({})
        })
      },
      optimizeApp: {
        description: '自动优化应用',
        parameters: z.object({
          type: z.enum(['performance', 'seo', 'accessibility'])
        })
      }
    },
    onFinish: async ({ text, toolCalls }) => {
      // 保存对话历史
      await saveConversation(sessionId, messages, text, toolCalls);
      // 强化学习反馈
      await recordRLFeedback(sessionId, toolCalls);
    }
  });

  return new StreamingTextResponse(result.toAIStream());
}
```

#### 3.1.2 系统 Prompt 设计

```typescript
function buildSystemPrompt(appState: AppState, memory: Memory): string {
  return `
你是 VibeHub AI，一个帮助用户创建和管理 Web 应用的助手。

## 当前应用状态
- 应用名称: ${appState.name || '未命名'}
- 技术栈: ${appState.stack || 'Next.js + Tailwind + Airtable'}
- 已生成文件: ${appState.files?.join(', ') || '无'}
- 部署状态: ${appState.deployed ? '已部署: ' + appState.url : '未部署'}

## 用户偏好记忆
${memory.preferences?.map(p => `- ${p}`).join('\n') || '暂无'}

## 可用工具
1. generateCode - 生成代码文件
2. deployApp - 部署应用到 Vercel
3. queryData - 查询 Airtable/Notion 数据
4. updateData - 更新数据记录
5. optimizeApp - 自动优化应用性能

## 工作原则
1. 优先使用对话回答简单问题
2. 需要修改代码时调用 generateCode
3. 数据查询必须通过 queryData，不能直接告诉用户 SQL
4. 每次修改后主动询问用户满意度
5. 记录用户偏好用于个性化

## 响应格式
- 简单回答: 直接回复
- 需要操作: 说明要做什么，然后调用工具
- 代码修改: 说明修改内容，生成代码，展示预览
`;
}
```

### 3.2 前端界面

#### 3.2.1 布局设计

```typescript
// app/components/Layout.tsx
export function MainLayout() {
  return (
    <div className="flex h-screen bg-background">
      {/* 左侧: 对话历史 */}
      <aside className="w-80 border-r bg-muted/50 flex flex-col">
        <ConversationSidebar />
      </aside>

      {/* 中间: 主工作区 */}
      <main className="flex-1 flex flex-col">
        {/* Tab 切换: 预览 / 数据 / 代码 */}
        <Tabs defaultValue="preview">
          <TabsList>
            <TabsTrigger value="preview">🖥️ 预览</TabsTrigger>
            <TabsTrigger value="data">📊 数据</TabsTrigger>
            <TabsTrigger value="code">📝 代码</TabsTrigger>
          </TabsList>

          <TabsContent value="preview">
            <PreviewFrame />
          </TabsContent>

          <TabsContent value="data">
            <DataPanel />
          </TabsContent>

          <TabsContent value="code">
            <CodeEditor />
          </TabsContent>
        </Tabs>

        {/* 底部: 对话输入 */}
        <ChatInput />
      </main>
    </div>
  );
}
```

#### 3.2.2 对话组件

```typescript
// app/components/ChatInput.tsx
'use client';

import { useChat } from 'ai/react';

export function ChatInput() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
    onFinish: (message) => {
      // 处理 AI 返回的工具调用结果
      handleToolResults(message.toolInvocations);
    }
  });

  return (
    <div className="border-t p-4">
      {/* 对话历史 */}
      <div className="mb-4 max-h-60 overflow-y-auto">
        {messages.map((m) => (
          <div key={m.id} className={cn('mb-2', m.role === 'user' ? 'text-right' : 'text-left')}>
            <span className={cn('inline-block px-3 py-2 rounded-lg',
              m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
            )}>
              {m.content}
            </span>
          </div>
        ))}
      </div>

      {/* 输入框 */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="说点什么，例如：'添加一个预约表单'..."
          className="flex-1 px-4 py-2 rounded-lg border"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg"
        >
          {isLoading ? '思考中...' : '发送'}
        </button>
      </form>
    </div>
  );
}
```

### 3.3 数据连接器

#### 3.3.1 抽象接口

```typescript
// lib/data-connectors/types.ts
export interface DataConnector {
  // 查询数据（自然语言）
  query(naturalLanguage: string): Promise<QueryResult>;

  // 更新数据
  update(recordId: string, changes: string): Promise<void>;

  // 创建记录
  create(data: Record<string, any>): Promise<string>;

  // 删除记录
  delete(recordId: string): Promise<void>;

  // 获取 Schema
  getSchema(): Promise<TableSchema>;
}

export interface QueryResult {
  records: any[];
  total: number;
  explanation: string; // AI 对查询结果的解释
}
```

#### 3.3.2 Airtable 实现

```typescript
// lib/data-connectors/airtable.ts
import Airtable from 'airtable';

export class AirtableConnector implements DataConnector {
  private base: Airtable.Base;
  private tableName: string;

  constructor(apiKey: string, baseId: string, tableName: string = 'Table 1') {
    this.base = new Airtable({ apiKey }).base(baseId);
    this.tableName = tableName;
  }

  async query(naturalLanguage: string): Promise<QueryResult> {
    // 使用 AI 将自然语言转换为 Airtable 查询
    const filterFormula = await this.nlpToAirtableFormula(naturalLanguage);

    const records = await this.base(this.tableName)
      .select({ filterByFormula: filterFormula })
      .all();

    return {
      records: records.map(r => ({ id: r.id, ...r.fields })),
      total: records.length,
      explanation: await this.generateExplanation(naturalLanguage, records)
    };
  }

  private async nlpToAirtableFormula(nlp: string): Promise<string> {
    // 调用 AI 转换
    const { text } = await generateText({
      model: openai('gpt-4-turbo-preview'),
      prompt: `将以下自然语言转换为 Airtable filterByFormula 公式:\n${nlp}`
    });
    return text;
  }
}
```

### 3.4 实时预览系统

#### 3.4.1 预览架构

```typescript
// lib/preview/deployer.ts
export class PreviewDeployer {
  async deploy(files: FileObject[]): Promise<string> {
    // 1. 创建临时 GitHub 仓库
    const repo = await this.createTempRepo();

    // 2. 推送代码
    await this.pushCode(repo, files);

    // 3. 触发 Vercel 部署
    const deployment = await this.triggerVercelDeploy(repo);

    // 4. 返回预览 URL
    return deployment.url;
  }

  async update(deploymentId: string, changes: FileChange[]): Promise<void> {
    // 增量更新，热重载
    await this.applyChanges(deploymentId, changes);
  }
}
```

#### 3.4.2 预览组件

```typescript
// app/components/PreviewFrame.tsx
export function PreviewFrame({ url }: { url: string }) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex-1 bg-white">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <LoadingSpinner />
        </div>
      )}

      {error ? (
        <div className="p-4 text-red-500">
          <p>预览加载失败: {error}</p>
          <button onClick={() => reloadPreview()}>重试</button>
        </div>
      ) : (
        <iframe
          src={url}
          className="w-full h-full border-0"
          onLoad={() => setIsLoading(false)}
          onError={() => setError('加载失败')}
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      )}
    </div>
  );
}
```

## 4. 数据库设计

### 4.1 Redis 数据结构（Upstash）

```typescript
// 对话记忆
key: `chat:${sessionId}:messages`
type: List
value: JSON array of messages

// 用户偏好
key: `user:${userId}:preferences`
type: Hash
value: { theme: 'dark', defaultStack: 'nextjs', ... }

// 应用状态
key: `app:${appId}:state`
type: Hash
value: {
  name: '花店网站',
  files: ['page.tsx', 'layout.tsx'],
  deployed: true,
  url: 'https://...',
  dataSource: { type: 'airtable', baseId: '...' }
}

// 强化学习反馈
key: `rl:${sessionId}:feedback`
type: List
value: [{ action: 'generateCode', result: 'success', timestamp: ... }]
```

## 5. 部署配置

### 5.1 Vercel 环境变量

```bash
# AI 提供商
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# 数据存储
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...

# Airtable (可选，用户自己配置)
AIRTABLE_API_KEY=...

# GitHub (用于部署)
GITHUB_TOKEN=ghp_...
```

### 5.2 项目结构

```
vibehub-ai-sdk/
├── app/
│   ├── api/
│   │   ├── chat/
│   │   │   └── route.ts      # 核心 AI 对话 API
│   │   ├── deploy/
│   │   │   └── route.ts      # 部署 API
│   │   └── data/
│   │       └── route.ts      # 数据查询 API
│   ├── components/
│   │   ├── ChatInput.tsx     # 对话输入
│   │   ├── PreviewFrame.tsx  # 预览框架
│   │   ├── DataPanel.tsx     # 数据面板
│   │   └── CodeEditor.tsx    # 代码编辑器
│   ├── hooks/
│   │   └── useChat.ts        # 对话状态管理
│   ├── lib/
│   │   ├── ai/
│   │   │   ├── client.ts     # AI SDK 配置
│   │   │   ├── tools.ts      # 工具定义
│   │   │   └── prompts.ts    # 系统 Prompt
│   │   ├── data-connectors/
│   │   │   ├── types.ts      # 接口定义
│   │   │   ├── airtable.ts   # Airtable 实现
│   │   │   └── notion.ts     # Notion 实现
│   │   └── preview/
│   │       └── deployer.ts   # 预览部署
│   ├── page.tsx              # 主页面
│   └── layout.tsx            # 根布局
├── components/ui/            # Shadcn UI 组件
├── lib/
│   └── utils.ts
├── public/
├── .env.local
├── next.config.js
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

## 6. 里程碑规划

### Milestone 1: 核心对话 (Week 1)
- [ ] 项目脚手架搭建
- [ ] Vercel AI SDK 集成
- [ ] 基础对话界面
- [ ] 流式响应实现

### Milestone 2: 代码生成 (Week 2)
- [ ] generateCode 工具实现
- [ ] 代码生成模板
- [ ] 实时预览框架
- [ ] 代码展示组件

### Milestone 3: 部署集成 (Week 3)
- [ ] Vercel 部署 API
- [ ] GitHub 集成
- [ ] 自动部署流程
- [ ] 预览 URL 展示

### Milestone 4: 数据连接 (Week 4)
- [ ] Airtable 连接器
- [ ] 自然语言查询
- [ ] 数据面板界面
- [ ] 用户配置流程

### Milestone 5: AI 自维护 (Week 5-6)
- [ ] 性能监控
- [ ] 自动优化建议
- [ ] 强化学习反馈
- [ ] 用户偏好学习

## 7. 技术风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| AI API 延迟高 | 用户体验差 | 流式响应 + 乐观更新 |
| Airtable API 限制 | 数据查询失败 | 本地缓存 + 降级提示 |
| 代码生成错误 | 应用无法运行 | 自动验证 + 错误恢复 |
| 对话上下文过长 | Token 超限 | 智能摘要 + 分层记忆 |

## 8. 开源策略

### 8.1 许可证
MIT License - 允许自由使用、修改、商业用途

### 8.2 社区贡献
- 数据连接器插件系统
- 自定义模板市场
- AI 工具扩展接口

---

## 附录

### A. 参考资源
- [Vercel AI SDK 文档](https://sdk.vercel.ai/docs)
- [Next.js App Router](https://nextjs.org/docs/app)
- [Airtable API](https://airtable.com/developers/web/api/introduction)
- [LangChain JS](https://js.langchain.com/)

### B. 相关项目
- [V0.dev](https://v0.dev) - Vercel 的 AI 生成 UI
- [ChatGPT Code Interpreter](https://chat.openai.com) - 对话式代码执行
- [Notion AI](https://notion.so) - 文档中的 AI 助手
