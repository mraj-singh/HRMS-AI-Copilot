from pydantic import BaseModel, Field

from typing import Literal

from pydantic import BaseModel, Field


class ConversationHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    history: list[ConversationHistoryMessage] = Field(
        default_factory=list,
        max_length=6,
    )


class ChatSessionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)


class ChatMessageCreate(BaseModel):
    role: str = Field(min_length=3, max_length=20)
    content: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    answer: str