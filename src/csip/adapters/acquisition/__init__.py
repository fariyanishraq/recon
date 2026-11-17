"""Fixture acquisition adapter: the safe local-mode default.

Serves synthetic, sanitized fixture content with zero network side
effects. It exists so the pipeline can be exercised end-to-end without
touching any live source (Phase 0/1 requirement; goals G2).

Hard rule: this adapter must never be wired to a real network source.
"""
