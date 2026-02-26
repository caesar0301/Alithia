# Storage Setup Guide

Configure storage backends for Alithia.

## Backends

| Backend | Description | Use Case |
|---------|-------------|----------|
| **SQLite** | Local file (default) | Works offline |
| **Supabase** | Cloud PostgreSQL | Multi-user |
| **PostgreSQL** | Self-hosted | Full control |

## Configuration

```json
{
  "storage": {
    "backend": "sqlite",  // "sqlite", "supabase", or "postgres"
    "user_id": "your_email@example.com",
    "fallback_to_sqlite": true,
    "sqlite_path": "data/alithia.db"
  }
}
```

### Supabase

```json
{
  "storage": {
    "backend": "supabase",
    "user_id": "you@example.com",
    "supabase": {
      "url": "https://xxxxx.supabase.co",
      "service_role_key": "your_key"
    }
  }
}
```

### PostgreSQL

```json
{
  "storage": {
    "backend": "postgres",
    "user_id": "you@example.com",
    "postgres": {
      "dsn": "postgresql://user:pass@host:5432/db"
    }
  }
}
```

## Supabase Setup

1. Create project at [supabase.com](https://supabase.com)
2. Run migrations in SQL Editor:
   - `alithia/storage/migrations/001_initial_schema.sql`
   - `002_paperscout_v2.sql`
   - `003_sync_service.sql`
   - `004_dashboard.sql`
3. Get credentials: Settings → API

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ALITHIA_SUPABASE_URL` | Supabase project URL |
| `ALITHIA_SUPABASE_SERVICE_KEY` | Service role key |
| `ALITHIA_POSTGRES_DSN` | PostgreSQL connection string |
| `ALITHIA_STORAGE_BACKEND` | Backend: sqlite, supabase, postgres |

## Troubleshooting

- **Connection fails**: Check credentials, network, project status (free tier may be paused)
- **Fallback to SQLite**: Expected when primary fails and `fallback_to_sqlite: true`

## Security

- Never commit credentials to version control
- Use `.gitignore`'d config files or environment variables
- Enable RLS if sharing Supabase project

