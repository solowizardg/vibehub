# Usage Guide - Next.js App Template

## Critical LLM Instructions

### Framework

- **Next.js 14 App Router only** - Do NOT use the Pages Router (`pages/` directory)
- **File-based routing** in `src/app/`
- **Server Components by default** - Add `"use client"` only when needed (useState, useEffect, event handlers, browser APIs)

### Styling

- **TailwindCSS v4** - CSS-based config via `@import "tailwindcss";` in globals.css
- **DO NOT modify**: `next.config.mjs`, `tsconfig.json`, `postcss.config.mjs`
- Use the **cn()** utility from `src/lib/cn.ts` for conditional classes

### File Structure

- **Layout**: Root layout in `src/app/layout.tsx`
- **Pages**: Create pages as `src/app/[route]/page.tsx` (e.g. `src/app/about/page.tsx` for `/about`)
- **API routes**: Create as `src/app/api/[route]/route.ts` (e.g. `src/app/api/users/route.ts` for `/api/users`)
- **Shared components**: Place in `src/components/`

### Data Fetching

- Use **async Server Components** for data fetching (no need for useEffect in Server Components)
- Or use **fetch** in Route Handlers (`route.ts`) for API responses
- For CMS/external data: call the backend API from Server Components using `fetch()`

### Conventions

- **TypeScript strict mode** - Use proper types, avoid `any`
- **Functional components with hooks** - Use standard React patterns
- **Metadata**: Export `metadata` or `generateMetadata` in layouts and pages for SEO
