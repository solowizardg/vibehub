# VibeHub AI SDK Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a conversation-first AI-native app generation platform using Vercel AI SDK

**Architecture:** Next.js 14 App Router with Vercel AI SDK for streaming conversations, edge deployment for real-time preview, Airtable/Notion for user-owned data

**Tech Stack:** Next.js 14, React, TypeScript, Tailwind CSS, Shadcn UI, Vercel AI SDK, Upstash Redis, OpenAI/Anthropic API

---

## Phase 1: Project Setup

### Task 1: Initialize Next.js Project with shadcn

**Files:**
- Create: Entire project structure

**Step 1: Initialize project**

```bash
cd D:\code\github\vibehub\.claude\worktrees\vibehub-ai-sdk
npx shadcn@latest init --yes --template next --base-color slate
```

Expected: Project created with Next.js 14, Tailwind, TypeScript

**Step 2: Configure project**

Modify: `components.json`
```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

**Step 3: Commit**

```bash
git add .
git commit -m "feat: initialize Next.js project with shadcn"
```

---

### Task 2: Install Core Dependencies

**Files:**
- Modify: `package.json`

**Step 1: Install AI SDK and dependencies**

```bash
npm install ai @ai-sdk/openai @ai-sdk/anthropic
npm install @upstash/redis @upstash/ratelimit
npm install airtable notion-client
npm install lucide-react
npm install zod
```

**Step 2: Install shadcn components**

```bash
npx shadcn@latest add button input textarea tabs scroll-area separator avatar badge
```

**Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "feat: add AI SDK and core dependencies"
```

---

### Task 3: Configure Environment Variables

**Files:**
- Create: `.env.local.example`
- Create: `.env.local` (gitignored)

**Step 1: Create environment template**

```bash
cat > .env.local.example << 'EOF'
# AI Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Upstash Redis (for conversation memory)
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...

# Optional: Airtable (for testing)
AIRTABLE_API_KEY=key...
AIRTABLE_BASE_ID=app...

# Optional: GitHub (for deployment features)
GITHUB_TOKEN=ghp_...
EOF
```

**Step 2: Update .gitignore**

```bash
cat >> .gitignore << 'EOF'

# Environment
.env.local
.env.production
EOF
```

**Step 3: Commit**

```bash
git add .env.local.example .gitignore
git commit -m "chore: add environment configuration template"
```

---

## Phase 2: Core AI Chat System

### Task 4: Create AI Client Configuration

**Files:**
- Create: `app/lib/ai/client.ts`

**Step 1: Write implementation**

```typescript
import { createOpenAI } from '@ai-sdk/openai';
import { createAnthropic } from '@ai-sdk/anthropic';

const openai = createOpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const anthropic = createAnthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

export function getModel(provider: 'openai' | 'anthropic' = 'openai') {
  if (provider === 'anthropic') {
    return anthropic('claude-3-sonnet-20240229');
  }
  return openai('gpt-4-turbo-preview');
}

export { openai, anthropic };
```

**Step 2: Commit**

```bash
git add app/lib/ai/client.ts
git commit -m "feat: add AI client configuration"
```

---

### Task 5: Create System Prompt Builder

**Files:**
- Create: `app/lib/ai/prompts.ts`

**Step 1: Write implementation**

```typescript
export interface AppState {
  name?: string;
  stack?: string;
  files?: string[];
  deployed?: boolean;
  url?: string;
}

export interface UserMemory {
  preferences?: string[];
  recentActions?: string[];
}

export function buildSystemPrompt(appState: AppState, memory: UserMemory): string {
  return `You are VibeHub AI, an assistant that helps users create and manage web applications through natural language conversation.

## Current Application State
${appState.name ? `- Name: ${appState.name}` : '- Name: Not yet created'}
${appState.stack ? `- Stack: ${appState.stack}` : '- Stack: Next.js + Tailwind + Airtable (default)'}
${appState.files && appState.files.length > 0 ? `- Files: ${appState.files.join(', ')}` : '- Files: None'}
${appState.deployed ? `- Deployed: ${appState.url}` : '- Deployed: No'}

## Available Tools
1. generateCode - Generate or modify code files
2. deployApp - Deploy the application to Vercel
3. queryData - Query data from Airtable/Notion
4. updateData - Update data records
5. optimizeApp - Automatically optimize the application

## User Preferences
${memory.preferences?.map(p => `- ${p}`).join('\n') || 'No preferences recorded yet'}

