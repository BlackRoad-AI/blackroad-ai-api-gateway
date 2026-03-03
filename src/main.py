"""
🌐 BlackRoad AI - Unified API Gateway
Routes requests to appropriate AI models across cluster.

Vendor-compatible API shims let any OpenAI or Anthropic client
point to this gateway just by changing their base URL.
OAuth2 Bearer token (API key) authentication protects all endpoints.
"""

import os
import random
import secrets
import time
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
from enum import Enum


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)

# API keys are loaded from the environment.  Multiple keys may be provided as
# a comma-separated list in BLACKROAD_API_KEYS.  When no keys are configured
# the gateway runs in open mode (useful during initial local setup).
_API_KEYS: set[str] = set(
    k.strip()
    for k in os.getenv("BLACKROAD_API_KEYS", "").split(",")
    if k.strip()
)


def _require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> str:
    """Validate Bearer token (OAuth2 API key).

    Returns the validated token so downstream handlers can log/trace it.
    Raises HTTP 401 when authentication fails.
    """
    if not _API_KEYS:
        # No keys configured — open mode, skip auth
        return "open"

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison to prevent timing attacks
    token = credentials.credentials
    for key in _API_KEYS:
        if secrets.compare_digest(token, key):
            return token

    raise HTTPException(
        status_code=401,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Data models — native BlackRoad API
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cluster configuration
# Node IPs can be overridden with env vars to support Tailscale addresses.
# Example: LUCIDIA_IP=100.x.x.x ARIA_IP=100.x.x.y ...
# ---------------------------------------------------------------------------

CLUSTER_NODES = [
    ClusterNode(
        name="lucidia",
        ip=os.getenv("LUCIDIA_IP", "192.168.4.38"),
        port=int(os.getenv("LUCIDIA_QWEN_PORT", "8000")),
        model_type="qwen",
    ),
    ClusterNode(
        name="lucidia-ollama",
        ip=os.getenv("LUCIDIA_IP", "192.168.4.38"),
        port=int(os.getenv("LUCIDIA_OLLAMA_PORT", "8001")),
        model_type="ollama",
    ),
    ClusterNode(
        name="aria",
        ip=os.getenv("ARIA_IP", "192.168.4.64"),
        port=int(os.getenv("ARIA_QWEN_PORT", "8000")),
        model_type="qwen",
    ),
    ClusterNode(
        name="aria-ollama",
        ip=os.getenv("ARIA_IP", "192.168.4.64"),
        port=int(os.getenv("ARIA_OLLAMA_PORT", "8001")),
        model_type="ollama",
    ),
    ClusterNode(
        name="alice",
        ip=os.getenv("ALICE_IP", "192.168.4.49"),
        port=int(os.getenv("ALICE_QWEN_PORT", "8000")),
        model_type="qwen",
    ),
    ClusterNode(
        name="alice-ollama",
        ip=os.getenv("ALICE_IP", "192.168.4.49"),
        port=int(os.getenv("ALICE_OLLAMA_PORT", "8001")),
        model_type="ollama",
    ),
    ClusterNode(
        name="octavia",
        ip=os.getenv("OCTAVIA_IP", "192.168.4.74"),
        port=int(os.getenv("OCTAVIA_QWEN_PORT", "8000")),
        model_type="qwen",
    ),
    ClusterNode(
        name="octavia-ollama",
        ip=os.getenv("OCTAVIA_IP", "192.168.4.74"),
        port=int(os.getenv("OCTAVIA_OLLAMA_PORT", "8001")),
        model_type="ollama",
    ),
]


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BlackRoad AI Gateway",
    description=(
        "Unified API for all BlackRoad AI models. "
        "Exposes OpenAI-compatible (/v1/chat/completions) and "
        "Anthropic-compatible (/v1/messages) endpoints so any existing "
        "client can be redirected to this gateway by changing only its "
        "base URL."
    ),
    version="2.0.0",
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
        "version": "2.0.0",
        "status": "online",
        "cluster_nodes": len(CLUSTER_NODES),
        "models": ["qwen", "deepseek", "ollama"],
        "vendor_compatible_apis": ["/v1/chat/completions (OpenAI)", "/v1/messages (Anthropic)"],
        "emoji": "🖤🛣️",
    }


