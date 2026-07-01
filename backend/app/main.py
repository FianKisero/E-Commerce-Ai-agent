from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_workflow

inventory_state: dict[str, int] = {
    "AeroFrame Laptop 14": 12,
    "Nova Monitor 27": 5,
}
cart_state: dict[str, int] = {}

app = FastAPI(title="E-Commerce AI Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WorkflowRequest(BaseModel):
    query: str
    approval: str | None = None


class CartItemRequest(BaseModel):
    sku: str
    quantity: int = 1


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ecommerce-agent"}


@app.post("/workflow")
def workflow(request: WorkflowRequest) -> dict:
    state, events = run_workflow(request.query, request.approval)
    return {"state": state, "events": events}


@app.get("/mcp/inventory")
def get_inventory() -> dict:
    return {"inventory": inventory_state}


@app.post("/mcp/cart/add")
def add_to_cart(request: CartItemRequest) -> dict:
    if request.quantity <= 0:
        return {"error": "Quantity must be positive"}

    current_stock = inventory_state.get(request.sku, 0)
    if current_stock < request.quantity:
        return {"error": "Insufficient stock", "available": current_stock}

    inventory_state[request.sku] = current_stock - request.quantity
    cart_state[request.sku] = cart_state.get(request.sku, 0) + request.quantity
    return {"status": "added", "cart": cart_state, "inventory": inventory_state}


@app.get("/mcp/cart")
def get_cart() -> dict:
    return {"cart": cart_state}


@app.post("/mcp/cart/checkout")
def checkout_cart() -> dict:
    cart_state.clear()
    return {"status": "checked_out", "cart": cart_state}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        payload = await websocket.receive_json()
        query = payload.get("query", "laptop for remote teams")
        approval = payload.get("approval")
        _, events = run_workflow(query, approval)

        for event in events:
            await websocket.send_json(event)

        await websocket.close()
    except WebSocketDisconnect:
        return
