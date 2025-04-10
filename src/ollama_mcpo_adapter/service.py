import logging
import multiprocessing
import socket
import time
from pathlib import Path
from typing import Dict, Optional, Union, List

import httpx

from .service_runner import run_mcpo
from .config_parser import parse_to_config, MCPServerInfo, extract_mcp_server_info_from_config


class MCPOService:
    def __init__(self, host: str, port: Union[int, str], config: Optional[Dict] = None,
            config_path: Optional[Union[str, Path]] = None) -> None:
        self.host = host
        self.port = port
        self.config = parse_to_config(config, config_path)

        self.started_event = multiprocessing.Event()
        self.abort_event = multiprocessing.Event()
        self.finished_event = multiprocessing.Event()

        self.process = None
        self.servers: List[MCPServerInfo] = extract_mcp_server_info_from_config(self.config)

    def start(self, wait: bool = True, timeout=30.0) -> None:
        from multiprocessing import Process
        self.process = Process(target=run_mcpo,
            args=(self.host, self.port, self.config, self.started_event, self.abort_event, self.finished_event))
        self.process.start()

        if wait:
            self.wait_for_mcpo_ready(timeout)

    def _get_host(self):
        if self.host == "0.0.0.0":
            return socket.gethostbyname(socket.gethostname())
        return self.host

    def wait_for_mcpo_ready(self, timeout):
        start_time = time.time()
        logging.debug(f"Waiting for mcpo process to be ready. Timeout: {timeout}")

        while not self.is_ready():
            self.finished_event.wait(0.5)

            if time.time() - start_time > timeout:
                logging.info(f"Waiting for mcpo to be ready timed out.")
                break

        # -- Check if mcpo server is served and reachable
        host = self._get_host()
        while time.time() - start_time < timeout:
            try:
                _ = httpx.get(f"http://{host}:{self.port}/docs", timeout=5.0)
                logging.info(f"Connection to mcpo service confirmed at {host}:{self.port}")
                break
            except (httpx.TimeoutException, httpx.ConnectError):
                self.finished_event.wait(0.5)

    def is_ready(self) -> bool:
        return self.started_event.is_set()

    def stop(self) -> None:
        self.abort_event.set()
        if self.process:
            self.process.join()

        self.finished_event.wait(timeout=10.0)

    def __enter__(self) -> 'MCPOService':
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
