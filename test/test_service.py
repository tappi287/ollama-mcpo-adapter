import logging
import time

import httpx

from ollama_mcpo_adapter import MCPOService

logging.getLogger("httpcore").setLevel(logging.WARNING)


def test_service(input_path):
    mcp_config = input_path.joinpath('mcp_config.json')
    host, port = "localhost", 4090

    with MCPOService(host, port, config_path=mcp_config) as mcpo_service:
        response = httpx.get(f"http://{host}:{port}/docs")
        assert response.status_code == 200

    time.sleep(0.5)
    no_longer_reachable = False

    try:
        response = httpx.get(f"http://{host}:{port}/docs", timeout=0.5)
    except httpx.ConnectTimeout:
        no_longer_reachable = True

    assert no_longer_reachable is True
    print(response)
