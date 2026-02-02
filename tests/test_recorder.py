import pytest
import os
import json
import shutil
from src.recorder import Recorder

TEST_DIR = "tests/temp_data"

@pytest.fixture
def recorder():
    # Setup
    r = Recorder(data_dir=TEST_DIR)
    yield r
    # Teardown
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)

def test_start_stop_produces_file(recorder):
    recorder.start()
    assert recorder.is_recording
    recorder.stop()
    assert not recorder.is_recording
    
    # Check file exists
    files = os.listdir(TEST_DIR)
    assert len(files) == 1
    assert files[0].endswith(".json")

def test_data_capsule_structure(recorder):
    recorder.start()
    recorder.log_frame({"ts": 1.0, "v": 100})
    recorder.log_frame({"ts": 1.1, "v": 101})
    recorder.log_event("TEST_EVENT", "Something happened")
    filepath = recorder.stop()
    
    assert filepath is not None
    
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    assert "meta" in data
    assert "frames" in data
    assert "events" in data
    
    assert len(data["frames"]) == 2
    assert len(data["events"]) == 1
    assert data["frames"][0]["v"] == 100
    assert data["events"][0]["type"] == "TEST_EVENT"
