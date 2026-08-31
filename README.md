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

Membrane does **not** own identity. Start the shared [Auth](../Auth/README.md) service, then the Membrane API + Vite console:

```bash
# Terminal 1 — Auth (:8090)
cd ../Auth && pip install -e ".[dev]" && AUTH_DATABASE_URL=sqlite+pysqlite:////tmp/pisigma_auth.db pisigma-auth

# Terminal 2 — Membrane API (:8787) + maintain loop
./start_all.sh

# Terminal 3 — Console
cd web && npm install && npm run dev
# → http://localhost:5173  (Google/GitHub/email login via Auth)
```

Env: `MEMBRANE_AUTH_JWKS_URL`, `MEMBRANE_AUTH_ISSUER`, OAuth client IDs on Auth (see Auth README).

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
