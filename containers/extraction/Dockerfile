# CSIP extraction stage (crawl4ai) — runs in Linux Docker because this
# machine's Windows Application Control policy blocks crawl4ai's compiled
# dependencies (xxhash, numpy) on the host.
FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "crawl4ai==0.9.5" \
    "fastapi==0.163.1" \
    "uvicorn==0.41.0"

# No Playwright/Chromium: this image uses the HTTP + LXML strategies only.
# Browser-dependent strategies are out of scope until the approved-methods
# policy explicitly authorizes browser_pages.

COPY extractor.py .

EXPOSE 8100

CMD ["uvicorn", "extractor:app", "--host", "0.0.0.0", "--port", "8100"]
