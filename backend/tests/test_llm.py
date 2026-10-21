import asyncio

from app.services.ai.llm import LLMService


async def main():
    llm = LLMService()

    messages = [
        {
            "role": "system",
            "content": "You are a helpful HR assistant. Answer concisely.",
        },
        {
            "role": "user",
            "content": "What is an HRMS?",
        },
    ]

    answer = await llm.chat(messages)
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())