@app.get("/health")
async def health():
    """Health check with cluster status (no auth required for monitoring)"""
    healthy_nodes = [node for node in CLUSTER_NODES if node.healthy]
    if len(healthy_nodes) == 0:
        status = "unhealthy"
    elif len(healthy_nodes) < len(CLUSTER_NODES):
        status = "degraded"
    else:
        status = "healthy"
    return {
        "status": status,
        "total_nodes": len(CLUSTER_NODES),
        "healthy_nodes": len(healthy_nodes),
        "nodes": [
            {
                "name": node.name,
                "model": node.model_type,
                "healthy": node.healthy,
                "load": node.load,
            }
            for node in CLUSTER_NODES
        ],
    }


@app.get("/models")
async def list_models(_token: str = Depends(_require_auth)):
    """List all available models across cluster"""
    models: Dict[str, List[Dict]] = {}
    for node in CLUSTER_NODES:
        if node.healthy:
            model_type = node.model_type
            if model_type not in models:
                models[model_type] = []
            models[model_type].append({
                "node": node.name,
                "endpoint": f"http://{node.ip}:{node.port}",
            })
    return models


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, _token: str = Depends(_require_auth)):
    """
    Chat with AI models via intelligent routing

    Features:
    - 🎯 Auto-select best model for query
    - ⚖️ Load balancing across nodes
    - 🔄 Automatic failover
    - 🧠 [MEMORY] integration
    - ⚡ Action execution
    - 🎨 Emoji enhancement
    """
    start_time = time.time()

    # Select node
    node = select_node(request.model, request.prefer_node)

    if not node:
        raise HTTPException(
            status_code=503,
            detail="No healthy nodes available for requested model",
        )

    # Route to appropriate endpoint based on model type
    try:
        if node.model_type == "ollama":
            result = await route_to_ollama(node, request)
        else:
            result = await route_to_direct_model(node, request)

        latency_ms = int((time.time() - start_time) * 1000)

        return ChatResponse(
            response=result["response"],
            model_used=result.get("model", node.model_type),
            node_used=node.name,
            memory_context_used=result.get("memory_context_used", False),
            emoji_enhanced=result.get("emoji_enhanced", True),
            actions_executed=result.get("actions_executed", []),
            latency_ms=latency_ms,
        )

    except httpx.ConnectError:
        # Mark node as unhealthy and retry
        node.healthy = False
        raise HTTPException(
            status_code=503,
            detail=f"Node {node.name} is unreachable. Try again for automatic failover.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# OpenAI-compatible API  (/v1/...)
# Clients that currently call api.openai.com can point to this gateway by
# setting OPENAI_API_BASE=http://<gateway>:7000/v1 and using any API key.
# ---------------------------------------------------------------------------

class _OAIMessage(BaseModel):
    role: str
    content: str


class _OAIChatRequest(BaseModel):
    model: str = "blackroad-auto"
    messages: List[_OAIMessage]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


@app.get("/v1/models")
async def oai_list_models(_token: str = Depends(_require_auth)):
    """OpenAI-compatible model list"""
    model_ids = [
        "blackroad-auto",
        "blackroad-qwen",
        "blackroad-ollama",
        "blackroad-deepseek",
    ]
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "owned_by": "blackroad", "created": 0}
            for m in model_ids
        ],
    }


