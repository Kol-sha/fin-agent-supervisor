from langgraph.graph import StateGraph, END

from graph.state import AgentState
from agents import stock_agent_node, fx_agent_node
from supervisor import supervisor_node, route_from_supervisor


def build_graph():
    """Собирает граф мультиагентной системы."""
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("stock_agent", stock_agent_node)
    workflow.add_node("fx_agent", fx_agent_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "stock": "stock_agent",
            "fx": "fx_agent",
            "finish": END,
        },
    )

    workflow.add_edge("stock_agent", "supervisor")
    workflow.add_edge("fx_agent", "supervisor")

    return workflow.compile()