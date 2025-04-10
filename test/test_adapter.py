import logging
from pathlib import Path

import pytest
from ollama import Client

from ollama_mcpo_adapter import OllamaMCPOAdapter, MCPOService

logging.getLogger("httpcore").setLevel(logging.WARNING)


def test_ollama_adapter_mcp_config(input_path):
    mcp_config_path = input_path.joinpath('mcp_config.json')
    adapter = OllamaMCPOAdapter(config_path=mcp_config_path)

    # Adapter should extract server names from provided MCP Config
    server_names = adapter._discover_servers("")
    assert len(server_names) == 2


def test_ollama_adapter_with_ollama(input_path, test_txt_file):
    test_txt_file.unlink(missing_ok=True)

    mcp_config_path = input_path.joinpath('mcp_config.json')
    host, port = "0.0.0.0", 4090

    with MCPOService(host, port, config_path=mcp_config_path) as service:
        adapter = OllamaMCPOAdapter(host, port)
        tools = adapter.list_tools_ollama()

        model = "qwen2.5-coder:14b-instruct-q4_K_M"
        prompt = f"Create a file named \"test_file.txt\" in {test_txt_file.parent.as_posix()} with content: test"

        client = Client(host="http://127.0.0.1:11434")
        response = client.chat(model=model, messages=[{'role': 'user', 'content': prompt}], tools=tools)

        if response.message.tool_calls:
            adapter.call_tools_from_response(response.message.tool_calls)

    assert len(tools) > 0
    assert len(response.message.tool_calls) > 0
    assert test_txt_file.exists()
