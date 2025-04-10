import json
import os
import sys
from pathlib import Path
from typing import Dict, Union, List, Optional

WIN_NPX_PATH: str = os.getenv("WIN_NODEJS_NPX_PATH", "npx")


def adapt_config(config: Dict[str, Union[str, List[str], Dict[str, Union[str, List[str]]]]]) -> Dict[
    str, Union[str, List[str], Dict[str, Union[str, List[str]]]]]:
    for server in config.get("mcpServers", {}):
        server_config = config["mcpServers"][server]

        if server_config["command"] == "npx" and sys.platform.lower().startswith('win'):
            server_config["command"] = WIN_NPX_PATH
    return config


def get_mcp_config(config_file: Union[Path, str]) -> Dict[str, Union[str, List[str], Dict[str, Union[str, List[str]]]]]:
    with open(config_file) as f:
        config = json.load(f)

    return adapt_config(config)


def parse_to_config(mcp_config: Optional[Dict] = None, mcp_config_path: Optional[Union[str, Path]] = None) -> Dict[
    str, Union[str, List[str], Dict[str, Union[str, List[str]]]]]:
    if mcp_config is None and mcp_config_path:
        mcp_config = get_mcp_config(mcp_config_path)
    elif mcp_config is not None:
        mcp_config = adapt_config(mcp_config)
    else:
        raise ValueError("Either config or config_path must be provided.")

    return mcp_config


class MCPServerInfo:
    def __init__(self, name: str, command: str, args: List[str]) -> None:
        self.name = name
        self.command = command
        self.args = args


def extract_mcp_server_info_from_config(config: dict) -> List[MCPServerInfo]:
    servers = []
    for name, server_conf in config.get("mcpServers", {}).items():
        servers.append(MCPServerInfo(name=name, command=server_conf["command"], args=server_conf.get("args", [])))
    return servers


def get_mcp_server_info(config: Optional[Dict] = None, config_path: Optional[Union[str, Path]] = None) -> List[
    MCPServerInfo]:
    """ Get a list of MCPServerInfo from an Claude Desktop MCP-Config.
        MCPServerInfo is just a helper object to quickly iterate MCP Server names
    """
    return extract_mcp_server_info_from_config(parse_to_config(config, config_path))


def get_mcp_server_names(config: Optional[Dict] = None, config_path: Optional[Union[str, Path]] = None) -> List[str]:
    return [s.name for s in get_mcp_server_info(config, config_path)]
