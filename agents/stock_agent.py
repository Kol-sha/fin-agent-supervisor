from tools.financial import get_stock_quote


def stock_agent_node(state):
    """Агент для вопросов об акциях."""
    question = state["question"]
    result = get_stock_quote.invoke({"ticker": question})
    return {
        "messages": [{"role": "assistant", "content": f"[Stock Agent] {result}"}],
        "done": True,
    }