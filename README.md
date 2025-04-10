
# 🦙 ollama-mcpo-adapter

**Expose MCPO tools as Ollama-compatible functions** using a simple Python adapter and optional runtime service.

---

## ✨ Features

- 🔌 Connect to any existing [MCPO](https://github.com/open-webui/mcpo) instance
- ⚙️ Launch your own MCPO server locally via `MCPOService`
- 🔁 Convert [MCP tools](https://modelcontextprotocol.info/docs) to Ollama-compatible tool functions

---

## 🚀 Quickstart

### 1. Install

```bash
pip install ollama-mcpo-adapter
```

Or with [`uv`](https://docs.astral.sh/uv/):

```bash
uv pip install -e .
```
---

### 2. Usage with Existing MCPO Instance

```python
from ollama_mcpo_adapter import OllamaMCPOAdapter

adapter = OllamaMCPOAdapter(host="localhost", port=5090)
# Gets tool descriptions from MCPO FastAPI /docs
tools = adapter.list_tools_ollama()
```

---

### 3. Usage with Local MCPO Service

```python
from ollama_mcpo_adapter import MCPOService, OllamaMCPOAdapter
from ollama import Client

# Start MCPO Service from a config or mcp_config JSON file
mcp_config = {
    "mcpServers": {
        "time": {"command": "uvx", "args": ["mcp-server-time", "--local-timezone=Europe/Berlin"]}
    }
}
mcpo = MCPOService("127.0.0.1", 4090, config=mcp_config,
                   # -OR- from an existing mcp_config file 
                   config_path="path/to/mcp_config.json")
# MCPOSService class handles MCPO server start-up and shutdown and in a subprocess
mcpo.start(wait=True)

# Connect the adapter
adapter = OllamaMCPOAdapter("127.0.0.1", 4090)
tools = adapter.list_tools_ollama()

# Send a prompt to Ollama using discovered tools
client = Client(host="http://127.0.0.1:11434")
response = client.chat(
    model="qwen2.5-coder:14b-instruct-q4_K_M",
    messages=[{"role": "user", "content": "Write a file..."}],
    tools=tools,
)

# Handle any tool calls
if response.message.tool_calls:
    adapter.call_tools_from_response(response.message.tool_calls)
```

---

## 🧪 Running Tests

```bash
pytest
```

Add your `mcp_config.json` and test files under `tests/data/input`.

---

## 📂 Project Structure

```
ollama_mcpo_adapter/
├── adapter.py        # Tool discovery + Ollama integration
├── service.py        # Optional: launch MCPO programmatically
├── service_runner.py # MCPO subprocess control
├── config_parser.py  # MCP config parsing helpers
```

---

## 📜 License

MIT. See [LICENSE](./LICENSE).
