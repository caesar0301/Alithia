# DeepXiv Migration: From Soothe to Alithia

**Status**: Completed  
**Date**: 2026-06-18  
**Author**: Xiaming Chen  

---

## Executive Summary

The **DeepXiv plugin** has been migrated from the `soothe.toolkits` package to `alithia_agent.plugins.deepxiv`. This migration brings academic paper search and progressive reading capabilities directly into the Alithia agent codebase, eliminating external dependencies on the soothe framework for this functionality.

---

## Migration Details

### Previous Location
```
soothe.toolkits.deepxiv
```

### New Location
```
alithia_agent.plugins.deepxiv
```

### Package Structure

```
alithia_agent/
├── plugins/
│   └── deepxiv/
│       ├── __init__.py          # DeepxivPlugin class with manifest
│       └── toolkit.py           # DeepxivToolkit with LangChain tools
```

---

## What Changed

### 1. Codebase Organization

**Before (in soothe):**
- DeepXiv toolkit was part of the soothe framework
- Located at `soothe.toolkits.deepxiv`
- Managed as part of the soothe package

**After (in alithia):**
- DeepXiv is now a first-class Alithia plugin
- Located at `alithia_agent.plugins.deepxiv`
- Self-contained toolkit within Alithia's plugin system

### 2. Dependencies

**Added to alithia (pyproject.toml):**
```toml
dependencies = [
    # ... existing dependencies ...
    "deepxiv-sdk>=0.1.0",
    "httpx>=0.25.0",
]
```

**Removed external dependency:**
- No longer depends on `soothe.toolkits` for DeepXiv functionality

### 3. Plugin Registration

**Entry Point Registration:**
```toml
[project.entry-points."soothe.plugins"]
paperscout = "alithia_agent.paperscout:PaperScoutPlugin"
paperlens = "alithia_agent.paperlens:PaperLensPlugin"
# Note: DeepXiv is registered via manual fallback, not entry point
```

**Manual Registration (in plugin_registration.py):**
```python
from alithia_agent.plugins.deepxiv import DeepxivPlugin

registry.register(
    getattr(DeepxivPlugin, "_plugin_manifest"),
    source="config",
    priority=30,
)
```

### 4. Import Paths

**Old imports (no longer valid):**
```python
from soothe.toolkits.deepxiv import DeepxivToolkit
from soothe.toolkits.deepxiv import DeepXivPlugin
```

**New imports:**
```python
from alithia_agent.plugins.deepxiv import DeepxivPlugin
from alithia_agent.plugins.deepxiv.toolkit import (
    DeepxivToolkit,
    DeepxivSearchTool,
    DeepxivPaperBriefTool,
    DeepxivPaperMetadataTool,
    DeepxivReadSectionTool,
    DeepxivGetFullPaperTool,
    DeepxivTrendingTool,
    DeepxivWebsearchTool,
)
```

---

## Plugin Functionality

The DeepXiv plugin provides the following tools for academic paper operations:

| Tool | Description |
|------|-------------|
| `deepxiv_search` | Semantic paper search across arXiv, bioRxiv, medRxiv, PMC |
| `deepxiv_paper_brief` | Quick summary (TLDR, keywords, citations) |
| `deepxiv_paper_metadata` | Paper structure overview |
| `deepxiv_read_section` | Read specific sections for token efficiency |
| `deepxiv_get_full_paper` | Complete paper content |
| `deepxiv_trending` | Trending papers based on social signals |
| `deepxiv_websearch` | Web search (higher token cost) |

---

## Configuration

### Plugin Manifest

```python
_plugin_manifest = type(
    "PluginManifest",
    (),
    {
        "name": "deepxiv",
        "version": "1.0.0",
        "description": "Academic paper search and progressive reading toolkit",
        "dependencies": ["langchain-core>=0.1.0", "deepxiv-sdk>=0.1.0"],
        "trust_level": "standard",
    },
)()
```

### Configuration Loading

The plugin loads configuration from:
1. **Soothe context** (if available): `context.config.deepxiv`
2. **Environment variables**: Auto-registration via deepxiv-sdk

**Configuration parameters:**
- `token`: DeepXiv API token (optional, uses auto-registration if not provided)
- `timeout`: Request timeout in seconds (default: 60)
- `max_retries`: Maximum retry attempts (default: 3)

---

## Integration with Alithia

### 1. Soothe Framework Integration

DeepXiv integrates with the soothe framework through:

**Entry Point Registration:**
- Registered via `soothe.plugins` entry points in `pyproject.toml`
- Or via manual fallback in `plugin_registration.py`

