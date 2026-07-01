from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_workflow

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ecommerce-agent"}


@app.post("/workflow")
def workflow(request: WorkflowRequest) -> dict:
    state, events = run_workflow(request.query, request.approval)
    return {"state": state, "events": events}


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