## Guidelines
- Always respond conversationally and friendly
- For simple questions, just answer directly
- For code changes, explain what you're doing, then use the generateCode tool
- For data queries, always use the queryData tool, never expose raw SQL
- After making changes, ask if the user is satisfied
- Remember user preferences for future interactions
- If you're unsure about something, ask clarifying questions

## Response Style
- Be concise but helpful
- Use emojis occasionally to keep it friendly
- When generating code, explain the key changes in simple terms`;
}
```

**Step 2: Commit**

```bash
git add app/lib/ai/prompts.ts
git commit -m "feat: add system prompt builder"
```

---

### Task 6: Create Tool Definitions

**Files:**
- Create: `app/lib/ai/tools.ts`

**Step 1: Write implementation**

```typescript
import { z } from 'zod';

export const tools = {
  generateCode: {
    description: 'Generate or modify a code file in the application',
    parameters: z.object({
      path: z.string().describe('The file path, e.g., "app/page.tsx"'),
      content: z.string().describe('The complete file content'),
      language: z.enum(['typescript', 'tsx', 'css', 'json', 'javascript']).describe('The programming language'),
      explanation: z.string().describe('Brief explanation of what this code does'),
    }),
  },

  deployApp: {
    description: 'Deploy the application to Vercel',
    parameters: z.object({
      projectName: z.string().describe('The project name for the deployment'),
      description: z.string().optional().describe('Optional description'),
    }),
  },

  queryData: {
    description: 'Query data from Airtable or Notion',
    parameters: z.object({
      source: z.enum(['airtable', 'notion']).describe('Which data source to query'),
      query: z.string().describe('Natural language description of what to query'),
      tableName: z.string().optional().describe('Specific table/collection name'),
    }),
  },

  updateData: {
    description: 'Update a data record',
    parameters: z.object({
      source: z.enum(['airtable', 'notion']).describe('Which data source'),
      recordId: z.string().describe('The record ID to update'),
      changes: z.string().describe('Natural language description of changes'),
    }),
  },

  optimizeApp: {
    description: 'Automatically optimize the application',
    parameters: z.object({
      type: z.enum(['performance', 'seo', 'accessibility', 'all']).describe('Type of optimization'),
    }),
  },
};

export type ToolName = keyof typeof tools;
```

**Step 2: Commit**

```bash
git add app/lib/ai/tools.ts
git commit -m "feat: add AI tool definitions"
```

---

### Task 7: Create Conversation Memory (Redis)

**Files:**
- Create: `app/lib/memory/redis.ts`

**Step 1: Write implementation**

```typescript
import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: any[];
  createdAt: number;
}

export interface Conversation {
  id: string;
  messages: Message[];
  userId?: string;
  appId?: string;
  createdAt: number;
  updatedAt: number;
}

export async function getConversation(sessionId: string): Promise<Conversation | null> {
  const data = await redis.get<string>(`conversation:${sessionId}`);
  if (!data) return null;
  return JSON.parse(data);
}

export async function saveConversation(sessionId: string, conversation: Conversation): Promise<void> {
  await redis.set(`conversation:${sessionId}`, JSON.stringify(conversation), {
    ex: 60 * 60 * 24 * 7, // 7 days expiry
  });
}

export async function addMessage(sessionId: string, message: Message): Promise<void> {
  const conversation = await getConversation(sessionId);
  if (conversation) {
    conversation.messages.push(message);
    conversation.updatedAt = Date.now();
    await saveConversation(sessionId, conversation);
  } else {
    await saveConversation(sessionId, {
      id: sessionId,
      messages: [message],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
  }
}

export async function getRecentMessages(sessionId: string, limit: number = 20): Promise<Message[]> {
  const conversation = await getConversation(sessionId);
  if (!conversation) return [];
  return conversation.messages.slice(-limit);
}
```

**Step 2: Commit**

```bash
git add app/lib/memory/redis.ts
git commit -m "feat: add Redis conversation memory"
```

---

### Task 8: Create Core Chat API Route

**Files:**
- Create: `app/api/chat/route.ts`

**Step 1: Write implementation**

