"""Few-shot examples library for code generation quality improvement.

This module provides correct code examples that are dynamically injected into prompts
to guide the LLM toward generating error-free code.
"""

from typing import Any

# Few-shot examples organized by template type and common pattern
FEW_SHOT_EXAMPLES: dict[str, dict[str, dict[str, Any]]] = {
    "react-vite": {
        "cn_import_usage": {
            "description": "Correct cn() utility import and usage",
            "keywords": ["cn", "tailwind", "className", "utility"],
            "context": "When using Tailwind CSS class merging with cn()",
            "example": '''===FILE: src/components/Button.tsx===
import { cn } from '@/lib/utils'  // CRITICAL: Must import cn before using

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  onClick,
}: ButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        // Base styles
        'inline-flex items-center justify-center rounded-md font-medium',
        'transition-colors focus-visible:outline-none focus-visible:ring-2',
        // Variant styles
        variant === 'primary' && 'bg-blue-600 text-white hover:bg-blue-700',
        variant === 'secondary' && 'bg-gray-100 text-gray-900 hover:bg-gray-200',
        variant === 'ghost' && 'hover:bg-gray-100',
        // Size styles
        size === 'sm' && 'h-8 px-3 text-sm',
        size === 'md' && 'h-10 px-4 text-base',
        size === 'lg' && 'h-12 px-6 text-lg',
        // Allow external className override
        className,
      )}
      data-vibehub-component="Button"
      data-vibehub-file="src/components/Button.tsx"
    >
      {children}
    </button>
  );
}
===END_FILE===''',
        },
        "framer_motion_types": {
            "description": "Correct Framer Motion transition typing",
            "keywords": ["framer-motion", "motion", "animation", "transition", "ease"],
            "context": "When using Framer Motion for animations",
            "example": '''===FILE: src/components/AnimatedCard.tsx===
import { motion } from 'framer-motion';

interface AnimatedCardProps {
  children: React.ReactNode;
  delay?: number;
}

// CRITICAL: Use array literals for ease, NEVER strings
// Use 'as const' for type safety
const transitionConfig = {
  duration: 0.3,
  ease: [0.25, 0.1, 0.25, 1],  // CORRECT: array literal for easeOut
} as const;

const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      ...transitionConfig,
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      duration: 0.2,
      ease: [0.25, 0.1, 0.25, 1],  // CORRECT: array literal
    },
  },
};

export function AnimatedCard({ children, delay = 0 }: AnimatedCardProps) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      transition={{ delay }}  // Additional delay prop works fine
      data-vibehub-component="AnimatedCard"
      data-vibehub-file="src/components/AnimatedCard.tsx"
    >
      {children}
    </motion.div>
  );
}
===END_FILE===''',
        },
        "framer_motion_jsx_syntax": {
            "description": "Correct Framer Motion JSX syntax and import",
            "keywords": ["framer-motion", "motion", "jsx", "syntax", "import"],
            "context": "When using Framer Motion components in JSX",
            "example": '''===FILE: src/components/MotionDemo.tsx===
import { motion } from 'framer-motion';  // CRITICAL: Must import motion

interface MotionDemoProps {
  title: string;
}

export function MotionDemo({ title }: MotionDemoProps) {
  return (
    <div>
      {/* CORRECT: Use <motion.div> with proper import */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        data-vibehub-component="MotionDemo"
        data-vibehub-file="src/components/MotionDemo.tsx"
      >
        <h1>{title}</h1>
      </motion.div>

      {/* CORRECT: Other motion elements */}
      <motion.span
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.2 }}
      >
        Animated text
      </motion.span>

      {/* CORRECT: motion.button with hover animation */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        transition={{ duration: 0.1 }}
      >
        Click me
      </motion.button>
    </div>
  );
}

// WRONG EXAMPLES - DO NOT USE:
// <motion.div> without import { motion } from 'framer-motion'
// <div.div> - invalid double dot
// <.div> - invalid leading dot
// <motion.> - incomplete tag
===END_FILE===''',
        },
        "jsx_syntax_rules": {
            "description": "JSX tag syntax rules and common mistakes",
            "keywords": ["jsx", "syntax", "tag", "component", "html"],
            "context": "When writing JSX tags in React components",
            "example": '''===FILE: src/components/JsxDemo.tsx===
import { Card } from './Card';  // Custom component import

interface JsxDemoProps {
  showCard?: boolean;
}

export function JsxDemo({ showCard }: JsxDemoProps) {
  return (
    <div>
      {/* CORRECT: Standard HTML elements */}
      <div className="container">
        <span>Text</span>
        <input type="text" />
        <img src="/logo.png" alt="Logo" />
      </div>

      {/* CORRECT: Custom components (PascalCase, imported) */}
      {showCard && <Card title="Hello" />}

      {/* CORRECT: Self-closing tags */}
      <br />
      <hr />
      <input type="checkbox" />

      {/* CORRECT: Framer Motion (imported from framer-motion) */}
      {/* <motion.div>...</motion.div> */}

      {/* WRONG - DO NOT USE:

      // Invalid: double dot notation
      <div.div>content</div.div>

      // Invalid: leading dot
      <.div>content</.div>

      // Invalid: incomplete motion tag
      <motion.>content</motion.>

      // Invalid: motion without import
      <motion.div>content</motion.div>  // without import { motion }

      // Invalid: lowercase custom component (React treats as HTML)
      <myComponent />  // Should be <MyComponent />

      // Invalid: unclosed tag
      <div>content    // Missing </div>

      // Invalid: mismatched tags
      <div><span>content</div></span>  // Wrong nesting
      */}
    </div>
  );
}
===END_FILE===''',
        },
        "component_with_hooks": {
            "description": "Correct component with React hooks",
            "keywords": ["useState", "useEffect", "useCallback", "hooks"],
            "context": "When using React hooks in Vite React",
            "example": '''===FILE: src/components/Counter.tsx===
import { useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';

interface CounterProps {
  initialValue?: number;
  step?: number;
  onChange?: (value: number) => void;
}

export function Counter({ initialValue = 0, step = 1, onChange }: CounterProps) {
  const [count, setCount] = useState(initialValue);
  const [isAnimating, setIsAnimating] = useState(false);

  // CRITICAL: useCallback with complete dependency array
  const increment = useCallback(() => {
    setCount((prev) => {
      const next = prev + step;
      return next;
    });
    setIsAnimating(true);
  }, [step]); // step is the only dependency

  const decrement = useCallback(() => {
    setCount((prev) => prev - step);
    setIsAnimating(true);
  }, [step]);

  // CRITICAL: useEffect with complete dependency array
  useEffect(() => {
    onChange?.(count);
  }, [count, onChange]); // Include ALL dependencies

  // Reset animation flag
  useEffect(() => {
    if (!isAnimating) return;
    const timer = setTimeout(() => setIsAnimating(false), 200);
    return () => clearTimeout(timer); // Cleanup
  }, [isAnimating]);

  return (
    <div
      className={cn(
        'flex items-center gap-4 p-4 rounded-lg border',
        isAnimating && 'scale-105 transition-transform',
      )}
      data-vibehub-component="Counter"
      data-vibehub-file="src/components/Counter.tsx"
    >
      <button
        onClick={decrement}
        className="w-10 h-10 rounded-full bg-gray-100 hover:bg-gray-200"
      >
        -
      </button>
      <span className="text-2xl font-bold w-12 text-center">{count}</span>
      <button
        onClick={increment}
        className="w-10 h-10 rounded-full bg-gray-100 hover:bg-gray-200"
      >
        +
      </button>
    </div>
  );
}
===END_FILE===''',
        },
    },
    "nextjs": {
        "use_client_hooks": {
            "description": "Correct 'use client' with hooks in Next.js",
            "keywords": ["use client", "useState", "useEffect", "Next.js", "browser"],
            "context": "When using React hooks in Next.js App Router",
            "example": '''===FILE: src/components/Counter.tsx===
"use client"  // CRITICAL: MUST be the FIRST line before imports

import { useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/cn';

interface CounterProps {
  initialValue?: number;
  step?: number;
}

export function Counter({ initialValue = 0, step = 1 }: CounterProps) {
  const [count, setCount] = useState(initialValue);

  const increment = useCallback(() => {
    setCount((prev) => prev + step);
  }, [step]);

  const decrement = useCallback(() => {
    setCount((prev) => prev - step);
  }, [step]);

  return (
    <div
      className={cn('flex items-center gap-4 p-4 rounded-lg border')}
      data-vibehub-component="Counter"
      data-vibehub-file="src/components/Counter.tsx"
    >
      <button
        onClick={decrement}
        className="w-10 h-10 rounded-full bg-gray-100"
      >
        -
      </button>
      <span>{count}</span>
      <button
        onClick={increment}
        className="w-10 h-10 rounded-full bg-gray-100"
      >
        +
      </button>
    </div>
  );
}
===END_FILE===''',
        },
        "browser_api_usage": {
            "description": "Correct browser API usage with 'use client'",
            "keywords": ["window", "document", "localStorage", "browser", "client"],
            "context": "When accessing browser-only APIs",
            "example": '''===FILE: src/components/LocalStorageDemo.tsx===
"use client"  // CRITICAL: Required for browser API access

import { useState, useEffect, useCallback } from 'react';

interface LocalStorageDemoProps {
  storageKey: string;
}

export function LocalStorageDemo({ storageKey }: LocalStorageDemoProps) {
  const [value, setValue] = useState<string>("");
  const [isClient, setIsClient] = useState(false);

  // CRITICAL: Check for client-side before accessing window/localStorage
  useEffect(() => {
    setIsClient(true);
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      setValue(stored);
    }
  }, [storageKey]);

  const saveValue = useCallback((newValue: string) => {
    setValue(newValue);
    localStorage.setItem(storageKey, newValue);
  }, [storageKey]);

  if (!isClient) {
    return <div>Loading...</div>; // Prevent hydration mismatch
  }

  return (
    <div data-vibehub-component="LocalStorageDemo" data-vibehub-file="src/components/LocalStorageDemo.tsx">
      <input
        type="text"
        value={value}
        onChange={(e) => saveValue(e.target.value)}
        className="border rounded px-3 py-2"
      />
      <p>Stored in localStorage key: {storageKey}</p>
    </div>
  );
}
===END_FILE===''',
        },
        "server_component": {
            "description": "Correct server component (no 'use client')",
            "keywords": ["server", "async", "fetch", "RSC", "server component"],
            "context": "When creating server components that fetch data",
            "example": '''===FILE: src/app/posts/page.tsx===
// NO "use client" directive - this is a Server Component
import { Suspense } from 'react';

interface Post {
  id: number;
  title: string;
  body: string;
}

// CRITICAL: Server Components can be async and fetch data directly
async function getPosts(): Promise<Post[]> {
  const res = await fetch('https://api.example.com/posts', {
    // Cache options for Next.js
    next: { revalidate: 60 },
  });

  if (!res.ok) {
    throw new Error('Failed to fetch posts');
  }

  return res.json();
}

// Server Component - no hooks, no browser APIs
export default async function PostsPage() {
  const posts = await getPosts();

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Posts</h1>
      <Suspense fallback={<div>Loading posts...</div>}>
        <ul className="space-y-4">
          {posts.map((post) => (
            <li key={post.id} className="border p-4 rounded-lg">
              <h2 className="font-semibold">{post.title}</h2>
              <p className="text-gray-600">{post.body}</p>
            </li>
          ))}
        </ul>
      </Suspense>
    </div>
  );
}
===END_FILE===''',
        },
        "framer_motion_jsx_syntax": {
            "description": "Correct Framer Motion JSX syntax and import",
            "keywords": ["framer-motion", "motion", "jsx", "syntax", "import"],
            "context": "When using Framer Motion components in JSX",
            "example": '''===FILE: src/components/MotionDemo.tsx===
"use client"  // Required for Framer Motion in Next.js

import { motion } from 'framer-motion';  // CRITICAL: Must import motion

interface MotionDemoProps {
  title: string;
}

export function MotionDemo({ title }: MotionDemoProps) {
  return (
    <div>
      {/* CORRECT: Use <motion.div> with proper import */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        data-vibehub-component="MotionDemo"
        data-vibehub-file="src/components/MotionDemo.tsx"
      >
        <h1>{title}</h1>
      </motion.div>

      {/* CORRECT: Other motion elements */}
      <motion.span
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.2 }}
      >
        Animated text
      </motion.span>
    </div>
  );
}

// WRONG EXAMPLES - DO NOT USE:
// <motion.div> without import { motion } from 'framer-motion'
// <div.div> - invalid double dot
// <.div> - invalid leading dot
// <motion.> - incomplete tag
===END_FILE===''',
        },
        "jsx_syntax_rules": {
            "description": "JSX tag syntax rules and common mistakes",
            "keywords": ["jsx", "syntax", "tag", "component", "html"],
            "context": "When writing JSX tags in React components",
            "example": '''===FILE: src/components/JsxDemo.tsx===
"use client"

import { Card } from './Card';  // Custom component import

interface JsxDemoProps {
  showCard?: boolean;
}

export function JsxDemo({ showCard }: JsxDemoProps) {
  return (
    <div>
      {/* CORRECT: Standard HTML elements */}
      <div className="container">
        <span>Text</span>
        <input type="text" />
        <img src="/logo.png" alt="Logo" />
      </div>

      {/* CORRECT: Custom components (PascalCase, imported) */}
      {showCard && <Card title="Hello" />}

      {/* CORRECT: Self-closing tags */}
      <br />
      <hr />
      <input type="checkbox" />

      {/* WRONG - DO NOT USE:
      // Invalid: double dot notation
      <div.div>content</div.div>

      // Invalid: leading dot
      <.div>content</.div>

      // Invalid: incomplete motion tag
      <motion.>content</motion.>

      // Invalid: motion without import
      <motion.div>content</motion.div>  // without import { motion }

      // Invalid: lowercase custom component
      <myComponent />  // Should be <MyComponent />
      */}
    </div>
  );
}
===END_FILE===''',
        },
    },
}

