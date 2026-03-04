# 🌐 BlackRoad AI - API Gateway

> ✅ **VERIFIED WORKING** — CI/CD pipeline active, Cloudflare Workers deployed, auto-merge enabled.
> All GitHub Actions pinned to SHA-256 commit hashes for supply-chain security.
>
> [![CI](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/ci.yml)
> [![CORE CI](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/core-ci.yml/badge.svg)](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/core-ci.yml)
> [![Deploy Workers](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/deploy-cloudflare-workers.yml/badge.svg)](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/deploy-cloudflare-workers.yml)

**Unified API for all AI models across the cluster**

## 🎯 Overview

The API Gateway provides a single endpoint for accessing all BlackRoad AI models with:
- 🎯 **Intelligent Routing** - Auto-select best model
- ⚖️ **Load Balancing** - Distribute across nodes
- 🔄 **Automatic Failover** - Health checks & retries
- 🧠 **[MEMORY] Integration** - Unified context
- 🌐 **Cluster Aware** - Manages 8+ nodes
- ⚡ **Low Latency** - Sub-second routing

## 🏗️ Architecture

```
                    ┌─────────────────────────┐
                    │   API Gateway :7000     │
                    │   ┌─────────────────┐   │
        Request ───▶│   │ Load Balancer   │   │
                    │   └────────┬────────┘   │
                    └────────────┼────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
         ┌────▼─────┐      ┌────▼─────┐      ┌────▼─────┐
         │ Lucidia  │      │   Aria   │      │  Alice   │
         ├──────────┤      ├──────────┤      ├──────────┤
         │ Qwen:8000│      │ Qwen:8000│      │ Qwen:8000│
         │Ollama:8001│      │Ollama:8001│      │Ollama:8001│
         └──────────┘      └──────────┘      └──────────┘
```

## 🚀 Quick Start

### Run Gateway
```bash
# Docker
docker-compose up -d

# Python (development)
python src/main.py
```

### Use the API
```bash
# Auto-select best model
curl -X POST http://localhost:7000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing",
    "model": "auto",
    "session_id": "user-123"
  }'

# Specific model type
curl -X POST http://localhost:7000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write Python code",
    "model": "qwen",
    "session_id": "user-123"
  }'

# Prefer specific node
curl -X POST http://localhost:7000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "model": "ollama",
    "specific_model": "qwen2.5:7b",
    "prefer_node": "lucidia-ollama",
    "session_id": "user-123"
  }'
```

## 📡 API Endpoints

### `GET /`
Service information
```bash
curl http://localhost:7000/
```

### `GET /health`
Cluster health status
```bash
curl http://localhost:7000/health
```

Response:
```json
{
  "status": "healthy",
  "total_nodes": 8,
  "healthy_nodes": 8,
  "nodes": [
    {
      "name": "lucidia",
      "model": "qwen",
      "healthy": true,
      "load": 0
    },
    ...
  ]
}
```

### `GET /models`
List all available models
```bash
curl http://localhost:7000/models
```

### `POST /chat`
Chat with AI models

Request:
```json
{
  "message": "Your question",
  "model": "auto",           // auto, qwen, deepseek, ollama
  "specific_model": null,    // For Ollama: "qwen2.5:7b"
  "max_tokens": 512,
  "temperature": 0.7,
  "use_memory": true,
  "enable_actions": true,
  "session_id": "user-123",
  "prefer_node": null        // Optional: "lucidia", "aria", etc.
}
```

Response:
```json
{
  "response": "Your answer here...",
  "model_used": "qwen",
  "node_used": "lucidia",
  "memory_context_used": true,
  "emoji_enhanced": true,
  "actions_executed": [],
  "latency_ms": 234
}
```

### `POST /broadcast`
Broadcast message to all nodes via [MEMORY]
```bash
curl -X POST http://localhost:7000/broadcast \
  -H "Content-Type: application/json" \
  -d '{"message": "System update"}'
```

## 🎯 Routing Strategy

1. **Model Selection**:
   - `auto` → Qwen (default)
   - `qwen` → Qwen2.5 models
   - `ollama` → Ollama runtime (multi-model)

2. **Node Selection**:
   - Filter by model type
   - Filter healthy nodes
   - Prefer specific node if requested
   - Round-robin load balancing

3. **Failover**:
   - Automatic health checks
   - Mark unhealthy nodes
   - Retry on different node

## 🌐 Cluster Nodes

Default configuration:
- **lucidia** (192.168.4.38) - Qwen:8000, Ollama:8001
- **aria** (192.168.4.64) - Qwen:8000, Ollama:8001
- **alice** (192.168.4.49) - Qwen:8000, Ollama:8001
- **octavia** (192.168.4.74) - Qwen:8000, Ollama:8001

## 🧠 [MEMORY] Integration

Gateway integrates with BlackRoad memory for:
- Session context management
- Cross-model coordination
- Broadcast messaging
- Collaboration with Claude instances

## 📊 Monitoring

```bash
# Health check
curl http://localhost:7000/health

# Watch logs
docker logs -f blackroad-ai-gateway
```

## 🔌 Integration Examples

### JavaScript/TypeScript
```typescript
const response = await fetch('http://localhost:7000/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Hello AI',
    model: 'auto',
    session_id: userId
  })
});
const data = await response.json();
console.log(data.response);
```

### Python
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        'http://localhost:7000/chat',
        json={
            'message': 'Hello AI',
            'model': 'auto',
            'session_id': user_id
        }
    )
    data = response.json()
    print(data['response'])
```

## 📄 License

BlackRoad Proprietary

---

🌌 **Built with the BlackRoad Vision** - One gateway, infinite models

---

## 🖤 BlackRoad OS

This repository is part of the **BlackRoad OS** ecosystem - the operating system for AI-first companies.

### 🌟 The Vision

BlackRoad OS enables entire companies to operate exclusively by AI while serving as the API layer above Google, OpenAI, and Anthropic, managing their AI model memory and continuity.

- **OS in a Window**: [os.blackroad.io](https://os.blackroad.io)
- **3D AI Models**: [products.blackroad.io](https://products.blackroad.io)
- **Agent Orchestration**: 30,000 AI agents coordinated via memory system

### 🤖 GitHub Integration

Need help? Mention **@blackroad** in any issue or PR to summon our intelligent agent cascade!

### 📊 Repository Stats

- **Organization**: Part of 15 BlackRoad organizations
- **Total Repos**: 144+ across the empire
- **AI Agents**: 30,000+ available for assistance

### 🔗 Links

- [BlackRoad OS](https://blackroad.io)
- [Documentation](https://docs.blackroad.io)
- [Status](https://status.blackroad.io)
- [GitHub Organizations](https://github.com/BlackRoad-OS)

### 📧 Contact

- Email: blackroad.systems@gmail.com
- Primary: amundsonalexa@gmail.com

### ⚖️ License

Copyright © 2026 BlackRoad OS, Inc. - All Rights Reserved

See [LICENSE](./LICENSE) for details.

---

🖤🛣️ **The road is the destination.**