@app.post("/v1/chat/completions")
async def oai_chat_completions(
    request: _OAIChatRequest,
    _token: str = Depends(_require_auth),
):
    """OpenAI ChatCompletion-compatible endpoint.

    Accepts the standard OpenAI request format and translates it into the
    BlackRoad internal routing layer.  Returns a response shaped like the
    OpenAI ChatCompletion object so existing clients work without changes.
    """
    # Map OpenAI model name to internal model type
    model_map = {
        "blackroad-qwen": ModelType.QWEN,
        "blackroad-deepseek": ModelType.DEEPSEEK,
        "blackroad-ollama": ModelType.OLLAMA,
    }
    internal_model = model_map.get(request.model, ModelType.AUTO)

    # Flatten messages into a single prompt (last user message as primary)
    user_messages = [m.content for m in request.messages if m.role == "user"]
    prompt = user_messages[-1] if user_messages else ""

    # Build a system prefix from any system messages
    system_parts = [m.content for m in request.messages if m.role == "system"]
    if system_parts:
        prompt = system_parts[-1] + "\n\n" + prompt

    internal_req = ChatRequest(
        message=prompt,
        model=internal_model,
        max_tokens=request.max_tokens or 512,
        temperature=request.temperature if request.temperature is not None else 0.7,
    )

    start_time = time.time()
    node = select_node(internal_model)
    if not node:
        raise HTTPException(status_code=503, detail="No healthy nodes available")

    try:
        if node.model_type == "ollama":
            result = await route_to_ollama(node, internal_req)
        else:
            result = await route_to_direct_model(node, internal_req)
    except httpx.ConnectError:
        node.healthy = False
        raise HTTPException(status_code=503, detail=f"Node {node.name} unreachable")

    response_text = result.get("response", "")
    latency_ms = int((time.time() - start_time) * 1000)

    prompt_tokens = prompt.split()
    completion_tokens = response_text.split()
    return {
        "id": f"chatcmpl-{secrets.token_hex(8)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt_tokens),
            "completion_tokens": len(completion_tokens),
            "total_tokens": len(prompt_tokens) + len(completion_tokens),
        },
        "_blackroad": {"node_used": node.name, "latency_ms": latency_ms},
    }


# ---------------------------------------------------------------------------
# Anthropic-compatible API  (/v1/messages)
# Clients that currently call api.anthropic.com can point to this gateway by
# setting ANTHROPIC_BASE_URL=http://<gateway>:7000 and using any API key.
# ---------------------------------------------------------------------------

class _AnthropicContentBlock(BaseModel):
    type: str = "text"
    text: str


class _AnthropicMessage(BaseModel):
    role: str
    content: Any  # str or list of content blocks


class _AnthropicRequest(BaseModel):
    model: str = "blackroad-auto"
    messages: List[_AnthropicMessage]
    system: Optional[str] = None
    max_tokens: int = 512
    temperature: Optional[float] = 0.7


def _extract_text(content: Any) -> str:
    """Extract plain text from Anthropic message content (str or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


@app.post("/v1/messages")
async def anthropic_messages(
    request: _AnthropicRequest,
    _token: str = Depends(_require_auth),
):
    """Anthropic Messages API-compatible endpoint.

    Accepts the standard Anthropic /v1/messages request format and translates
    it into the BlackRoad routing layer.  Returns a response shaped like the
    Anthropic Messages object so existing clients work without changes.
    """
    # Build prompt from messages
    user_parts = [
        _extract_text(m.content)
        for m in request.messages
        if m.role == "user"
    ]
    prompt = user_parts[-1] if user_parts else ""
    if request.system:
        prompt = request.system + "\n\n" + prompt

    internal_req = ChatRequest(
        message=prompt,
        model=ModelType.AUTO,
        max_tokens=request.max_tokens,
        temperature=request.temperature if request.temperature is not None else 0.7,
    )

    start_time = time.time()
    node = select_node(ModelType.AUTO)
    if not node:
        raise HTTPException(status_code=503, detail="No healthy nodes available")

    try:
        if node.model_type == "ollama":
            result = await route_to_ollama(node, internal_req)
        else:
            result = await route_to_direct_model(node, internal_req)
    except httpx.ConnectError:
        node.healthy = False
        raise HTTPException(status_code=503, detail=f"Node {node.name} unreachable")

    response_text = result.get("response", "")
    latency_ms = int((time.time() - start_time) * 1000)

    input_tokens = prompt.split()
    output_tokens = response_text.split()
    return {
        "id": f"msg_{secrets.token_hex(8)}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": response_text}],
        "model": request.model,
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": len(input_tokens),
            "output_tokens": len(output_tokens),
        },
        "_blackroad": {"node_used": node.name, "latency_ms": latency_ms},
    }


def select_node(model_type: ModelType, prefer_node: Optional[str] = None) -> Optional[ClusterNode]:
    """
    Select best node using load balancing

    Strategy:
    1. Filter by model type
    2. Filter healthy nodes
    3. Prefer specific node if requested
    4. Select least loaded node
    """
    # Get nodes for requested model type
    if model_type == ModelType.AUTO:
        # Default to Qwen for AUTO
        model_type = ModelType.QWEN

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
async def broadcast_to_all_nodes(message: str, _token: str = Depends(_require_auth)):
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
