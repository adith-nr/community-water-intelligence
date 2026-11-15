"""Server-side model factory and an explicit connectivity check for LangGraph."""
import os
from typing import TypedDict

from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph


def create_model() -> ChatGroq:
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("Set GROQ_API_KEY in the backend environment.")
    return ChatGroq(model=os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"),
                    temperature=0, timeout=20, max_retries=0)


class CheckState(TypedDict):
    responded: bool


def check():
    model = create_model()

    def probe(_: CheckState) -> CheckState:
        response = model.invoke("Reply with the single word OK.")
        return {"responded": bool(response.content)}

    graph = StateGraph(CheckState)
    graph.add_node("probe", probe)
    graph.add_edge(START, "probe")
    graph.add_edge("probe", END)
    if not graph.compile().invoke({"responded": False})["responded"]:
        raise RuntimeError("Groq returned an empty response.")


if __name__ == "__main__":
    try:
        check()
    except Exception as error:
        raise SystemExit(f"Groq connectivity check failed ({type(error).__name__}).") from None
    print("Groq responded through LangGraph.")

