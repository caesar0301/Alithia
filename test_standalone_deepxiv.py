#!/usr/bin/env python3
"""Test standalone deepxiv plugin functionality."""

import importlib.util
import sys


def test_imports():
    """Test that deepxiv plugin can be imported without soothe.toolkits."""
    print("=" * 60)
    print("Test 1: Import deepxiv plugin")
    print("=" * 60)

    try:
        from alithia_agent.plugins.deepxiv import DeepxivPlugin  # noqa: F401

        print("✓ DeepxivPlugin imported successfully")

        from alithia_agent.plugins.deepxiv.toolkit import (  # noqa: F401
            DeepxivGetFullPaperTool,
            DeepxivPaperBriefTool,
            DeepxivPaperMetadataTool,
            DeepxivReadSectionTool,
            DeepxivSearchTool,
            DeepxivToolkit,
            DeepxivTrendingTool,
            DeepxivWebsearchTool,
        )

        print("✓ All toolkit components imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_no_soothe_references():
    """Verify no references to soothe.toolkits.deepxiv."""
    print("\n" + "=" * 60)
    print("Test 2: Check for soothe.toolkits references")
    print("=" * 60)

    import inspect

    from alithia_agent.plugins.deepxiv import DeepxivPlugin, toolkit

    # Check source code for references
    toolkit_source = inspect.getsource(toolkit)
    plugin_source = inspect.getsource(DeepxivPlugin)

    if "soothe.toolkits" in toolkit_source or "soothe.toolkits" in plugin_source:
        print("✗ Found references to soothe.toolkits")
        return False

    print("✓ No references to soothe.toolkits found")
    return True


def test_toolkit_initialization():
    """Test that toolkit can be initialized."""
    print("\n" + "=" * 60)
    print("Test 3: Toolkit initialization")
    print("=" * 60)

    try:
        from alithia_agent.plugins.deepxiv.toolkit import DeepxivToolkit

        toolkit = DeepxivToolkit(token="test_token", timeout=30, max_retries=2)
        print("✓ DeepxivToolkit initialized successfully")
        print(f"  - Token: {toolkit.token}")
        print(f"  - Timeout: {toolkit.timeout}")
        print(f"  - Max retries: {toolkit.max_retries}")

        # Get tools (without initializing reader to avoid SDK dependency)
        tools = toolkit.get_tools()
        print(f"✓ Retrieved {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}")

        return True
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_plugin_initialization():
    """Test that plugin can be initialized."""
    print("\n" + "=" * 60)
    print("Test 4: Plugin initialization")
    print("=" * 60)

    try:
        from alithia_agent.plugins.deepxiv import DeepxivPlugin

        plugin = DeepxivPlugin()
        print("✓ DeepxivPlugin instantiated successfully")

        # Check manifest
        manifest = plugin._plugin_manifest
        print("✓ Plugin manifest:")
        print(f"  - Name: {manifest.name}")
        print(f"  - Version: {manifest.version}")
        print(f"  - Description: {manifest.description}")

        return True
    except Exception as e:
        print(f"✗ Plugin initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_tool_schemas():
    """Test that tool input schemas are properly defined."""
    print("\n" + "=" * 60)
    print("Test 5: Tool input schemas")
    print("=" * 60)

    try:
        from alithia_agent.plugins.deepxiv.toolkit import (
            DeepxivGetFullPaperInput,
            DeepxivPaperBriefInput,
            DeepxivPaperMetadataInput,
            DeepxivReadSectionInput,
            DeepxivSearchInput,
            DeepxivTrendingInput,
            DeepxivWebsearchInput,
        )

        schemas = [
            ("DeepxivSearchInput", DeepxivSearchInput),
            ("DeepxivPaperBriefInput", DeepxivPaperBriefInput),
            ("DeepxivPaperMetadataInput", DeepxivPaperMetadataInput),
            ("DeepxivReadSectionInput", DeepxivReadSectionInput),
            ("DeepxivGetFullPaperInput", DeepxivGetFullPaperInput),
            ("DeepxivTrendingInput", DeepxivTrendingInput),
            ("DeepxivWebsearchInput", DeepxivWebsearchInput),
        ]

        for name, schema_class in schemas:
            # Verify schema has fields
            fields = schema_class.model_fields
            print(f"✓ {name} has {len(fields)} fields: {list(fields.keys())}")

        return True
    except Exception as e:
        print(f"✗ Schema validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_helper_functions():
    """Test helper functions."""
    print("\n" + "=" * 60)
    print("Test 6: Helper functions")
    print("=" * 60)

    try:
        # Test _resolve_env
        import os

        from alithia_agent.plugins.deepxiv.toolkit import (
            _author_display_name,
            _format_author_names,
            _preview,
            _resolve_env,
            resolve_deepxiv_token,
        )

        os.environ["TEST_TOKEN"] = "test_value_123"
        result = _resolve_env("${TEST_TOKEN}")
        print(f"✓ _resolve_env('${{TEST_TOKEN}}') = '{result}'")
        assert result == "test_value_123"

        # Test _preview
        preview = _preview("This is a very long string that should be truncated", max_len=20)
        print(f"✓ _preview() truncates properly: '{preview}'")
        assert len(preview) <= 20

        # Test _author_display_name
        assert _author_display_name("John Doe") == "John Doe"
        assert _author_display_name({"name": "Jane Doe"}) == "Jane Doe"
        print("✓ _author_display_name() works correctly")

        # Test _format_author_names
        names = _format_author_names(["Alice", "Bob", "Charlie"], limit=2)
        assert "et al." in names
        print(f"✓ _format_author_names() truncates properly: '{names}'")

        # Test resolve_deepxiv_token
        token = resolve_deepxiv_token(None)
        print(f"✓ resolve_deepxiv_token(None) returns: {'None' if token is None else token}")

        return True
    except Exception as e:
        print(f"✗ Helper function test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\nTesting standalone deepxiv plugin functionality")
    print("=" * 60)

    # Check if deepxiv_sdk is installed
    sdk_installed = importlib.util.find_spec("deepxiv_sdk") is not None
    print(f"deepxiv_sdk installed: {sdk_installed}")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("No soothe references", test_no_soothe_references()))
    results.append(("Toolkit initialization", test_toolkit_initialization()))
    results.append(("Plugin initialization", test_plugin_initialization()))
    results.append(("Tool schemas", test_tool_schemas()))
    results.append(("Helper functions", test_helper_functions()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("✓ Plugin works independently without referencing soothe.toolkits.deepxiv")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
