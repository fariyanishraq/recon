"""API layer: HTTP contracts over thin handlers.

Route handlers validate requests and delegate to application use cases;
they never call browser, model, or database internals directly.
"""
