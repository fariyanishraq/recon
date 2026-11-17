# CSIP Extraction Service (crawl4ai in Linux Docker)

Why: this machine's Windows Application Control policy blocks crawl4ai's
compiled dependencies (`xxhash`, `numpy`) from loading on the host. The
extraction stage therefore runs inside a Linux container, where no such
policy applies. (The alternative — an App Control exclusion for this
project's `.venv` — requires a manual admin policy change and is not
implemented.)

## Run

```powershell
docker compose -f containers/extraction/docker-compose.yml up -d --build
```

The service binds **loopback only** (`127.0.0.1:8100`) — never publicly
reachable (goals G8).

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | liveness |
| `POST /extract_raw` | extract from **already-captured** artifact HTML (no network). Preferred path: extraction from stored artifacts keeps acquisition governed. |
| `POST /extract` | fetch + extract a URL. The caller MUST only pass URLs authorized by an approved SourceProfile/plan — this service performs no policy checks itself. |

Both return deterministic structured JSON (title, markdown, metadata,
links). The LLM never performs extraction or persistence.

## Notes

- HTTP + LXML strategies only (no Playwright/Chromium in the image).
  Browser-dependent strategies require policy-approved `browser_pages`
  methods first.
- Smoke test without the server: `docker run --rm csip-extraction:latest python extractor.py --selftest`
