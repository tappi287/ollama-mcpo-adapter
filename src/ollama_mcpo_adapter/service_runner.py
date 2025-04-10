import asyncio
import json
import logging
import multiprocessing
import os
import subprocess
import sys
import tempfile
from typing import Dict, List, Union

import psutil


def _kill_process_group(process: subprocess.Popen = None, process_id: int = None) -> None:
    if process is not None:
        process_id = process.pid

    try:
        parent = psutil.Process(process_id)
        children = parent.children(recursive=True)
        for child in children:
            logging.info(f"Shutting down child process {child.pid} {child.name()}")
            child.kill()
        logging.info(f"Shutting down parent process {parent.pid} {parent.name()}")
        parent.kill()
    except psutil.NoSuchProcess:
        pass

    if process is not None:
        process.wait()


def run_mcpo(host: str, port: Union[int, str],
             config: Dict[str, Union[str, List[str], Dict[str, Union[str, List[str]]]]],
             started_event: multiprocessing.Event = None, abort_event: multiprocessing.Event = None,
             finished_event: multiprocessing.Event = None) -> None:
    if not abort_event:
        from multiprocessing import Event
        abort_event = Event()

    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as temp_file:
        json.dump(config, temp_file)
        temp_config_path = temp_file.name

    cmd = ["mcpo", "--host", host, "--port", str(port), "--config", temp_config_path]
    process = None

    try:
        logging.info(f"Launching MCPO: {' '.join(cmd)}")

        # On POSIX: preexec_fn sets up a new process group
        if sys.platform != "win32":
            process = subprocess.Popen(cmd, preexec_fn=os.setsid)
        else:
            # On Windows: create new process group
            process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

        if started_event:
            started_event.set()

        while not abort_event.is_set():
            try:
                process.wait(timeout=5.0)
                # Exit if finished naturally
                logging.info("Process was terminated.")
                break
            except subprocess.TimeoutExpired:
                continue
    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Graceful shutdown triggered")
    finally:
        try:
            logging.debug("Trying to terminate process group.")
            if process is not None:
                _kill_process_group(process)
        except Exception as e:
            logging.error(f"Error terminating processes: {e}")

        try:
            logging.debug("Cleaning temp file.")
            os.unlink(temp_config_path)
        except FileNotFoundError:
            pass

        if finished_event:
            finished_event.set()
    logging.info(f"run_mcpo finished.")