```typescript
import { StreamingTextResponse, streamText } from 'ai';
import { z } from 'zod';
import { getModel } from '@/app/lib/ai/client';
import { buildSystemPrompt } from '@/app/lib/ai/prompts';
import { tools } from '@/app/lib/ai/tools';
import {
  getConversation,
  saveConversation,
  addMessage,
  type Message
} from '@/app/lib/memory/redis';

export async function POST(req: Request) {
  try {
    const { messages, sessionId = crypto.randomUUID() } = await req.json();

    // Get conversation history
    const conversation = await getConversation(sessionId);
    const history = conversation?.messages || [];

    // Build context (in real app, fetch from DB)
    const appState = {
      name: conversation?.appId ? 'Sample App' : undefined,
      stack: 'Next.js + Tailwind + Airtable',
    };
    const memory = {
      preferences: conversation?.userId ? [] : undefined,
    };

    const systemPrompt = buildSystemPrompt(appState, memory);

    // Combine history with new messages
    const allMessages = [
      { role: 'system', content: systemPrompt },
      ...history.slice(-10), // Last 10 messages for context
      ...messages,
    ];

    const result = await streamText({
      model: getModel('openai'),
      messages: allMessages,
      tools,
      maxTokens: 2000,
      onFinish: async ({ text, toolCalls, toolResults }) => {
        // Save assistant message
        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: text,
          toolCalls: toolCalls || [],
          createdAt: Date.now(),
        };
        await addMessage(sessionId, assistantMessage);

        // Save user message
        const lastUserMessage = messages[messages.length - 1];
        if (lastUserMessage) {
          const userMessage: Message = {
            id: crypto.randomUUID(),
            role: 'user',
            content: lastUserMessage.content,
            createdAt: Date.now(),
          };
          await addMessage(sessionId, userMessage);
        }
      },
    });

    return new StreamingTextResponse(result.toAIStream());

  } catch (error) {
    console.error('Chat API error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
```

**Step 2: Commit**

```bash
git add app/api/chat/route.ts
git commit -m "feat: add core chat API with streaming and tools"
```

---

## Phase 3: Frontend Components

### Task 9: Create Chat Input Component

**Files:**
- Create: `app/components/chat/ChatInput.tsx`

**Step 1: Write implementation**

```typescript
'use client';

import { useState, FormEvent } from 'react';
import { useChat } from 'ai/react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ChatInputProps {
  sessionId?: string;
  onToolCall?: (toolCall: any) => void;
}

export function ChatInput({ sessionId, onToolCall }: ChatInputProps) {
  const [isLoading, setIsLoading] = useState(false);

  const { messages, input, handleInputChange, handleSubmit, isLoading: chatLoading } = useChat({
    api: '/api/chat',
    body: { sessionId },
    onFinish: (message) => {
      setIsLoading(false);
      if (message.toolCalls && onToolCall) {
        message.toolCalls.forEach(onToolCall);
      }
    },
    onError: (error) => {
      console.error('Chat error:', error);
      setIsLoading(false);
    },
  });

  const onSubmit = (e: FormEvent) => {
    setIsLoading(true);
    handleSubmit(e);
  };

  return (
    <div className="border-t bg-background p-4">
      <form onSubmit={onSubmit} className="flex gap-2">
        <Textarea
          value={input}
          onChange={handleInputChange}
          placeholder="Say something like 'Create a flower shop booking website'..."
          className="flex-1 min-h-[60px] max-h-[200px] resize-none"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSubmit(e);
            }
          }}
          disabled={isLoading}
        />
        <Button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="h-auto px-4"
        >
          {isLoading || chatLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add app/components/chat/ChatInput.tsx
git commit -m "feat: add chat input component with streaming"
```

---

### Task 10: Create Message List Component

**Files:**
- Create: `app/components/chat/MessageList.tsx`

**Step 1: Write implementation**

