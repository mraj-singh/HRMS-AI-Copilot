
from unittest.mock import patch

import httpx
import pytest
from groq import RateLimitError

from app.services.ai.llm import LLMService


@pytest.mark.asyncio
async def test_rate_limit_error_propagates():
    llm = LLMService()

    rate_limit_error = RateLimitError(
        "Simulated rate limit",
        response=httpx.Response(
            429,
            request=httpx.Request(
                "POST", "https://example.com"
            ),
        ),
        body=None,
    )

    with patch.object(
        llm.client.chat.completions,
        "create",
        side_effect=rate_limit_error,
    ):
        with pytest.raises(RateLimitError):
            await llm.chat([
                {"role": "user", "content": "Test"}
            ])