# Common patterns that apply to all templates
COMMON_EXAMPLES: dict[str, dict[str, Any]] = {
    "props_interface": {
        "description": "Correct Props interface pattern",
        "keywords": ["interface", "props", "TypeScript", "types"],
        "example": '''// CORRECT: Named interface at top of file
interface CardProps {
  title: string;
  description?: string;  // optional
  children: React.ReactNode;
  onAction?: () => void;
}

export function Card({ title, description, children, onAction }: CardProps) {
  return (
    <div>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {children}
      {onAction && <button onClick={onAction}>Action</button>}
    </div>
  );
}

// WRONG: Inline type (avoid this)
// export function Card({ title }: { title: string })''',
    },
    "dependency_array": {
        "description": "Complete dependency array examples",
        "keywords": ["useEffect", "useCallback", "dependencies", "deps"],
        "example": '''// CORRECT: Include ALL dependencies
function UserProfile({ userId, onUpdate }: { userId: string; onUpdate: () => void }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, [userId]); // userId is used, so it's in deps

  const handleUpdate = useCallback(() => {
    onUpdate();
    fetchUser(userId).then(setUser);
  }, [onUpdate, userId]); // BOTH onUpdate and userId are used

  return <div>{user?.name}</div>;
}

// WRONG: Missing dependencies
// useEffect(() => { fetchUser(userId) }, []); // Missing userId!
// useCallback(() => { onUpdate() }, []); // Missing onUpdate!''',
    },
    "conditional_rendering": {
        "description": "Type-safe conditional rendering",
        "keywords": ["conditional", "render", "optional", "ternary"],
        "example": '''interface NotificationProps {
  message: string;
  type?: 'info' | 'success' | 'warning' | 'error';
  onDismiss?: () => void;
}

export function Notification({ message, type = 'info', onDismiss }: NotificationProps) {
  // Type-safe style mapping
  const typeStyles: Record<string, string> = {
    info: 'bg-blue-100 text-blue-800',
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    error: 'bg-red-100 text-red-800',
  };

  return (
    <div className={typeStyles[type]}>
      <p>{message}</p>
      {/* CORRECT: Check before rendering */}
      {onDismiss && (
        <button onClick={onDismiss}>Dismiss</button>
      )}
    </div>
  );
}''',
    },
    "jsx_common_errors": {
        "description": "Common JSX syntax errors and correct versions",
        "keywords": ["jsx", "error", "syntax", "framer-motion", "motion", "tag"],
        "example": '''// =============================================================================
// COMMON JSX ERRORS - AVOID THESE
// =============================================================================

// ERROR 1: Invalid double-dot JSX tag
// WRONG:
const wrong1 = <div.div>Content</div.div>;
const wrong2 = <motion.div.span>Content</motion.div.span>;

// CORRECT:
const correct1 = <div>Content</div>;
const correct2 = <motion.div>Content</motion.div>;

// -----------------------------------------------------------------------------

// ERROR 2: Leading dot in JSX tag
// WRONG:
const wrong3 = <.div>Content</.div>;

// CORRECT:
const correct3 = <div>Content</div>;

// -----------------------------------------------------------------------------

// ERROR 3: Incomplete motion tag
// WRONG:
import { motion } from 'framer-motion';
const wrong4 = <motion.>Content</motion.>;

// CORRECT:
import { motion } from 'framer-motion';
const correct4 = <motion.div>Content</motion.div>;

// -----------------------------------------------------------------------------

// ERROR 4: Using motion without import
// WRONG:
// (no import)
const wrong5 = <motion.div>Content</motion.div>;

// CORRECT:
import { motion } from 'framer-motion';
const correct5 = <motion.div>Content</motion.div>;

// -----------------------------------------------------------------------------

// ERROR 5: Unclosed or mismatched tags
// WRONG:
const wrong6 = <div><span>Content</div></span>;  // Mismatched order
const wrong7 = <div>Content;  // Missing closing tag

// CORRECT:
const correct6 = <div><span>Content</span></div>;
const correct7 = <div>Content</div>;

// =============================================================================
// JSX RULES SUMMARY
// =============================================================================
// 1. HTML elements: <div>, <span>, <input /> (lowercase, no dots)
// 2. Custom components: <Component /> (PascalCase, must be imported)
// 3. Framer Motion: <motion.div> (requires: import { motion })
// 4. Always close tags: <div></div> or self-close <img />
// 5. Never use: <x.y.z>, <.x>, <motion.> (invalid syntax)
''',
    },
}


