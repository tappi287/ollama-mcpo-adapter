import logging

from ollama import Client

from ollama_mcpo_adapter import OllamaMCPOAdapter, MCPOService
from ollama_mcpo_adapter.config_parser import parse_to_config

logging.getLogger("httpcore").setLevel(logging.WARNING)


def test_ollama_adapter_mcp_config(input_path):
    adapter = OllamaMCPOAdapter(config_path=input_path.joinpath('mcp_config.json'))

    # Adapter should extract server names from provided MCP Config
    server_names = adapter._discover_servers("")
    assert len(server_names) == 3
    assert all(isinstance(name, str) for name in server_names)


def test_ollama_adapter_with_ollama(input_path, output_path, test_txt_file, ollama_running):
    mcp_config = parse_to_config(mcp_config_path=input_path.joinpath('mcp_config.json'))

    # -- Allow file access to local test dir
    mcp_config["mcpServers"]["filesystem"]["args"][2] = test_txt_file.parent.as_posix()
    mcp_config["mcpServers"].pop("time")

    host, port = "0.0.0.0", 4090

    with MCPOService(host, port, config=mcp_config) as service:
        adapter = OllamaMCPOAdapter(host, port)
        tools = adapter.list_tools_ollama()

        model = "qwen2.5-coder:7b"
        prompt = f"Create a file named \"test_file.txt\" in {test_txt_file.parent.as_posix()} with content: test"

        client = Client(host="http://127.0.0.1:11434")

        response = client.chat(model=model, messages=[{'role': 'user', 'content': prompt}], tools=tools)

        if response.message.tool_calls:
            adapter.call_tools_from_response(response.message.tool_calls)

            for tool_call in response.message.tool_calls:
                fname = tool_call.get("function").get("name")
                args = tool_call.get("function").get("arguments", "{}")
                logging.info(f"Received tool call {fname}: {args}")

    assert any(
        "test_file.txt" in str(call.get("function", {}).get("arguments", "")) for call in response.message.tool_calls)
    assert len(tools) > 0
    assert len(response.message.tool_calls) > 0
    assert test_txt_file.exists()
