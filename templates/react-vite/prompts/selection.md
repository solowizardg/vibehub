# When to Select This Template

Choose the **react-vite** template when the user wants to build:

- **React SPAs** - Single-page applications that run entirely in the browser
- **Dashboards** - Admin panels, analytics dashboards, internal tools
- **Client-side apps** - Apps that fetch data from APIs or a backend CMS and render in the browser
- **Prototypes and MVPs** - Quick iteration with a fast development experience

**Do NOT select this template when:**

- SSR (Server-Side Rendering) is required - use a framework like Next.js, Remix, or similar
- SSG (Static Site Generation) with pre-rendering is required - consider Astro or Next.js
- The app needs built-in backend/database - this template is frontend-only
- Static marketing sites with minimal interactivity - simpler static generators may suffice

This template prioritizes **fast dev experience** (Vite HMR, minimal config) and **client-side React** over server capabilities.

## Dependency Baseline (Build Safety)

This template also treats `package.json` as the dependency manifest.

- Only import third-party packages that are declared in `package.json`
- If generation needs a new package, update `package.json` in the same step
- Keep CSS plugins/imports aligned with declared dependencies
