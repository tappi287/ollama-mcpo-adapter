import logging
import sys
from pathlib import Path

import pytest

# Basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ]
)

test_data_path = Path(__file__).parent.joinpath("data")
test_data_input_path = test_data_path.joinpath('input')
test_data_output_path = test_data_path.joinpath('output')


@pytest.fixture
def output_path() -> Path:
    test_data_output_path.mkdir(exist_ok=True)
    return test_data_output_path


@pytest.fixture
def input_path() -> Path:
    return test_data_input_path


@pytest.fixture
def test_txt_file() -> Path:
    return test_data_output_path.joinpath('test_file.txt')


@pytest.fixture(autouse=True)
def cleanup_test_file(test_txt_file):
    yield
    if test_txt_file.exists():
        test_txt_file.unlink()