# E2B Sandbox Templates

This directory contains the custom E2B sandbox templates used by the AI agent to execute and test generated code.

## Why Custom Templates?

Vibehub's AI agent generates modern web applications (e.g., Next.js, React + Vite) that have large dependency trees. Running `npm install` inside a standard E2B sandbox for every user request is slow and often results in Out-Of-Memory (OOM) errors due to sandbox resource limits.

To solve this, we use **Custom E2B Templates**. These templates pre-install all the necessary `node_modules` during the **cloud build phase**. When the agent creates a sandbox, it starts instantly with all dependencies already available, allowing for lightning-fast `npm install` (which just verifies the lockfile) and immediate dev server startup.

## Requirements

- An [E2B](https://e2b.dev/) account (the Free Tier is sufficient for open-source self-hosting).
- The E2B CLI installed globally: `npm install -g @e2b/cli`

## How to Build the Templates

Before the agent can use these sandboxes, you must build the templates in your own E2B account.

### 1. Authenticate the CLI

Open a terminal and log in to your E2B account:

```bash
npx -y @e2b/cli@latest auth login
```

### 2. Build the Next.js Template

Navigate to the `nextjs` template directory, install the required SDK, and run the build:

```bash
cd e2b-templates/nextjs
npm install e2b tsx
npx tsx build.prod.ts
```

This process takes 1-2 minutes. The CLI will output a Template ID like this:
`Template created with ID: w4ys13s7hogs17qus07h`

### 3. Update Environment Variables

Copy the Template ID from the previous step and add it to your `backend/.env` file:

```env
E2B_TEMPLATE_NEXTJS="your_template_id_here"
```

## Creating Additional Templates

If you wish to add support for a new framework (e.g., `react-vite`):

1. Create a new directory under `e2b-templates/` (e.g., `react-vite`).
2. Run `npx -y @e2b/cli@latest template init --name "react-vite-sandbox"` inside the new directory and select TypeScript.
3. Modify the generated `template.ts` to copy your `package.json` and run `npm install` (see `nextjs/template.ts` for reference).
4. Run `npx tsx build.prod.ts` to build it.
5. Add the resulting Template ID to your `.env` file (e.g., `E2B_TEMPLATE_REACT_VITE`).
6. Update `get_template_id()` in `backend/sandbox/e2b_backend.py`.
