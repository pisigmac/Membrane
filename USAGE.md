# Membrane Usage Guide

Step-by-step guide for running Membrane Memory OS, the HTTP console, and wiring it into agents.

## 1. Prerequisites

- Python 3.10+
- Node 20+ (console)
- Sibling [DeskID](../DeskID/) authentication service for multi-user login

```bash
pip install -e ".[dev,api]"
# optional real embeddings:
pip install -e ".[embeddings]"
```

## 2. Start / stop

```bash
# Option A: Run via Docker (standalone Membrane container)
docker compose up -d
# To stop: docker compose down

# Option B: Run locally on host
# Terminal 1: DeskID (required for console JWT login)
cd ../DeskID && AUTH_DATABASE_URL=sqlite+pysqlite:////tmp/deskid_auth.db deskid

# Terminal 2: Membrane store + maintain loop + API
./start_all.sh          # also starts membrane serve on :8787
./scripts/health.sh
./stop_all.sh           # stops loop + API (keeps data)

# Terminal 3: Vite console
cd web && npm install && npm run dev   # :5173
```

What `start_all.sh` does:

1. Sets `MEMBRANE_ROOT` (default: `./.membrane`)
2. Installs / locates the `membrane` CLI
3. Runs `membrane init`
4. Starts `scripts/maintain_loop.sh` in the background
5. Starts `membrane serve` (API; serves `web/dist` if built)

Logs under `$MEMBRANE_ROOT/logs/`. PIDs under `$MEMBRANE_ROOT/run/`.

### DeskID / API env

| Variable | Purpose |
|----------|---------|
| `MEMBRANE_AUTH_JWKS_URL` | DeskID JWKS (default `http://127.0.0.1:8090/.well-known/jwks.json`) |
| `MEMBRANE_AUTH_ISSUER` | Must match DeskID `AUTH_ISSUER` |
| `MEMBRANE_AUTH_AUDIENCE` | Default `membrane` |
| `MEMBRANE_CORS_ORIGINS` | SPA origins |
| `AUTH_*` | See DeskID `.env.example` (Google/GitHub OAuth; prefix is still `AUTH_`) |

Machine agents may use `X-API-Key` with keys in `$MEMBRANE_ROOT/auth/api_keys.json` (prefer DeskID JWTs long-term).

Demo-speed schedule (optional):

```bash
MEMBRANE_DEMO_SCHEDULE=1 ./start_all.sh
```

## 3. Ingest session history

Sessions are JSON or JSONL. See [`fixtures/sessions.json`](fixtures/sessions.json).

```bash
./scripts/ingest.sh fixtures/sessions.json --user-id 4821 --session-id demo
```

This runs **construct → govern**:

- Skips adversarial / low `safety_score` sessions
- Routes memories to `user-4821` (or session staging if ephemeral)
- Holds contradictions as `PENDING` for 24h

Equivalent CLI:

```bash
export MEMBRANE_ROOT=./.membrane
membrane construct -i fixtures/sessions.json -o /tmp/batch.json
membrane govern -b /tmp/batch.json --user-id 4821 --session-id demo --root "$MEMBRANE_ROOT"
```

## 4. Query memory for a task

```bash
./scripts/query.sh "How do I deploy?" --scope user-4821 --budget 2000
```

Output is a prompt block:

```text
=== AGENT MEMORY ===
[Constraints]
- ...
[Skills]
- ...
[Facts]
- ...
[Preferences]
- ...
=== END MEMORY ===
```

Paste that block into your agent’s system prompt (or use the Python helper below).

## 5. Resolve contradictions

```bash
./scripts/health.sh
# pick an id from unresolved_contradictions
membrane resolve-contradiction --id <contradiction-uuid> --keep new \
  --root "$MEMBRANE_ROOT"
# --keep: new | existing | both-archive
```

## 6. Maintenance (manual)

```bash
membrane maintain --mode daily   --root "$MEMBRANE_ROOT"
membrane maintain --mode weekly  --root "$MEMBRANE_ROOT"
membrane maintain --mode monthly --root "$MEMBRANE_ROOT"   # HALTs on checksum mismatch
```

Cron alternative: [`scripts/cron.example`](scripts/cron.example).

## 7. Configuration

| Variable | Purpose |
|----------|---------|
| `MEMBRANE_ROOT` | Data directory (JSONL store, audit, logs) |
| `MEMBRANE_CONFIG` | Path to `config.yaml` |
| `MEMBRANE_LLM_API_KEY` | Required if `llm.provider: openai_compat` |
| `MEMBRANE_DEMO_SCHEDULE` | `1` = faster maintain loop for demos |

Edit [`config.yaml`](config.yaml) for TTLs, contradiction thresholds, embeddings provider (`stub` \| `sentence-transformers`), and LLM extractor.

---

## Agent integrations

### Current status

**No first-party plugins** for LangChain, LlamaIndex, CrewAI, AutoGen, Cursor, Claude Desktop, or MCP ship in v1.0.

Membrane is agent-agnostic by design: any agent that can run a shell command or call Python can use it.

### Supported integration paths today

| Path | How |
|------|-----|
| **CLI / scripts** | `./scripts/query.sh` or `membrane retrieve` before each turn |
| **Python API** | `membrane.integrations.inject_system_memory(...)` |
| **Cursor / Claude rules** | Paste `cursor_rule_snippet()` into a project rule (manual hook) |
| **OpenAI-compatible agents** | Inject memory into the `messages` list as a system message |

### Python example (OpenAI-style agents)

```python
from membrane.integrations import inject_system_memory

messages = [
    {"role": "system", "content": "You are a helpful ops assistant."},
    {"role": "user", "content": "How do I deploy?"},
]

messages = inject_system_memory(
    messages,
    task="How do I deploy?",
    scope="user-4821",
    root="./.membrane",
    budget=2000,
)
# pass `messages` to your chat completion API
```

Fetch only the block:

```python
from membrane.integrations import fetch_memory_block

block = fetch_memory_block("How do I deploy?", "user-4821", root="./.membrane")
print(block)
```

### Cursor / Claude Code (manual)

```bash
./scripts/query.sh "<the user question>" --scope user-4821
```

Copy the printed `=== AGENT MEMORY ===` block into the agent’s context. Constraints in that block should be treated as hard rules.

Or print a rule template:

```python
from membrane.integrations import cursor_rule_snippet
print(cursor_rule_snippet(scope="user-4821"))
```

### Suggested future adapters (not built yet)

- MCP server exposing `retrieve` / `ingest` / `status` tools
- LangChain `BaseRetriever` / tool wrapper
- LlamaIndex memory module
- Cursor/Claude MCP install one-liner

If you want one of these next, say which agent stack to target first.

---

## Utilities reference

| Script | Role |
|--------|------|
| `./start_all.sh` | Init + start maintain loop |
| `./stop_all.sh` | Stop maintain loop |
| `scripts/ingest.sh` | construct → govern |
| `scripts/query.sh` | retrieve for a task |
| `scripts/health.sh` | status + loop PID |
| `scripts/reset.sh` | stop; optional `--data` wipe |
| `scripts/maintain_loop.sh` | background scheduler |
| `scripts/env.sh` | shared env (sourced by others) |
| `scripts/cron.example` | system cron template |

## Typical day-one flow

```bash
./start_all.sh
./scripts/ingest.sh fixtures/sessions.json --user-id 4821 --session-id demo
./scripts/query.sh "How do I deploy?" --scope user-4821
./scripts/health.sh
./stop_all.sh
```