def get_relevant_examples(template_name: str, context: str, max_examples: int = 2) -> list[dict[str, Any]]:
    """Get relevant few-shot examples based on template and context.

    Args:
        template_name: The template being used (react-vite, nextjs, etc.)
        context: The generation context (phase description, file purpose, etc.)
        max_examples: Maximum number of examples to return

    Returns:
        List of example dictionaries with 'description' and 'example' keys
    """
    context_lower = context.lower()
    matched_examples: list[tuple[int, dict[str, Any]]] = []

    # Check template-specific examples
    template_examples = FEW_SHOT_EXAMPLES.get(template_name, {})
    for key, example in template_examples.items():
        score = _calculate_relevance_score(context_lower, example)
        if score > 0:
            matched_examples.append((score, example))

    # Check common examples
    for key, example in COMMON_EXAMPLES.items():
        score = _calculate_relevance_score(context_lower, example)
        if score > 0:
            matched_examples.append((score, example))

    # Sort by relevance score (descending) and take top max_examples
    matched_examples.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in matched_examples[:max_examples]]


def _calculate_relevance_score(context: str, example: dict[str, Any]) -> int:
    """Calculate relevance score based on keyword matching."""
    score = 0
    keywords = example.get("keywords", [])

    for keyword in keywords:
        if keyword.lower() in context:
            score += 1

    return score


