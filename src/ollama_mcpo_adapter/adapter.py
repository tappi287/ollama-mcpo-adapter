import json
import logging
import re
import socket
from pathlib import Path
from typing import List, Dict, Any, Sequence, Optional, Union

import httpx
from ollama import Message

from .config_parser import parse_to_config, get_mcp_server_names
from .dispatcher import dispatch_tool_call


class OllamaMCPOAdapter:
    SERVER_DESCRIPTION_PATTERN = re.compile(r"\[([\w_-]+)]")  # find [time] [file-system] [some-123_name]

    def __init__(self, host: str = "localhost", port: int = 5090, config: Optional[Dict] = None,
                 config_path: Optional[Union[str, Path]] = None):
        if host == "0.0.0.0":
            host = socket.gethostbyname(socket.gethostname())

        self.host = host
        self.port = port

        self.mcp_config: Optional[dict] = None
        if config is not None or config_path is not None:
            self.mcp_config = parse_to_config(config, config_path)

        self.tool_registry: Dict[str, str] = {}
        self.ollama_tools: List[Dict[str, Any]] = []

    @staticmethod
    def _resolve_ref(ref: str, schemas: Dict[str, Any]) -> Dict[str, Any]:
        if ref.startswith("#/components/schemas/"):
            key = ref.split("/")[-1]
            return schemas.get(key, {})
        return {}

    @staticmethod
    def _clean_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        for name, definition in props.items():
            definition.pop("title", None)
            if definition.get("description", "").strip() == "":
                definition.pop("description", None)
            cleaned[name] = definition
        return cleaned

    def list_tools_ollama(self) -> List[Dict[str, Any]]:
        """ Contacts the MCPO FastAPI server docs and retrieves available MCP servers and their functions """
        self.ollama_tools.clear()
        self.tool_registry.clear()

        server_base_url = f"http://{self.host}:{self.port}"

        for name in self._discover_servers(server_base_url):
            openapi_url = f"{server_base_url}/{name}/openapi.json"
            try:
                spec = httpx.get(openapi_url).json()
                schemas = spec.get("components", {}).get("schemas", {})

                for path, methods in spec.get("paths", {}).items():
                    if "post" not in methods:
                        continue

                    post = methods["post"]
                    tool_name = f"{name}_{path.strip('/').replace('/', '_')}"
                    description = post.get("description", "")
                    body = post.get("requestBody", {})

                    schema = body.get("content", {}).get("application/json", {}).get("schema", {})
                    if "$ref" in schema:
                        schema = self._resolve_ref(schema["$ref"], schemas)

                    cleaned_properties = self._clean_properties(schema.get("properties", {}))
                    required = schema.get("required", [])

                    tool_def = {"type": "function", "function": {"name": tool_name, "description": description,
                        "parameters": {"type": "object", "properties": cleaned_properties, "required": required}}}

                    full_url = f"{server_base_url}/{name}{path}"
                    self.tool_registry[tool_name] = full_url
                    self.ollama_tools.append(tool_def)

            except Exception as e:
                logging.warning(f"Failed to load tools from {openapi_url}: {e}")

        return self.ollama_tools

    def _discover_servers(self, server_base_url: str) -> List[str]:
        """ Return a list of MCP Server names from the automatically generated MCPO docs description
            or from an existing MCP Configuration
        """
        if self.mcp_config is not None:
            return get_mcp_server_names(self.mcp_config)

        response = httpx.get(f"{server_base_url}/openapi.json")
        if response.status_code > 210:
            raise ConnectionError("MCPO service is not available or not ready")

        desc = response.json().get("info", {}).get("description", "")
        return self.SERVER_DESCRIPTION_PATTERN.findall(desc)

    def call_tool(self, tool_call: Message.ToolCall) -> Any:
        function = tool_call.get("function", {})
        tool_name = function.get("name")
        args_json = function.get("arguments", "{}")

        try:
            if isinstance(args_json, (str, bytes, bytearray)):
                params = json.loads(args_json)
            else:
                params = args_json
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON arguments: {args_json}")

        if tool_name not in self.tool_registry:
            raise ValueError(f"Tool '{tool_name}' not found in registry.")

        tool_url = self.tool_registry[tool_name]
        return dispatch_tool_call(tool_url, params)

    def call_tools_from_response(self, tool_calls: Sequence[Message.ToolCall]) -> List[Any]:
        return [self.call_tool(call) for call in tool_calls]
