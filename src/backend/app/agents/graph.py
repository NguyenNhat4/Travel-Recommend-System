from langgraph.graph import END, StateGraph

from src.backend.app.agents.nodes.example_node import analyze_node, respond_node
from src.backend.app.agents.state import AgentState


def should_continue(state: AgentState) -> str:
    if state.get("error"):
        return END
    return "respond"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("analyze", analyze_node)
    graph.add_node("respond", respond_node)
    graph.set_entry_point("analyze")
    graph.add_conditional_edges("analyze", should_continue)
    graph.add_edge("respond", END)
    return graph.compile()


agent = build_graph()
