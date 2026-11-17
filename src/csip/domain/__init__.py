"""Domain layer: entities, value objects, invariants.

Dependency rule (project_structure.md section 4.1): this package depends only
on the standard library and stable internal domain primitives. It must never
import FastAPI, Agno, Crawl4AI, Browser-use, Ollama, or Supabase SDKs.
"""
