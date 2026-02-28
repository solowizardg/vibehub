# Strapi E2B Template

This template provides a Strapi headless CMS backend for VibeHub applications.

## Overview

The Strapi template runs alongside the frontend application in the E2B sandbox, providing:

- Auto-generated Content-Types based on the project blueprint
- REST API for frontend data fetching
- Admin panel for content management
- SQLite database for data persistence

## Architecture

```
E2B Sandbox
├── /home/user/project/     # Frontend application (Next.js/React)
└── /home/user/strapi/      # Strapi CMS backend
```

## Ports

- Frontend: 3000 (Next.js) or 4173 (Vite preview)
- Strapi CMS: 1337

## API Endpoints

Once running, Strapi provides:

- Content API: `http://localhost:1337/api/{content-type}`
- Admin Panel: `http://localhost:1337/admin`
- Health Check: `http://localhost:1337/api/health`

## Content-Type Generation

The `cms_setup` node in the LangGraph pipeline:

1. Analyzes the project blueprint for data requirements
2. Generates Strapi Content-Type schemas in JSON format
3. Writes schemas to `src/api/{name}/content-types/{name}/schema.json`
4. Starts the Strapi development server

## Frontend Integration

Generated frontend code receives:

- `NEXT_PUBLIC_STRAPI_URL` environment variable (or equivalent for Vite)
- TypeScript interfaces matching the Strapi schemas
- API client utilities for fetching data

Example API call:

```typescript
const response = await fetch(
  `${process.env.NEXT_PUBLIC_STRAPI_URL}/api/articles?populate=*`
);
const { data, meta } = await response.json();
```

## Configuration

### Environment Variables

Frontend applications should use:

```
NEXT_PUBLIC_STRAPI_URL=https://{sandbox-host}:1337  # Next.js
VITE_STRAPI_URL=https://{sandbox-host}:1337         # Vite
```

### CORS

Strapi is configured to allow all origins (`*`) for development.

## Development

To test the Strapi template locally:

1. Create a sandbox with the strapi template
2. Install dependencies: `npm install`
3. Start development server: `npm run develop`
4. Access admin panel at `http://localhost:1337/admin`

## Content-Type Schema Format

```json
{
  "kind": "collectionType",
  "collectionName": "articles",
  "info": {
    "singularName": "article",
    "pluralName": "articles",
    "displayName": "Article",
    "description": "Blog articles"
  },
  "options": {
    "draftAndPublish": true
  },
  "attributes": {
    "title": {
      "type": "string",
      "required": true
    },
    "content": {
      "type": "richtext"
    },
    "slug": {
      "type": "uid",
      "targetField": "title"
    }
  }
}
```
