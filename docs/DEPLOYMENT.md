# Deployment

## 1. Configure

```bash
cp .env.example .env
```

Replace both webhook tokens with long independent random values.

Important: TradingView cannot add arbitrary HMAC headers to an alert webhook. The current receiver therefore authenticates with an unguessable URL-path token. If a reverse proxy logs request paths, redact `/webhook/tradingview/*` and `/webhook/jev/*` from access logs.

## 2. Start

```bash
docker compose up -d --build
```

Containers:

- `api`: FastAPI gateway on port 8080.
- `streamer`: Binance + Hyperliquid live microstructure collection.
- shared Docker volume: SQLite/WAL database.

## 3. TradingView

In the indicator:

- enable **Export Research Candidates** for dataset collection;
- optionally enable **Export Qualified Candidates to Jev** after the webhook pipeline is running.

Create an alert using **Any alert() function call** and point it to:

```
https://YOUR_HOST/webhook/tradingview/YOUR_TV_WEBHOOK_TOKEN
```

The Pine payload carries a stable `event_id`. Research and Jev candidates on the same bar/side share that identity.

## 4. Reverse proxy

Use TLS. A minimal production reverse proxy should:

- terminate HTTPS;
- restrict request body size;
- redact webhook-token paths from logs;
- set sane read/connect timeouts;
- expose only port 443 publicly;
- keep SQLite volume and `.env` off public mounts.

## 5. Health

```bash
curl https://YOUR_HOST/health
```

Expected fields include event, snapshot, open-shadow and closed-shadow counts.

## 6. Jev

Fetch the compact adjudication object:

```bash
GET /jev/request/{event_id}
```

Send that object to the Jev client/model of choice. Return the typed decision to:

```
POST /webhook/jev/YOUR_JEV_WEBHOOK_TOKEN
```

An ACCEPT is not sufficient by itself. The gateway also requires:

- direction equal to Pine side;
- direction probability >= configured threshold;
- setup probability >= configured threshold;
- liquidity_safe = true;
- toxic_flow = false;
- execution environment favorable or marginal;
- Pine candidate still satisfies deterministic A+ score and R gates.

Only then can a **shadow** trade be armed.

## 7. Research dataset

After collecting candidates:

1. export TradingView alert payloads from the database using `research/build_dataset.py`;
2. separately label price outcomes with `research/label_candidates.py`;
3. rebuild the joined dataset with the label file;
4. run `research/validate.py`;
5. only after adequate data, run `research/train_meta.py`.

The final chronological test segment is not an optimization surface. If you inspect it and change the strategy, it becomes research data and you need a new future holdout.

## 8. Backups

Back up the SQLite database using SQLite's online backup semantics, not a blind copy while WAL writes are active. For long-running collection, schedule regular database snapshots and periodically export immutable event/enrichment datasets.

## 9. Promotion gates

No live execution module should be added until:

- Pine compile = 0 errors / 0 warnings;
- service CI is green;
- sufficient candidate sample;
- frozen chronological OOS;
- execution-cost model;
- shadow period;
- no unresolved data-quality/staleness failures;
- explicit risk policy independent of the model.
