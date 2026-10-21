import logging
from groq import Groq
from groq import AsyncGroq
from groq import APIConnectionError, APIStatusError, RateLimitError
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )

            content = response.choices[0].message.content

            if content is None:
                raise ValueError("The LLM returned an empty response.")

            return content

        except RateLimitError:
            logger.warning("Groq rate limit reached.")
            raise

        except APIConnectionError:
            logger.exception("Could not connect to Groq.")
            raise

        except APIStatusError as exc:
            logger.error("Groq API returned HTTP status %s.", exc.status_code)
            raise