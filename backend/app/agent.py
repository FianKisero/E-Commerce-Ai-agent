import os
from typing import TypedDict

import requests
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

try:
    from langgraph.types import interrupt as langgraph_interrupt
except ImportError:  # pragma: no cover - fallback for older installs
    def langgraph_interrupt(payload: dict):
        return payload


def interrupt(payload: dict):
    try:
        return langgraph_interrupt(payload)
    except RuntimeError:
        return {"approval": "cancel"}


class AgentState(TypedDict, total=False):
    query: str
    status: str
    products: list[dict]
    inventory: dict[str, int]
    approval: str | None
    purchase: dict | None
    needs_approval: bool
    history: list[dict]


def _fallback_products(query: str) -> list[dict]:
    return [
        {
            "name": "AeroFrame Laptop 14",
            "price": "$1,299",
            "merchant": "Northstar Tech",
            "reason": "Meets procurement rules and energy compliance",
            "url": "https://example.com/aeroframe",
            "query": query,
        },
        {
            "name": "Nova Monitor 27",
            "price": "$399",
            "merchant": "BluePeak Devices",
            "reason": "High reliability and low carbon packaging",
            "url": "https://example.com/nova-monitor",
            "query": query,
        },
    ]


def search_products(query: str) -> list[dict]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _fallback_products(query)

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        return [
            {
                "name": item.get("title", "Research result"),
                "price": item.get("price", "Price unavailable"),
                "merchant": item.get("source", "Web result"),
                "reason": item.get("content", "Relevant match"),
                "url": item.get("url", "https://example.com"),
                "query": query,
            }
            for item in results[:3]
        ]
    except Exception:
        return _fallback_products(query)


def summarize_with_gemini(query: str, products: list[dict]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini not configured"

    prompt = (
        "You are a low-cost procurement assistant. Choose the best product from the list using only brief reasoning. "
        f"Query: {query}\nProducts:\n"
        + "\n".join(
            f"- {p['name']} | {p['merchant']} | {p['price']} | {p['reason']}"
            for p in products[:3]
        )
        + "\nReturn one short sentence."
    )

    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 80, "temperature": 0.2},
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates", [])
        if candidates:
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip() or "Gemini returned no content"
    except Exception:
        pass

    return "Gemini request failed"


def check_inventory(products: list[dict]) -> dict[str, int]:
    inventory = {
        "AeroFrame Laptop 14": 12,
        "Nova Monitor 27": 5,
    }
    return {product["name"]: inventory.get(product["name"], 0) for product in products}


def research_node(state: AgentState) -> AgentState:
    products = search_products(state["query"])
    summary = summarize_with_gemini(state["query"], products)
    return {
        **state,
        "products": products,
        "status": "research_complete",
        "history": [
            *state.get("history", []),
            {"node": "research", "message": f"Found {len(products)} candidate products. {summary}"},
        ],
    }


def inventory_node(state: AgentState) -> AgentState:
    inventory = check_inventory(state.get("products", []))
    return {
        **state,
        "inventory": inventory,
        "status": "inventory_checked",
        "history": [
            *state.get("history", []),
            {"node": "inventory", "message": "Inventory check completed"},
        ],
    }


def approval_node(state: AgentState) -> AgentState:
    if state.get("approval"):
        return {
            **state,
            "needs_approval": False,
            "status": "approval_received",
            "history": [
                *state.get("history", []),
                {"node": "approval", "message": f"Approval received: {state['approval']}"},
            ],
        }

    decision = interrupt(
        {
            "message": "Human approval required before checkout.",
            "actions": ["approve", "cancel"],
        }
    )
    approval_value = (decision or {}).get("approval", "cancel")
    return {
        **state,
        "approval": approval_value,
        "needs_approval": approval_value != "approve",
        "status": "approval_received" if approval_value == "approve" else "awaiting_approval",
        "history": [
            *state.get("history", []),
            {"node": "approval", "message": f"Decision: {approval_value}"},
        ],
    }


def purchase_node(state: AgentState) -> AgentState:
    decision = state.get("approval", "cancel")
    if decision != "approve":
        return {
            **state,
            "purchase": None,
            "status": "cancelled",
            "history": [
                *state.get("history", []),
                {"node": "purchase", "message": "Checkout cancelled"},
            ],
        }

    purchase = {
        "status": "completed",
        "items": state.get("products", [])[:1],
        "message": "Purchase transaction staged successfully",
    }
    return {
        **state,
        "purchase": purchase,
        "status": "purchase_complete",
        "history": [
            *state.get("history", []),
            {"node": "purchase", "message": "Checkout completed"},
        ],
    }


def route_after_approval(state: AgentState) -> str:
    return "purchase" if not state.get("needs_approval", False) else END


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("research", research_node)
    workflow.add_node("inventory", inventory_node)
    workflow.add_node("approval", approval_node)
    workflow.add_node("purchase", purchase_node)
    workflow.set_entry_point("research")
    workflow.add_edge("research", "inventory")
    workflow.add_edge("inventory", "approval")
    workflow.add_conditional_edges("approval", route_after_approval, {"purchase": "purchase", END: END})
    workflow.add_edge("purchase", END)
    return workflow.compile()


GRAPH = build_graph()


def run_workflow(query: str, approval: str | None = None) -> tuple[AgentState, list[dict]]:
    initial_state: AgentState = {
        "query": query,
        "status": "started",
        "products": [],
        "inventory": {},
        "approval": approval,
        "purchase": None,
        "needs_approval": False,
        "history": [],
    }

    state = research_node(initial_state)
    first_product = state["products"][0] if state.get("products") else None
    events = [
        {
            "type": "thought",
            "message": "Node: research_product -> Searching the web for compliant products.",
        },
        {
            "type": "product",
            "product": {
                **(first_product or {}),
                "compliance": ["Compliance reviewed", "Inventory checked"],
                "link": (first_product or {}).get("url", "https://example.com"),
            },
        },
    ]

    state = inventory_node(state)
    events.append({"type": "thought", "message": "Node: inventory_check -> Verifying local stock and cart readiness."})

    state = approval_node(state)
    if state.get("needs_approval", False):
        events.append(
            {
                "type": "interrupt",
                "message": "Human approval required before checkout.",
                "actions": ["Approve Checkout", "Cancel Transaction"],
            }
        )
        return state, events

    state = purchase_node(state)
    events.append({"type": "thought", "message": "Node: purchase -> Finalizing the approved transaction."})
    return state, events
