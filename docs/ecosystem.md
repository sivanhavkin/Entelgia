<div style="display: flex; align-items: center; justify-content: space-between;">
  <img src="../Assets/entelgia-logo.png" alt="Entelgia Logo" width="120" style="margin: 0;"/>
  <h1 style="flex-grow: 1; text-align: center; font-size: 2.5em; font-weight: bold; margin: 0;">Ecosystem</h1>
  <div style="width: 120px;" aria-hidden="true"></div>
</div>

This document lists optional external indexes and ecosystem references.

## External Indexes

Entelgia may be indexed by third-party open-source AI agent registries for discoverability purposes.
These listings are external and not required for using or understanding the core system.

## Community Proposals

The following proposals were submitted by external contributors and are documented here for transparency and future reference.
They are **not merged into the core system** and do not reflect current project scope or roadmap.

### AI Agent Marketplace Index & Router Support (PR #3)

An external proposal suggested indexing Entelgia in a third-party AI Agent marketplace and adding related badges or routing metadata.

- Scope: External indexing / discoverability
- Nature: Marketplace & registry integration
- Status: Not merged (out of current scope)

The project currently prioritizes a **research-focused CoreMind architecture** with minimal external dependencies.
This proposal is documented for reference only.

---

## Web Research Dependencies (v2.8.0)

The optional Web Research Module introduces two new runtime dependencies:

| Package | Purpose | Version |
|---------|---------|---------|
| `beautifulsoup4` | HTML parsing and text extraction from web pages | ≥ 4.12.0 |
| `requests` | HTTP GET/POST to DuckDuckGo and target URLs | ≥ 2.31.0 (already required) |

These are declared in `requirements.txt`.  The module itself imports `bs4` lazily
and logs a warning (rather than raising) if `beautifulsoup4` is not installed, so
the rest of the system continues to function.

The search backend is **DuckDuckGo HTML** (`https://html.duckduckgo.com/html/`) — no
API key is required and no third-party SDK is added to the dependency tree.
