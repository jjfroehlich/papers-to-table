from pathlib import Path
from time import perf_counter

from backend.app.config import load_config
from backend.app.runner import Runner


def test_small_batch_performance_smoke(tmp_path: Path):
    config = load_config('tests/fixtures/configs/test-config.json')
    config.paths.output_dir = str(tmp_path / 'artifacts')
    start = perf_counter()
    Runner(Path(config.paths.output_dir)).execute(config)
    elapsed = perf_counter() - start
    assert elapsed < 20, f'Fixture batch unexpectedly slow: {elapsed:.2f}s'
