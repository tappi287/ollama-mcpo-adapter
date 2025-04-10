import logging
import logging.handlers
import socket
import sys
import time
from multiprocessing import context
from pathlib import Path
from typing import Dict, Optional, Union

import httpx

from .config_parser import parse_to_config
from .service_runner import run_mcpo

MP_CONTEXT = context.SpawnContext()


class MCPOService:
    def __init__(self, host: str, port: Union[int, str], config: Optional[Dict] = None,
                 config_path: Optional[Union[str, Path]] = None, timeout = 30.0) -> None:
        self.host = host
        self.port = port
        self.config = parse_to_config(config, config_path)
        self.timeout = 30.0

        self.started_event = MP_CONTEXT.Event()
        self.abort_event = MP_CONTEXT.Event()
        self.finished_event = MP_CONTEXT.Event()

        self.process = None

        # Set up logging queue and listener in the main process.
        self.log_queue = MP_CONTEXT.Queue(-1)

        # Add/Get a handler for writing to stdout
        logger, console_handler = logging.getLogger(), None
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                console_handler = handler
                break
        if console_handler is None:
            console_handler = logging.StreamHandler(stream=sys.stdout)
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(processName)s - %(levelname)s: %(message)s'))

        self.log_listener = logging.handlers.QueueListener(self.log_queue, console_handler)

    def start(self, wait: bool = True) -> None:
        self.log_listener.start()

        self.process = MP_CONTEXT.Process(target=self.run_with_logging, args=(
            self.host, self.port, self.config, self.started_event, self.abort_event, self.finished_event,
            self.log_queue))
        self.process.start()

        if wait:
            self.wait_for_mcpo_ready()

    @staticmethod
    def run_with_logging(host: str, port: Union[int, str], config: Dict, started_event: MP_CONTEXT.Event,
                         abort_event: MP_CONTEXT.Event, finished_event: MP_CONTEXT.Event,
                         log_queue: MP_CONTEXT.Queue) -> None:

        # Set up logging in the child process
        root_logger = logging.getLogger()
        handler = logging.handlers.QueueHandler(log_queue)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)

        run_mcpo(host, port, config, started_event, abort_event, finished_event)

    def _get_host(self) -> str:
        if self.host == "0.0.0.0":
            return socket.gethostbyname(socket.gethostname())
        return self.host

    def wait_for_mcpo_ready(self) -> None:
        start_time = time.time()
        logging.debug(f"Waiting for mcpo process to be ready. Timeout: {self.timeout}")

        while not self.is_ready():
            self.finished_event.wait(0.5)

            if time.time() - start_time > self.timeout:
                logging.info("Waiting for mcpo to be ready timed out.")
                break

        host = self._get_host()
        logging.debug(f"Checking for connection to mcpo service at http://{host}:{self.port}/docs")
        while time.time() - start_time < self.timeout and not self.finished_event.is_set():
            try:
                _ = httpx.get(f"http://{host}:{self.port}/docs", timeout=5.0)
                logging.info(f"Connection to mcpo service confirmed at {host}:{self.port}")
                break
            except (httpx.TimeoutException, httpx.ConnectError):
                self.finished_event.wait(0.5)

    def is_ready(self) -> bool:
        return self.started_event.is_set()

    def cleanup(self):
        """ Try to eliminate leftover processes """
        from .service_runner import _kill_process_group

        if isinstance(self.process, MP_CONTEXT.Process):
            _kill_process_group(process_id=self.process.pid)

    def stop(self) -> None:
        self.abort_event.set()
        if self.process:
            self.process.join()

        self.finished_event.wait(timeout=self.timeout // 3)

        # Ensure the listener stops by putting a sentinel in the queue
        self.log_queue.put_nowait(None)
        self.log_listener.stop()

    def __enter__(self) -> 'MCPOService':
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
