# React-Vite Template Usage Guide

## Tech Stack

- **React 19** - Latest React with concurrent features
- **Vite 6** - Fast bundler and dev server with HMR
- **TypeScript 5.7+** - Strict mode enabled
- **TailwindCSS v4** - CSS-based config, no tailwind.config.js; uses `@tailwindcss/vite` plugin

## File Structure Conventions

- `src/components/` - Reusable UI components
- `src/pages/` - Page-level components (route targets)
- `src/lib/` - Utilities, helpers, API clients
- `src/hooks/` - Custom React hooks

## CSS Approach

- Use TailwindCSS v4 utility classes directly
- Use the `cn()` helper from `@/lib/cn` for conditional classes: `cn('base-classes', condition && 'conditional-classes', className)`
- Tailwind v4 scans source files automatically - no content config needed
- Theme customization goes in `src/index.css` via `@theme` blocks if needed

## Key Rules

1. **DO NOT modify** `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`, or `postcss.config.js`
2. The template includes a basic `App.tsx` shell - build pages and components from there
3. When adding new pages, update the routing in `App.tsx` (add `<Route>` entries)
4. Use `fetch()` to call backend APIs or CMS endpoints
5. Use **functional components with hooks** only - no class components
6. **Naming**: PascalCase for components, camelCase for utilities/hooks

## Example Component

```tsx
import { cn } from '@/lib/cn';

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn('rounded-lg border bg-card p-4 shadow-sm', className)}>
      {children}
    </div>
  );
}
```

## Adding a New Page

1. Create `src/pages/MyPage.tsx`
2. In `App.tsx`, add: `<Route path="/my-page" element={<MyPage />} />`

## Icons

Use `lucide-react` for icons: `import { ChevronRight } from 'lucide-react'`
