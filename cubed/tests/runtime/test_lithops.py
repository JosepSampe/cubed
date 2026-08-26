import platform
import sys
from functools import partial

import pytest

from cubed.tests.runtime.utils import check_invocation_counts, deterministic_failure

pytest.importorskip("lithops")

from lithops.executors import LocalhostExecutor
from lithops.retries import RetryingFunctionExecutor

from cubed.runtime.executors.lithops import map_unordered


@pytest.fixture(scope="module")
def lithops_executor():
    config = {
        "lithops": {
            "backend": "localhost",
            "storage": "localhost",
            "include_modules": None,
        },
        "localhost": {"runtime": sys.executable},
    }
    with RetryingFunctionExecutor(LocalhostExecutor(config=config)) as executor:
        yield executor


def run_test(
    lithops_executor,
    function,
    input,
    retries,
    timeout=10,
    use_backups=False,
):
    outputs = set()
    for output in map_unordered(
        lithops_executor,
        [function],
        [input],
        ["group0"],
        timeout=timeout,
        retries=retries,
        use_backups=use_backups,
        wait_dur_sec=0.1,
    ):
        outputs.add(output)
    return outputs


# fmt: off
@pytest.mark.parametrize(
    ("timing_map", "n_tasks", "retries"),
    [
        # no failures
        ({}, 3, 2),
        # first invocation fails
        ({0: [-1], 1: [-1], 2: [-1]}, 3, 2),
        # first two invocations fail
        ({0: [-1, -1], 1: [-1, -1], 2: [-1, -1]}, 3, 2),
    ],
)
# fmt: on
@pytest.mark.parametrize("use_backups", [False, True])
def test_success(
    tmp_path, lithops_executor, timing_map, n_tasks, retries, use_backups
):
    outputs = run_test(
        lithops_executor,
        function=partial(deterministic_failure, tmp_path, timing_map),
        input=range(n_tasks),
        retries=retries,
        use_backups=use_backups,
    )

    assert outputs == set(range(n_tasks))

    check_invocation_counts(tmp_path, timing_map, n_tasks, retries)


# fmt: off
@pytest.mark.parametrize(
    ("timing_map", "n_tasks", "retries"),
    [
        # too many failures
        ({0: [-1], 1: [-1], 2: [-1, -1, -1]}, 3, 2),
    ],
)
# fmt: on
@pytest.mark.parametrize("use_backups", [False, True])
def test_failure(
    tmp_path, lithops_executor, timing_map, n_tasks, retries, use_backups
):
    with pytest.raises(RuntimeError):
        run_test(
            lithops_executor,
            function=partial(deterministic_failure, tmp_path, timing_map),
            input=range(n_tasks),
            retries=retries,
            use_backups=use_backups,
        )

    check_invocation_counts(tmp_path, timing_map, n_tasks, retries)


# fmt: off
@pytest.mark.parametrize(
    ("timing_map", "n_tasks", "retries"),
    [
        ({0: [3]}, 10, 2),
    ],
)
# fmt: on
@pytest.mark.skipif(platform.system() == "Windows", reason="does not run on windows")
def test_stragglers(tmp_path, lithops_executor, timing_map, n_tasks, retries):
    outputs = run_test(
        lithops_executor,
        function=partial(deterministic_failure, tmp_path, timing_map),
        input=range(n_tasks),
        retries=retries,
        timeout=500,
        use_backups=True,
    )

    assert outputs == set(range(n_tasks))

    check_invocation_counts(tmp_path, timing_map, n_tasks, retries)
