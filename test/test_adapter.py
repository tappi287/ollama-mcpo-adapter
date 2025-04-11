import json
import logging
import unittest.mock

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


def test_ollama_adapter_with_openapi_spec(input_path, ):
    """ Test that the OllamaMCPOAdapter correctly parses an OpenAPI spec from a file,
        without relying on an actual running MCPO instance.
    """
    # Load the static OpenAPI specification file
    openapi_path = input_path.joinpath('filesystem_openapi.json')
    with open(openapi_path, 'r') as f:
        openapi_spec = json.load(f)
    openapi_schemas = openapi_spec.get("components", {}).get("schemas", {})

    # Mock MCPConfig for server_name discovery
    with open(input_path.joinpath('mcp_config.json'), "r") as f:
        mock_mcp_config = {"mcpServers": {"filesystem": json.load(f)["mcpServers"]["filesystem"]}}

    # Mock httpx.get to return our test OpenAPI spec
    mock_response = unittest.mock.Mock()
    mock_response.content = json.dumps(openapi_spec).encode()
    mock_response.status_code = 200
    mock_response.json.return_value = openapi_spec

    with unittest.mock.patch('ollama_mcpo_adapter.adapter.httpx.get', return_value=mock_response):
        # Create adapter instance pointing to non-existent server (we're mocking the response)
        adapter = OllamaMCPOAdapter("localhost", 5090, config=mock_mcp_config)

        # Get tools from OpenAPI spec
        ollama_tools = adapter.list_tools_ollama()

        # Verify that tools were parsed correctly
        assert len(ollama_tools) > 0, "Expected at least one tool to be discovered"

        for ollama_tool in ollama_tools:
            ollama_tool_name = ollama_tool.get('function', {}).get('name')
            assert 'type' in ollama_tool and ollama_tool['type'] == 'function', f"Tool {ollama_tool_name} is missing or has incorrect type"

            openapi_path_name = f"/{ollama_tool_name.split("_", 1)[1]}"
            assert openapi_path_name in openapi_spec["paths"], f"Tool {ollama_tool_name} not found in OpenAPI Paths"
            openapi_path = openapi_spec["paths"][openapi_path_name].get("post", {})

            # Verify required fields
            ollama_tool_function = ollama_tool.get("function", {})
            required_fields = ['name', 'description', 'parameters']
            for field in required_fields:
                assert field in ollama_tool_function, f"Tool missing required field: {field}"

            # Verify parameters
            if 'requestBody' in openapi_path:
                openapi_schema = adapter._resolve_ref(
                    openapi_path['requestBody']['content']['application/json']['schema']['$ref'], openapi_schemas)
                ollama_tool_params = ollama_tool_function.get("parameters", {})
                assert ollama_tool_params['properties'] == openapi_schema['properties']
                assert ollama_tool_params['required'] == openapi_schema['required']

    print("Successfully parsed OpenAPI spec and verified Ollama tool structure")


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
