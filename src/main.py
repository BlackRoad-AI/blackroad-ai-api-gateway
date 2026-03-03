"""
🌐 BlackRoad AI - Unified API Gateway
Routes requests to appropriate AI models across cluster

All requests mentioning @copilot, @lucidia, @blackboxprogramming, @ollama,
or @blackroad are routed directly to local Ollama nodes — no external
providers involved.
"""

import os
import re
import random
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import httpx
from enum import Enum

# Mentions that force Ollama routing — all served from local hardware
OLLAMA_TRIGGER_MENTIONS = {
    "@copilot",
    "@lucidia",
    "@blackboxprogramming",
    "@ollama",
    "@blackroad",
}


def _extract_mentions(message: str) -> set:
    """Return lower-cased @mentions found in *message* (word-boundary safe)."""
    return {m.lower() for m in re.findall(r"(?<!\w)@\w+", message)}


def _should_force_ollama(message: str) -> bool:
    """Return True when the message contains any Ollama-trigger mention."""
    return bool(_extract_mentions(message) & OLLAMA_TRIGGER_MENTIONS)


class ModelType(str, Enum):
    """Available model types"""
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    AUTO = "auto"


class ChatRequest(BaseModel):
    message: str
    model: ModelType = ModelType.AUTO
    specific_model: Optional[str] = None  # e.g., "qwen2.5:7b" for Ollama
    max_tokens: int = 512
    temperature: float = 0.7
    use_memory: bool = True
    enable_actions: bool = True
    session_id: Optional[str] = None
    prefer_node: Optional[str] = None  # Specific Pi node


class ChatResponse(BaseModel):
    response: str
    model_used: str
    node_used: str
    memory_context_used: bool
    emoji_enhanced: bool
    actions_executed: List[str] = []
    latency_ms: int


class ClusterNode(BaseModel):
    """Represents a node in the cluster"""
    name: str
    ip: str
    port: int
    model_type: str
    healthy: bool = True
    load: int = 0


# Cluster configuration
CLUSTER_NODES = [
    ClusterNode(name="lucidia", ip="192.168.4.38", port=8000, model_type="qwen"),
    ClusterNode(name="lucidia-ollama", ip="192.168.4.38", port=8001, model_type="ollama"),
    ClusterNode(name="aria", ip="192.168.4.64", port=8000, model_type="qwen"),
    ClusterNode(name="aria-ollama", ip="192.168.4.64", port=8001, model_type="ollama"),
    ClusterNode(name="alice", ip="192.168.4.49", port=8000, model_type="qwen"),
    ClusterNode(name="alice-ollama", ip="192.168.4.49", port=8001, model_type="ollama"),
    ClusterNode(name="octavia", ip="192.168.4.74", port=8000, model_type="qwen"),
    ClusterNode(name="octavia-ollama", ip="192.168.4.74", port=8001, model_type="ollama"),
]


app = FastAPI(
    title="BlackRoad AI Gateway",
    description="Unified API for all BlackRoad AI models",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "service": "BlackRoad AI Gateway",
        "version": "1.0.0",
        "status": "online",
        "cluster_nodes": len(CLUSTER_NODES),
        "models": ["qwen", "deepseek", "ollama"],
        "emoji": "🖤🛣️"
    }


@app.get("/health")
async def health():
    """Health check with cluster status"""
    healthy_nodes = [node for node in CLUSTER_NODES if node.healthy]
    return {
        "status": "healthy" if len(healthy_nodes) > 0 else "degraded",
        "total_nodes": len(CLUSTER_NODES),
        "healthy_nodes": len(healthy_nodes),
        "nodes": [
            {
                "name": node.name,
                "model": node.model_type,
                "healthy": node.healthy,
                "load": node.load
            }
            for node in CLUSTER_NODES
        ]
    }