def format_examples_for_prompt(examples: list[dict[str, Any]]) -> str:
    """Format examples for inclusion in the system prompt."""
    if not examples:
        return ""

    parts = ["\n## CORRECT CODE EXAMPLES\n"]

    for i, example in enumerate(examples, 1):
        parts.append(f"\n### Example {i}: {example.get('description', '')}\n")
        parts.append(f"Context: {example.get('context', 'General usage')}\n")
        parts.append("```typescript\n")
        parts.append(example.get("example", ""))
        parts.append("\n```\n")

    return "\n".join(parts)


def inject_examples_into_prompt(
    base_prompt: str,
    template_name: str,
    phase_description: str,
    phase_files: str,
) -> str:
    """Inject relevant few-shot examples into the prompt.

    Args:
        base_prompt: The original system prompt
        template_name: The template being used
        phase_description: Description of the current phase
        phase_files: Comma-separated list of files being generated

    Returns:
        Enhanced prompt with relevant examples
    """
    # Combine context for matching
    context = f"{phase_description} {phase_files}"

    # Get relevant examples
    examples = get_relevant_examples(template_name, context, max_examples=2)

    if not examples:
        return base_prompt

    # Format and inject examples
    examples_section = format_examples_for_prompt(examples)

    # Insert examples before the final "Generate the complete content" instruction
    marker = "Generate the complete content for each file listed in this phase."
    if marker in base_prompt:
        return base_prompt.replace(marker, examples_section + "\n" + marker)

    # Fallback: append to end
    return base_prompt + examples_section
