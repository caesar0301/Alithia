"""
Tests for _describe_result milestone generation in agent.py.

Verifies that info_messages from nodes are properly surfaced as
human-readable milestones, including skip/warning messages.
"""

from alithia.paperscout.agent import _describe_result


class TestDescribeResultWithInfoMessages:
    """_describe_result surfaces info_messages when present."""

    def test_data_collection_with_skip_info(self):
        result = {
            "discovered_papers": [],
            "current_step": "data_collection_complete",
            "info_messages": ["Date range 20250224-20250224 already processed, skipped"],
        }
        msg = _describe_result("data_collection", result)
        assert "already processed" in msg

    def test_data_collection_without_info_shows_count(self):
        result = {
            "discovered_papers": [1, 2, 3],
            "current_step": "data_collection_complete",
        }
        msg = _describe_result("data_collection", result)
        assert "3 papers" in msg

    def test_data_collection_empty_no_info(self):
        result = {
            "discovered_papers": [],
            "current_step": "data_collection_complete",
        }
        msg = _describe_result("data_collection", result)
        assert msg == "No new papers to process"

    def test_communication_with_skip_info(self):
        result = {
            "current_step": "workflow_complete",
            "info_messages": ["Notification already sent for 2025-02-24, skipped (exactly-once)"],
        }
        msg = _describe_result("communication", result)
        assert "exactly-once" in msg
        assert "2025-02-24" in msg

    def test_communication_without_info_complete(self):
        result = {"current_step": "workflow_complete"}
        msg = _describe_result("communication", result)
        assert msg == "Workflow complete"

    def test_communication_error(self):
        result = {"current_step": "communication_error"}
        msg = _describe_result("communication", result)
        assert msg == "Email delivery failed"

    def test_profile_analysis_ok(self):
        result = {"current_step": "profile_analysis_complete"}
        assert _describe_result("profile_analysis", result) == "Profile validated"

    def test_profile_analysis_error(self):
        result = {"current_step": "profile_validation_error"}
        assert _describe_result("profile_analysis", result) == "Profile validation failed"

    def test_relevance_assessment_with_papers(self):
        result = {"scored_papers": [1, 2], "current_step": "relevance_assessment_complete"}
        msg = _describe_result("relevance_assessment", result)
        assert "2 papers" in msg

    def test_relevance_assessment_empty(self):
        result = {"scored_papers": [], "current_step": "relevance_assessment_complete"}
        assert _describe_result("relevance_assessment", result) == "No papers to rank"

    def test_content_generation_success(self):
        result = {"email_content": "html...", "current_step": "content_generation_complete"}
        assert _describe_result("content_generation", result) == "Generated summaries & recommendations"

    def test_content_generation_error(self):
        result = {"current_step": "content_generation_error"}
        assert _describe_result("content_generation", result) == "Content generation failed"

    def test_content_generation_empty(self):
        result = {"current_step": "content_generation_complete"}
        assert _describe_result("content_generation", result) == "No content to generate"

    def test_info_messages_takes_last_entry(self):
        """When multiple info_messages exist, use the last one."""
        result = {
            "discovered_papers": [],
            "current_step": "data_collection_complete",
            "info_messages": ["First message", "Second message"],
        }
        msg = _describe_result("data_collection", result)
        assert msg == "Second message"

    def test_empty_info_messages_falls_through(self):
        """Empty info_messages list should fall through to normal logic."""
        result = {
            "discovered_papers": [1],
            "current_step": "data_collection_complete",
            "info_messages": [],
        }
        msg = _describe_result("data_collection", result)
        assert "1 papers" in msg

    def test_unknown_node(self):
        result = {"current_step": "some_step"}
        assert _describe_result("unknown_node", result) == "some_step"
