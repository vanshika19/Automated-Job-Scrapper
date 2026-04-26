# API authentication

The API ships with an optional bearer-token gate. By default (no token
configured) every endpoint is open — useful for local development. Once
`API_TOKEN` is set, every request to a protected endpoint must carry an
`Authorization: Bearer <token>` header.

## Enable

Generate a token and set it on the API process:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
export API_TOKEN=<paste-here>
python -m job_scraper serve
```

In Docker Compose, edit `.env`:

```env
API_TOKEN=<paste-here>
```

then `docker compose up -d --force-recreate api`.

You can configure several tokens by separating them with commas
(`API_TOKEN=token-a,token-b`). All tokens are compared in constant time.

## Public vs protected


| Path                 | Auth     |
| -------------------- | -------- |
| `GET /api/health`    | Public   |
| `GET /api/stats`     | Required |
| `GET /api/companies` | Required |
| `GET /api/jobs`      | Required |
| `POST /api/match`    | Required |


`/api/health` reports `auth_required: true|false` so the dashboard knows
whether to surface the token UI.

## Frontend

When the dashboard receives a 401 it pops the token dialog automatically.
Tokens are stored in browser `localStorage` under `jobscrapper.apiToken`
(the user can clear or update them anytime via the gear button in the
header).

## Curl example

```bash
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/api/stats
```

