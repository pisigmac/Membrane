# Membrane Memory OS v1.0

Open-source operating system for agent memory: **ingestion → distillation → storage → retrieval → contradiction management → forgetting**.

## Install

```bash
pip install -e ".[dev,api]"
# optional real embeddings:
pip install -e ".[embeddings]"
```

## Quick start (CLI)

```bash
./start_all.sh
./scripts/ingest.sh fixtures/sessions.json --user-id 4821 --session-id demo
./scripts/query.sh "How do I deploy?" --scope user-4821
./scripts/health.sh
./stop_all.sh
```

## Console (multi-user UI)

Membrane does **not** own identity. It validates JWTs against [DeskID](../DeskID/README.md) (or any external JWKS endpoint).

### Run with Docker

```bash
# Optional: One-time setup of central DeskID identity stack (if not already running)
./setup_deskid.sh

# Run Membrane in Docker:
docker compose up -d
# Or point to an external / remote DeskID:
# MEMBRANE_AUTH_JWKS_URL=https://auth.example.com/.well-known/jwks.json docker compose up -d
```

### Run Locally on Host

```bash
# Terminal 1 — DeskID (:8090)
cd ../DeskID && pip install -e ".[dev]" && AUTH_DATABASE_URL=sqlite+pysqlite:////tmp/deskid_auth.db deskid

# Terminal 2 — Membrane API (:8787) + maintain loop
./start_all.sh

# Terminal 3 — Console
cd web && npm install && npm run dev
# → http://localhost:5173  (Google/GitHub/email login via DeskID)
```

Env: `MEMBRANE_AUTH_JWKS_URL`, `MEMBRANE_AUTH_ISSUER`, OAuth client IDs on DeskID (see DeskID README; env prefix remains `AUTH_*`).

Full walkthrough: [`USAGE.md`](USAGE.md).

```bash
export MEMBRANE_ROOT=./.membrane
membrane init --root "$MEMBRANE_ROOT"

membrane construct --input fixtures/sessions.json --out /tmp/batch.json
membrane govern --batch /tmp/batch.json --user-id 4821 --session-id demo --root "$MEMBRANE_ROOT"
membrane retrieve --task "How do I deploy?" --scope user-4821 --budget 2000 --root "$MEMBRANE_ROOT"
membrane status --root "$MEMBRANE_ROOT"
membrane maintain --mode daily --root "$MEMBRANE_ROOT"
```

## Phases

| Phase | Command | Role |
|-------|---------|------|
| Construction | `membrane construct` | Segment sessions, extract/validate/score memories |
| Governance | `membrane govern` | Scope, PII scan, contradiction hold, append-only persist |
| Retrieval | `membrane retrieve` | Rank by similarity + recency + confidence; format prompt block |
| Maintenance | `membrane maintain --mode daily\|weekly\|monthly` | Evict, consolidate, dedup, compact + checksum |

## Layout (`$MEMBRANE_ROOT`)

```
memory/
  org/memories.jsonl
  user-{id}/memories.jsonl
  session-{id}/staging/memories.jsonl
  archive/{scope}/memories.jsonl
  audit/main.log
  audit/contradictions/{id}.json
```

All paths are relative to `MEMBRANE_ROOT`. Absolute traversal is rejected.

## Config

Defaults live in [`config.yaml`](config.yaml). Override with `MEMBRANE_CONFIG` or `--config`.

- Embeddings: `stub` (default, offline) or `sentence-transformers`
- LLM extractor: `heuristic` (default) or `openai_compat` (`MEMBRANE_LLM_API_KEY`)

## Guardrails

- Sessions marked adversarial/jailbreak or below `safety_score_threshold` are never constructed.
- Archived memories are not retrieved unless `--include-archived`.
- Monthly compaction **HALTs** on audit/store checksum mismatch.

## Cron

See [`scripts/cron.example`](scripts/cron.example).

## License

MIT