@app.get("/models")
async def list_models():
    """List all available models across cluster"""
    models = {}
    for node in CLUSTER_NODES:
        if node.healthy:
            model_type = node.model_type
            if model_type not in models:
                models[model_type] = []
            models[model_type].append({
                "node": node.name,
                "endpoint": f"http://{node.ip}:{node.port}"
            })
    return models


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with AI models via intelligent routing

    Features:
    - 🎯 Auto-select best model for query
    - ⚖️ Load balancing across nodes
    - 🔄 Automatic failover
    - 🧠 [MEMORY] integration
    - ⚡ Action execution
    - 🎨 Emoji enhancement
    - 🖥️  @mention routing — @copilot/@lucidia/@blackboxprogramming/@ollama
          all go straight to local Ollama; no external providers
    """
    import time
    start_time = time.time()

    # Honour @mention overrides: any trigger mention forces local Ollama
    effective_model = request.model
    if _should_force_ollama(request.message):
        effective_model = ModelType.OLLAMA

    # Select node
    node = select_node(effective_model, request.prefer_node)

    if not node:
        raise HTTPException(
            status_code=503,
            detail="No healthy nodes available for requested model"
        )

    # Route to appropriate endpoint based on model type
    try:
        if node.model_type == "ollama":
            response = await route_to_ollama(node, request)
        else:
            response = await route_to_direct_model(node, request)

        latency_ms = int((time.time() - start_time) * 1000)

        return ChatResponse(
            response=response["response"],
            model_used=response.get("model", node.model_type),
            node_used=node.name,
            memory_context_used=response.get("memory_context_used", False),
            emoji_enhanced=response.get("emoji_enhanced", True),
            actions_executed=response.get("actions_executed", []),
            latency_ms=latency_ms
        )

    except httpx.ConnectError:
        # Mark node as unhealthy and retry
        node.healthy = False
        raise HTTPException(
            status_code=503,
            detail=f"Node {node.name} is unreachable. Try again for automatic failover."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def select_node(model_type: ModelType, prefer_node: Optional[str] = None) -> Optional[ClusterNode]:
    """
    Select best node using load balancing

    Strategy:
    1. Filter by model type
    2. Filter healthy nodes
    3. Prefer specific node if requested
    4. Select least loaded node

    AUTO defaults to Ollama so all traffic stays on local hardware.
    """
    # Default AUTO → Ollama (local hardware, no external providers)
    if model_type == ModelType.AUTO:
        model_type = ModelType.OLLAMA

    candidates = [
        node for node in CLUSTER_NODES
        if node.healthy and node.model_type == model_type.value
    ]

    if not candidates:
        # Fallback to any healthy node
        candidates = [node for node in CLUSTER_NODES if node.healthy]

    if not candidates:
        return None

    # Prefer specific node if requested
    if prefer_node:
        for node in candidates:
            if node.name == prefer_node:
                return node

    # Select least loaded node (round-robin for now)
    return random.choice(candidates)


async def route_to_ollama(node: ClusterNode, request: ChatRequest) -> Dict:
    """Route to Ollama wrapper"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"http://{node.ip}:{node.port}/chat",
            json={
                "model": request.specific_model or "qwen2.5:7b",
                "message": request.message,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "use_memory": request.use_memory,
                "session_id": request.session_id
            }
        )
        return response.json()


async def route_to_direct_model(node: ClusterNode, request: ChatRequest) -> Dict:
    """Route to direct model (Qwen, DeepSeek)"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"http://{node.ip}:{node.port}/chat",
            json={
                "message": request.message,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "use_memory": request.use_memory,
                "enable_actions": request.enable_actions,
                "session_id": request.session_id
            }
        )
        return response.json()


@app.post("/broadcast")
async def broadcast_to_all_nodes(message: str):
    """
    Broadcast a message to all nodes via [MEMORY] system
    Useful for coordination between models
    """
    try:
        import subprocess
        result = subprocess.run(
            [
                "/host-home/memory-system.sh", "log", "broadcast",
                "api-gateway-broadcast",
                message,
                "ai-broadcast,coordination"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )
        return {
            "status": "broadcasted",
            "message": message,
            "success": result.returncode == 0
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000, log_level="info")
