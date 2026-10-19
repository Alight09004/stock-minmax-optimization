"""Streamlit's in-process AppTest exercises real view interactions, no server mock."""

from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from streamlit.testing.v1 import AppTest


VIEW = Path(__file__).resolve().parents[1] / "dashboard/benchmark_view.py"


def test_dashboard_run_and_missing_result():
    root = VIEW.parents[1]
    app = AppTest.from_file(str(VIEW), default_timeout=30).run()
    assert not app.exception
    app.text_input[0].set_value(str(root / "datasets/sample_stock.csv")).run()
    app.button[0].click().run()
    assert not app.exception
    result = app.session_state["benchmark_result"]
    assert result["cases"][0]["n"] == 240
    assert result["cases"][0]["algorithms"]["baseline"]["comparison_count"] == 478
    assert len(app.metric) == 2
    app.text_input[1].set_value(str(root / "results/generated/nonexistent.json"))
    app.button[1].click().run()
    assert not app.exception
    assert any("Cannot load results" in error.value for error in app.error)


def test_dashboard_missing_data_and_malformed_json(tmp_path):
    app = AppTest.from_file(str(VIEW), default_timeout=30).run()
    app.text_input[0].set_value(str(tmp_path / "missing.csv")).run()
    assert not app.exception
    assert app.button[0].disabled
    assert any("Prepared data is unavailable" in error.value for error in app.error)
    bad_result = tmp_path / "invalid.json"
    bad_result.write_text('{"schema_version":1,"cases":[{}]}', encoding="utf-8")
    app.text_input[1].set_value(str(bad_result))
    app.button[1].click().run()
    assert not app.exception
    assert any("Cannot load results" in error.value for error in app.error)


def test_dashboard_load_actual_export():
    import pytest

    result_path = VIEW.parents[1] / "results/generated/baseline_benchmark.json"
    if not result_path.exists():
        pytest.skip("Generate the real benchmark export first")
    app = AppTest.from_file(str(VIEW), default_timeout=30).run()
    app.text_input[1].set_value(str(result_path))
    app.button[1].click().run()
    assert not app.exception
    assert len(app.selectbox[1].options) == 5
    app.selectbox[1].select(1_000_000).run()
    assert not app.exception
    result = app.session_state["benchmark_result"]
    case = result["cases"][-1]
    assert case["analysis"]["algorithms"]["baseline"]["comparison_count"] == 1_999_998
    assert case["analysis"]["empirical_speedup"] is None


def test_streamlit_http_smoke():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(VIEW),
         "--server.headless=true", "--browser.gatherUsageStats=false",
         "--server.address=127.0.0.1", f"--server.port={port}"],
        cwd=VIEW.parents[1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise AssertionError(process.stdout.read())
            try:
                with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
                    assert response.status == 200
                with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise AssertionError("Streamlit server failed to become healthy")
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
