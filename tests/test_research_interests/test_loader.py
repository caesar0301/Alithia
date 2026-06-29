"""Tests for the research-interests Markdown loader (RFC-010 §7)."""

from pathlib import Path

from alithia_agent.research_interests import load_research_interests


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_file_parsed_with_body_stripped(tmp_path):
    _write(
        tmp_path / "multimodal.md",
        (
            "---\ntitle: Multimodal\ntags: [clip, siglip]\n"
            "notes: prioritize benchmarks\n---\n\n## Body\ncross-modal alignment\n"
        ),
    )
    units = load_research_interests(tmp_path)
    assert len(units) == 1
    u = units[0]
    assert u.title == "Multimodal"
    assert u.tags == ["clip", "siglip"]
    assert u.notes == "prioritize benchmarks"
    assert "cross-modal alignment" in u.body
    assert "---" not in u.body  # frontmatter stripped


def test_no_frontmatter_skipped(tmp_path, caplog):
    _write(tmp_path / "plain.md", "# Just a markdown doc\nNo frontmatter here.")
    units = load_research_interests(tmp_path)
    assert units == []


def test_malformed_yaml_skipped(tmp_path):
    _write(tmp_path / "bad.md", "---\ntitle: [unterminated\n---\n\nbody")
    assert load_research_interests(tmp_path) == []


def test_missing_title_skipped(tmp_path):
    _write(tmp_path / "notitle.md", "---\ntags: [foo]\n---\n\nbody")
    assert load_research_interests(tmp_path) == []


def test_zotero_subdir_included_recursively(tmp_path):
    _write(tmp_path / "hand.md", "---\ntitle: Hand-written\n---\n\nbody text here")
    _write(
        tmp_path / "zotero" / "ABC123.md",
        "---\ntitle: Synced\nsource: zotero\nzotero_item_key: ABC123\n---\n\nabstract",
    )
    units = load_research_interests(tmp_path)
    titles = {u.title for u in units}
    assert titles == {"Hand-written", "Synced"}
    synced = next(u for u in units if u.title == "Synced")
    assert synced.source == "zotero"
    assert synced.zotero_item_key == "ABC123"


def test_missing_directory_returns_empty(tmp_path):
    assert load_research_interests(tmp_path / "does_not_exist") == []


def test_empty_directory_returns_empty(tmp_path):
    assert load_research_interests(tmp_path) == []


def test_stable_path_sorted_order(tmp_path):
    # Create files in non-sorted order.
    for name in ["c-third.md", "a-first.md", "b-second.md"]:
        _write(tmp_path / name, f"---\ntitle: {name}\n---\n\nbody")
    units = load_research_interests(tmp_path)
    assert [u.title for u in units] == ["a-first.md", "b-second.md", "c-third.md"]


def test_tags_list_parsed_correctly(tmp_path):
    _write(tmp_path / "t.md", "---\ntitle: T\ntags: [alpha, beta, gamma]\n---\n\nbody")
    units = load_research_interests(tmp_path)
    assert units[0].tags == ["alpha", "beta", "gamma"]


def test_weight_and_categories_parsed(tmp_path):
    _write(
        tmp_path / "w.md",
        "---\ntitle: W\nweight: 2.5\narxiv_categories: [cs.CV, cs.CL]\n---\n\nbody",
    )
    u = load_research_interests(tmp_path)[0]
    assert u.weight == 2.5
    assert u.arxiv_categories == ["cs.CV", "cs.CL"]


def test_mixed_valid_and_invalid_only_returns_valid(tmp_path):
    _write(tmp_path / "good.md", "---\ntitle: Good\n---\n\nbody")
    _write(tmp_path / "bad.md", "---\ntitle: [bad\n---\n\nbody")
    _write(tmp_path / "notitle.md", "---\ntags: [x]\n---\n\nbody")
    units = load_research_interests(tmp_path)
    assert len(units) == 1
    assert units[0].title == "Good"
