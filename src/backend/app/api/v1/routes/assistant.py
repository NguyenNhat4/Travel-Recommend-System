from fastapi import APIRouter, HTTPException

from src.backend.app.agents.graph import agent
from src.backend.app.domain.itinerary.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with the current itinerary-agent skeleton."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
async def agent_status():
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