```typescript
'use client';

import { useEffect, useRef } from 'react';
import { User, Bot, Wrench } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: any[];
}

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <ScrollArea className="flex-1 p-4" ref={scrollRef}>
      <div className="space-y-4">
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <div className="animate-pulse">AI is thinking...</div>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}

function MessageItem({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <Avatar className={isUser ? 'bg-primary' : 'bg-muted'}>
        <AvatarFallback>
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div className={`flex-1 space-y-2 ${isUser ? 'text-right' : ''}`}>
        <div
          className={`inline-block rounded-lg px-4 py-2 text-left ${
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted'
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {message.toolCalls.map((tool, idx) => (
              <Badge key={idx} variant="secondary" className="gap-1">
                <Wrench className="h-3 w-3" />
                {tool.function?.name || tool.name}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add app/components/chat/MessageList.tsx
git commit -m "feat: add message list component with auto-scroll"
```

---

### Task 11: Create Chat Sidebar Component

**Files:**
- Create: `app/components/chat/ChatSidebar.tsx`

**Step 1: Write implementation**

```typescript
'use client';

import { useState } from 'react';
import { Plus, MessageSquare, History, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';

interface Conversation {
  id: string;
  title: string;
  updatedAt: Date;
}

interface ChatSidebarProps {
  conversations?: Conversation[];
  currentId?: string;
  onSelect?: (id: string) => void;
  onNew?: () => void;
  onDelete?: (id: string) => void;
}

export function ChatSidebar({
  conversations = [],
  currentId,
  onSelect,
  onNew,
  onDelete
}: ChatSidebarProps) {
  return (
    <div className="flex h-full flex-col bg-muted/50">
      <div className="p-4">
        <Button
          className="w-full justify-start gap-2"
          onClick={onNew}
          variant="outline"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      <Separator />

      <ScrollArea className="flex-1 px-3 py-2">
        <div className="space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center text-sm text-muted-foreground py-4">
              No conversations yet
            </div>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => onSelect?.(conv.id)}
                className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  currentId === conv.id
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-muted'
                }`}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <span className="flex-1 truncate">{conv.title}</span>
                {currentId === conv.id && onDelete && (
                  <Trash2
                    className="h-3 w-3 opacity-0 group-hover:opacity-100 hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(conv.id);
                    }}
                  />
                )}
              </button>
            ))
          )}
        </div>
      </ScrollArea>

      <Separator />

      <div className="p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <History className="h-3 w-3" />
          <span>Conversations saved for 7 days</span>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add app/components/chat/ChatSidebar.tsx
git commit -m "feat: add chat sidebar component"
```

---

### Task 12: Create Preview Frame Component

**Files:**
- Create: `app/components/preview/PreviewFrame.tsx`

**Step 1: Write implementation**

```typescript
'use client';

import { useState } from 'react';
import { Loader2, ExternalLink, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface PreviewFrameProps {
  url?: string;
  isLoading?: boolean;
  onRefresh?: () => void;
}

export function PreviewFrame({ url, isLoading, onRefresh }: PreviewFrameProps) {
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!url) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-muted/50 p-8 text-center">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ExternalLink className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">No Preview Yet</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Start a conversation to create your app. The preview will appear here.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-muted/50">
        <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
        <p className="text-sm text-muted-foreground">Building your app...</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b bg-muted/50 px-4 py-2">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            {url}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            className="gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            Refresh
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <a href={url} target="_blank" rel="noopener noreferrer" className="gap-1">
              <ExternalLink className="h-3 w-3" />
              Open
            </a>
          </Button>
        </div>
      </div>

      {/* Iframe */}
      <div className="flex-1 bg-white">
        {!iframeLoaded && !error && (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {error ? (
          <div className="flex h-full flex-col items-center justify-center p-8 text-center">
            <p className="text-destructive mb-4">Failed to load preview</p>
            <Button onClick={() => { setError(null); setIframeLoaded(false); }}>
              Retry
            </Button>
          </div>
        ) : (
          <iframe
            src={url}
            className="h-full w-full border-0"
            onLoad={() => setIframeLoaded(true)}
            onError={() => setError('Failed to load')}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            allow="accelerometer; camera; encrypted-media; geolocation; gyroscope; microphone; payment"
          />
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add app/components/preview/PreviewFrame.tsx
git commit -m "feat: add preview frame component with loading states"
```

---

### Task 13: Create Main Page Layout

**Files:**
- Create: `app/page.tsx`
- Create: `app/layout.tsx` (update)

**Step 1: Write main page**

```typescript
'use client';

import { useState } from 'react';
import { useChat } from 'ai/react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ChatSidebar } from '@/app/components/chat/ChatSidebar';
import { MessageList } from '@/app/components/chat/MessageList';
import { ChatInput } from '@/app/components/chat/ChatInput';
import { PreviewFrame } from '@/app/components/preview/PreviewFrame';

export default function Home() {
  const [sessionId] = useState(() => crypto.randomUUID());
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [isDeploying, setIsDeploying] = useState(false);

  const { messages, isLoading } = useChat({
    api: '/api/chat',
    body: { sessionId },
  });

  const handleToolCall = (toolCall: any) => {
    const toolName = toolCall.function?.name || toolCall.name;

    if (toolName === 'deployApp' && toolCall.function?.arguments) {
      const args = JSON.parse(toolCall.function.arguments);
      setIsDeploying(true);
      // In real implementation, this would trigger actual deployment
      setTimeout(() => {
        setPreviewUrl(`https://${args.projectName}-demo.vercel.app`);
        setIsDeploying(false);
      }, 2000);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <div className="w-80 border-r">
        <ChatSidebar onNew={() => window.location.reload()} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        <Tabs defaultValue="preview" className="flex-1 flex flex-col">
          <TabsList className="mx-4 mt-4 w-auto justify-start">
            <TabsTrigger value="preview">🖥️ Preview</TabsTrigger>
            <TabsTrigger value="chat">💬 Chat</TabsTrigger>
            <TabsTrigger value="code">📝 Code</TabsTrigger>
          </TabsList>

          <TabsContent value="preview" className="flex-1 m-0 border-0">
            <PreviewFrame
              url={previewUrl}
              isLoading={isDeploying}
            />
          </TabsContent>

          <TabsContent value="chat" className="flex-1 flex flex-col m-0 border-0">
            <MessageList messages={messages} isLoading={isLoading} />
            <ChatInput
              sessionId={sessionId}
              onToolCall={handleToolCall}
            />
          </TabsContent>

          <TabsContent value="code" className="flex-1 m-0 border-0 p-4">
            <div className="h-full rounded-lg bg-muted p-4 font-mono text-sm">
              <p className="text-muted-foreground">Code editor coming soon...</p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
```

**Step 2: Update layout**

```typescript
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'VibeHub AI - Build Apps with Conversation',
  description: 'Create web applications through natural language conversation',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

**Step 3: Commit**

```bash
git add app/page.tsx app/layout.tsx
git commit -m "feat: add main page layout with tabs and chat integration"
```

---

## Phase 4: Integration & Polish

### Task 14: Update Global Styles

**Files:**
- Modify: `app/globals.css`

**Step 1: Add custom styles**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: hsl(var(--muted-foreground) / 0.3);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: hsl(var(--muted-foreground) / 0.5);
}

/* Animations */
@keyframes pulse-subtle {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.animate-pulse-subtle {
  animation: pulse-subtle 2s ease-in-out infinite;
}
```

**Step 2: Commit**

```bash
git add app/globals.css
git commit -m "style: update global styles with custom scrollbar and animations"
```

---

### Task 15: Create README

**Files:**
- Create: `README.md`

**Step 1: Write README**

```markdown
# VibeHub AI SDK

Build web applications through natural language conversation.

## Features

- 🗣️ **Conversation-First**: No complex dashboards, just talk to AI
- 🚀 **Real-time Preview**: See changes instantly as you chat
- 🔧 **Auto-Deployment**: One-click deploy to Vercel
- 💾 **Data Ownership**: Connect your own Airtable/Notion
- 🤖 **Self-Maintaining**: AI automatically optimizes your app

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **AI**: Vercel AI SDK + OpenAI/Anthropic
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: Upstash Redis
- **Deployment**: Vercel

## Getting Started

### Prerequisites

- Node.js 18+
- OpenAI API key
- Upstash Redis account

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/vibehub-ai-sdk.git
cd vibehub-ai-sdk

# Install dependencies
npm install

# Copy environment variables
cp .env.local.example .env.local

# Edit .env.local with your API keys
```

### Environment Variables

```env
OPENAI_API_KEY=sk-...
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...
```

### Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Usage

1. Start a conversation with the AI
2. Describe the app you want to build
3. Watch the preview update in real-time
4. Deploy when satisfied

## Architecture

See [docs/plans/2025-03-01-vibehub-ai-sdk-design.md](docs/plans/2025-03-01-vibehub-ai-sdk-design.md)

## License

MIT
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions"
```

---

## Phase 5: Final Verification

### Task 16: Build Verification

**Step 1: Run build**

```bash
npm run build
```

Expected: Build successful with no errors

**Step 2: Commit final changes**

```bash
git add .
git commit -m "chore: final build verification"
```

---

## Summary

### Completed Features

1. ✅ Next.js 14 project with TypeScript
2. ✅ Vercel AI SDK integration with streaming
3. ✅ Tool calling system (generateCode, deployApp, queryData, etc.)
4. ✅ Redis conversation memory
5. ✅ Chat UI (sidebar, message list, input)
6. ✅ Real-time preview frame
7. ✅ Tabbed interface (Preview/Chat/Code)
8. ✅ shadcn/ui components

### Next Steps (Future Milestones)

- Implement actual code generation tool
- Integrate Vercel deployment API
- Add Airtable/Notion data connectors
- Implement self-optimization features
- Add reinforcement learning feedback

---

**Plan complete. Ready for execution.**
