from unittest.mock import MagicMock, patch

import pytest

from alithia.researcher.connection import (
    EmailConnection,
    GithubConnection,
    GoogleScholarConnection,
    LLMConnection,
    XConnection,
    ZoteroConnection,
)
from alithia.researcher.profile import ResearcherProfile
from alithia.utils.llm_utils import get_llm_client


@pytest.mark.unit
def test_get_llm_sets_env_and_model():
    profile = ResearcherProfile(
        email="test@example.com",
        zotero=ZoteroConnection(zotero_id="z", zotero_key="k"),
        llm=LLMConnection(openai_api_key="secret", openai_api_base="http://base", model_name="gpt-x"),
        email_notification=EmailConnection(
            smtp_server="smtp.test.com",
            smtp_port=587,
            sender="test@example.com",
            sender_password="test_pass",
        ),
        github=GithubConnection(github_username="test_user", github_token="test_token"),
        google_scholar=GoogleScholarConnection(scholar_id="test_id", serpapi_key="test_token"),
        x=XConnection(x_username="test_user", x_token="test_token"),
    )

    fake_client = MagicMock()
    fake_client.chat_model = "gpt-x"
    with patch("noesium.core.llm.get_llm_client", return_value=fake_client) as mock_get:
        result = get_llm_client(profile.llm)

    assert result.chat_model == "gpt-x"
    # called with provider openai and chat_model
    mock_get.assert_called_with(provider="openai", api_key="secret", base_url="http://base", chat_model="gpt-x")
