from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ItineraryContext(BaseModel):
    language: Literal["vi", "en"] = "vi"


class ItineraryRequestModel(BaseModel):
    conversationId: str | None = None
    message: str | None = Field(default=None, min_length=1, max_length=1000)
    intentOverride: dict[str, Any] | None = None
    context: ItineraryContext | None = None

    @model_validator(mode="after")
    def requires_message_or_override(self):
        if self.intentOverride is not None and not self.conversationId:
            raise ValueError("intentOverride requires conversationId")
        if self.message:
            return self
        if self.conversationId and self.intentOverride:
            return self
        raise ValueError("message or conversationId with intentOverride is required")
