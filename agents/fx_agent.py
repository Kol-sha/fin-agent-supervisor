from tools.financial import get_fx_rate


def fx_agent_node(state):
    """Агент для вопросов о валютах."""
    question = state["question"]
    result = get_fx_rate.invoke({"pair": question})
    return {
        "messages": [{"role": "assistant", "content": f"[FX Agent] {result}"}],
        "done": True,
    }