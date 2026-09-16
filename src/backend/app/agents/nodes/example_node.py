from src.backend.app.agents.state import AgentState
from src.backend.app.infrastructure.llm.client import get_llm


async def analyze_node(state: AgentState) -> AgentState:
    query = state.get("query", "")
    if not query:
        return {**state, "error": "Query is required"}
    return {**state, "analysis": f"Analyzing: {query}"}


async def respond_node(state: AgentState) -> AgentState:
    llm = get_llm()
    result = await llm.ainvoke(state.get("query", ""))
    return {**state, "response": str(result.content)}
