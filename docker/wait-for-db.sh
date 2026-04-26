#!/usr/bin/env bash
# Wait for the database to accept connections before launching the app.
# Works for both sqlite (no-op) and postgres (parses DATABASE_URL).
set -euo pipefail

URL="${DATABASE_URL:-}"

if [[ -z "${URL}" || "${URL}" == sqlite:* ]]; then
  echo "[wait-for-db] sqlite or no DATABASE_URL set; skipping wait."
  exit 0
fi

# crude parser: postgresql+psycopg://user:pass@host:port/dbname
host=$(echo "${URL}" | sed -E 's#.*@([^:/?]+).*#\1#')
port=$(echo "${URL}" | sed -E 's#.*:([0-9]+)/.*#\1#; t; s#.*#5432#')

echo "[wait-for-db] waiting for ${host}:${port} ..."
for i in $(seq 1 60); do
  if (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
    echo "[wait-for-db] ${host}:${port} is up."
    exit 0
  fi
  sleep 1
done
echo "[wait-for-db] timed out waiting for ${host}:${port}" >&2
exit 1
