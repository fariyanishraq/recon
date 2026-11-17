"""CSIP application entrypoint (safe local mode)."""

from __future__ import annotations

import uvicorn

from csip.api.app import create_app
from csip.infrastructure.config.settings import load_settings
from csip.infrastructure.observability.logging import configure_logging

app = create_app(load_settings())


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    # Local/dev entrypoint. Production deployment owns its own process model.
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
