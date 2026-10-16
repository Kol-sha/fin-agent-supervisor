from config import llm
from .prompt import SUPERVISOR_PROMPT


def supervisor_node(state):
    """Решает, какому агенту передать запрос."""
    if state.get("done"):
        return {"next": "finish"}

    question = state["question"]

    response = llm.invoke([
        {"role": "system", "content": SUPERVISOR_PROMPT},
        {"role": "user", "content": question},
    ])

    decision = response.content.strip().lower()

    if "stock" in decision:
        next_agent = "stock"
    elif "fx" in decision:
        next_agent = "fx"
    else:
        next_agent = "finish"

    print(f"[Supervisor] решение: {next_agent}")
    return {
        "next": next_agent,
        "first_decision": next_agent,
    }


def route_from_supervisor(state):
    """Conditional edge: куда идти после supervisor."""
    return state["next"]