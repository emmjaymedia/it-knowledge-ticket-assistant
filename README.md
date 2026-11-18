# ServiceDesk Knowledge

An IT support workspace that answers employee questions from a scoped knowledge base and turns unresolved requests into editable support tickets. The sample workspace uses synthetic IT policies.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app
```

Open http://127.0.0.1:8000. The browser workspace and JSON API run on the same FastAPI server. Open `/docs` for the API contract. The default configuration runs without credentials or a separate database.

| Try | Expected behavior |
| --- | --- |
| VPN connection timeout | Returns a troubleshooting excerpt and cites its section. |
| Issue without guidance | Offers a ticket draft. Edit it and submit to get a ticket ID. |
| Restricted recovery guide | An employee receives no restricted excerpt. |

## Retrieval and ticket flow

- Ingestion turns each named article section into a chunk with a stable ID and access label. The optional PostgreSQL store uses pgvector cosine distance. Local mode uses normalized hashed term vectors with domain synonyms.
- The server scopes candidates by role before answer selection. When enabled, the model selects a candidate ID or abstains. The API returns the original approved excerpt and citation. Invalid selections and provider failures during selection fall back to the top scoped excerpt. Embedding service failures send the request to IT review.
- Ticket routing uses deterministic rules. The user can edit the queue and description before submitting. A unique request ID prevents duplicates on retry, and reusing that ID with different content produces a conflict.
- Application logs track latency, response mode, and available chat token counts without logging question text or excerpts. Tickets are stored in SQLite. Set `TICKET_DB` to keep the file on a persistent volume.

## PostgreSQL and model configuration

Copy `.env.example` to `.env`, set the variables you want, and export them before starting the server. For the local PostgreSQL container set `DATABASE_URL=postgresql://servicedesk:local-development@127.0.0.1:5432/servicedesk`.

```bash
docker compose up -d vector
set -a
source .env
set +a
python engine.py
uvicorn app:app
```

Set `OPENAI_API_KEY` for model-assisted selection. With PostgreSQL enabled, this also enables OpenAI embeddings. Re-run ingestion with the same settings used by the API whenever the embedding configuration or documents change. The query and scoped excerpt candidates are sent to the configured provider when model selection is enabled.

The browser runs as an employee. To test the IT role, configure `IT_DEMO_TOKEN` and use the API with the `X-IT-Token` header. The shared token and anonymous employee flow are intended for synthetic data demonstrations. A real rollout would require an identity provider, per-user ticket ownership, and rate limits.

## Evaluation

```bash
python -m unittest -v
python evaluate.py
```

The local benchmark scores exact top citation or correct abstention on 13 labeled questions. The recorded run scored **11/13** for keyword matching on headings and **13/13** for local vector retrieval against full sections. Section content helped distinguish VPN sign-in problems from connection timeouts and software licensing requests from identity questions.

See [evaluation.json](evaluation.json) for timings and individual failures. The dataset is small and synthetic. Its timings cover local retrieval and answer assembly. The benchmark used zero provider calls and does not estimate hosted model quality, latency, or cost.
