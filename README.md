# 🖤 BlackRoad OS — Your AI. Your Hardware. Your Rules.

## 👆 Just Click a Link

**No terminal. No setup. No jargon. Just open a portal and see it work.**

| Portal | What it does |
|--------|-------------|
| 🚀 **[Launch BlackRoad OS](https://os.blackroad.io)** | An entire AI OS — in your browser. Talk to it. Watch it work. |
| 🌐 **[BlackRoad.io](https://blackroad.io)** | The main site. Start here. |
| 🤖 **[3D AI Models](https://products.blackroad.io)** | Meet Lucidia, Aria & the crew — interactive 3D. |
| 🌍 **[Lucidia AI](https://lucidia.earth)** | Our flagship AI. She remembers you. |
| ⛓️ **[RoadChain](https://roadchain.io)** | AI infrastructure on-chain. |
| 📖 **[Documentation](https://docs.blackroad.io)** | Plain-English guides. No jargon. |
| 💚 **[System Status](https://status.blackroad.io)** | Is everything online? Check here. |
| 🗂️ **[Portal Hub](https://blackroad-ai.github.io/blackroad-ai-api-gateway/)** | All portals in one place. |

---

> [![CI](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/ci.yml)
> [![CORE CI](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/core-ci.yml/badge.svg)](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/core-ci.yml)
> [![Deploy Workers](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/deploy-cloudflare-workers.yml/badge.svg)](https://github.com/BlackRoad-AI/blackroad-ai-api-gateway/actions/workflows/deploy-cloudflare-workers.yml)

---

## 🏗️ What is this repo?

This is the **API Gateway** — the backend that routes traffic to all BlackRoad AI models. You don't need to touch this to use BlackRoad. [Just click a portal above.](#-just-click-a-link)

If you're a developer and want to understand the architecture:

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

### 🗂️ Infrastructure Directory

> Full index of all BlackRoad organizations, domains, and infrastructure:  
> **[blackroad-ai.github.io/blackroad-ai-api-gateway/](https://blackroad-ai.github.io/blackroad-ai-api-gateway/)**

### 🔗 Links

- [BlackRoad OS](https://blackroad.io)
- [Documentation](https://docs.blackroad.io)
- [Status](https://status.blackroad.io)
- [GitHub Enterprise](https://github.com/enterprises/blackroad-os)
- [BlackRoad AI](https://github.com/BlackRoad-AI)
- [BlackRoad OS Org](https://github.com/BlackRoad-OS)
- [BlackRoad Cloud](https://github.com/BlackRoad-Cloud)
- [BlackRoad Security](https://github.com/BlackRoad-Security)
- [BlackRoad Labs](https://github.com/BlackRoad-Labs)
- [BlackRoad Foundation](https://github.com/BlackRoad-Foundation)
- [BlackRoad Ventures](https://github.com/BlackRoad-Ventures)
- [BlackRoad Studio](https://github.com/BlackRoad-Studio)
- [BlackRoad Media](https://github.com/BlackRoad-Media)
- [BlackRoad Education](https://github.com/BlackRoad-Education)
- [BlackRoad Gov](https://github.com/BlackRoad-Gov)
- [BlackRoad Hardware](https://github.com/BlackRoad-Hardware)
- [BlackRoad Interactive](https://github.com/BlackRoad-Interactive)
- [BlackRoad Archive](https://github.com/BlackRoad-Archive)
- [Blackbox Enterprises](https://github.com/Blackbox-Enterprises)
- [Lucidia AI](https://lucidia.earth)
- [RoadChain](https://roadchain.io)
- [BlackRoad Quantum](https://blackroadquantum.com)

### 📧 Contact

- Email: blackroad.systems@gmail.com
- Primary: amundsonalexa@gmail.com

### ⚖️ License

Copyright © 2026 BlackRoad OS, Inc. - All Rights Reserved

See [LICENSE](./LICENSE) for details.

---

🖤🛣️ **The road is the destination.**
