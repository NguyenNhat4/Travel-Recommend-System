from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="User message")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent response")
    analysis: str = Field(default="", description="Internal analysis")
