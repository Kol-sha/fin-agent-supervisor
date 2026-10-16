import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    question: str
    messages: Annotated[list, operator.add]
    next: str
    done: bool
    first_decision: str