**Plugin Lifecycle:**
- `on_load(context)`: Initializes toolkit with configuration
- `get_tools()`: Returns LangChain BaseTool instances

### 2. Usage in Subagents

DeepXiv tools are available to all soothe subagents (PaperScout, PaperLens) through the soothe plugin system.

**Example usage in a subagent:**
```python
from langchain_core.tools import BaseTool

def get_tools(self) -> list[BaseTool]:
    """Get DeepXiv tools from plugin registry."""
    from soothe.plugin.global_registry import get_registered_tools
    return get_registered_tools("deepxiv")
```

### 3. Direct Toolkit Usage

For direct use without soothe framework:

```python
from alithia_agent.plugins.deepxiv.toolkit import DeepxivToolkit

# Initialize toolkit
toolkit = DeepxivToolkit(
    token="your-api-token",  # optional
    timeout=60,
    max_retries=3,
)

# Get LangChain tools
tools = toolkit.get_tools()

# Use tools
search_tool = tools[0]
result = await search_tool.ainvoke({
    "query": "transformer architectures",
    "limit": 10
})
```

---

## Migration Rationale

### Why Migrate DeepXiv to Alithia?

1. **Domain Alignment**: DeepXiv provides academic paper search capabilities specifically for research workflows, which is Alithia's core domain.

2. **Reduced Dependencies**: Removes dependency on soothe.toolkits, making Alithia more self-contained.

3. **Customization**: Allows Alithia-specific customizations without requiring changes to the soothe framework.

4. **Simplified Testing**: Test suite can run independently without requiring the full soothe framework.

5. **Clear Ownership**: Alithia team can maintain and evolve DeepXiv integration without coordinating with soothe maintainers.

### What Remains in Soothe

The soothe framework continues to provide:
- Plugin infrastructure (`@plugin`, `@subagent` decorators)
- Goal engine and orchestration
- Storage protocols (`AsyncPersistStore`)
- Event system and observability
- Configuration management

---

## Testing

### Standalone Testing

A standalone test script verifies the migration:

```bash
python test_standalone_deepxiv.py
```

**Test coverage:**
1. Import verification without soothe.toolkits references
2. Plugin initialization and manifest validation
3. Toolkit initialization with configuration
4. Tool instantiation and availability

### Unit Tests

Located at `tests/unit/plugins/test_deepxiv.py`

---

## Breaking Changes

### For Users

**No breaking changes** - functionality remains the same from user perspective.

### For Developers

**Breaking changes:**
- Import paths changed from `soothe.toolkits.deepxiv` to `alithia_agent.plugins.deepxiv`
- Configuration must be provided through Alithia's config system, not soothe.toolkits config

**Non-breaking:**
- All tool names remain the same
- Tool functionality unchanged
- API signatures unchanged

---

## Backwards Compatibility

### Temporary Compatibility Layer

If needed, a compatibility shim can be added:

```python
# In soothe/toolkits/deepxiv.py (if maintaining backwards compatibility)
from alithia_agent.plugins.deepxiv import DeepxivPlugin
from alithia_agent.plugins.deepxiv.toolkit import DeepxivToolkit

__all__ = ["DeepxivPlugin", "DeepxivToolkit"]
```

However, this is **not recommended** - direct migration to new import paths is preferred.

---

## Future Considerations

### Potential Enhancements

1. **Caching**: Add local caching for paper metadata and search results
2. **Batch Operations**: Support batch paper retrieval for efficiency
3. **Custom Ranking**: Alithia-specific ranking algorithms for search results
4. **Integration with Zotero**: Direct export of papers to Zotero library

### Maintenance

- DeepXiv plugin will be maintained as part of Alithia codebase
- Updates to deepxiv-sdk dependency managed through pyproject.toml
- Plugin follows Alithia's release cycle, not soothe's

---

## References

- **RFC-007-plugin-integration**: Soothe framework integration contracts
- **RFC-009-soothe-integration**: Soothe integration architecture
- **Test Suite**: `test_standalone_deepxiv.py`
- **Unit Tests**: `tests/unit/plugins/test_deepxiv.py`

---

## Changelog

### 2026-06-18
- Initial migration documentation created
- DeepXiv plugin migrated from `soothe.toolkits` to `alithia_agent.plugins.deepxiv`
- Added `deepxiv-sdk>=0.1.0` and `httpx>=0.25.0` to dependencies
- Updated plugin registration to include DeepXiv
- Created standalone test suite for verification