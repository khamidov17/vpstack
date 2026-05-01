import os
import subprocess
import pytest
from pathlib import Path

def run_config(args, env):
    bin_path = Path(__file__).parent.parent / "bin" / "vpstack-config"
    cmd = [str(bin_path.absolute())] + args

    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True
    )

def test_config_set_get(tmp_path):
    # Set custom HOME to avoid messing with real config
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)

    run_config(["set", "telemetry", "off"], env=env)
    res = run_config(["get", "telemetry"], env=env)

    assert res.stdout.strip() == "off"

def test_config_invalid_key(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)

    res = run_config(["set", "invalid_key", "value"], env=env)
    assert res.returncode != 0
    assert "unknown key" in res.stderr
