import pickle

import fsspec
import numpy as np
import pytest
import zarr
from numpy.testing import assert_array_equal
from rechunker.executors.python import PythonPipelineExecutor

import cubed as xp
from cubed import Callback
from cubed.primitive.blockwise import apply_blockwise
from cubed.runtime.executors.beam import BeamDagExecutor
from cubed.runtime.executors.lithops import LithopsDagExecutor
from cubed.runtime.executors.python import PythonDagExecutor
from cubed.tests.utils import create_zarr

LITHOPS_LOCAL_CONFIG = {"lithops": {"backend": "localhost", "storage": "localhost"}}


@pytest.fixture()
def spec(tmp_path):
    return xp.Spec(tmp_path, max_mem=100000)


@pytest.fixture(
    scope="module",
    params=[
        PythonPipelineExecutor(),
        PythonDagExecutor(),
        BeamDagExecutor(),
        LithopsDagExecutor(config=LITHOPS_LOCAL_CONFIG),
    ],
)
def executor(request):
    return request.param


# Test API

# Array object


def test_object_bool(tmp_path, executor):
    spec = xp.Spec(tmp_path, 100000, executor=executor)
    a = xp.asarray(
        [[False, False, False], [False, False, False], [False, False, False]],
        chunks=(2, 2),
        spec=spec,
    )
    b = xp.all(a)
    assert not b

    a = xp.asarray(
        [[True, True, True], [True, True, True], [True, True, True]],
        chunks=(2, 2),
        spec=spec,
    )
    b = xp.all(a)
    assert b


# Creation functions


def test_arange(spec, executor):
    a = xp.arange(12, chunks=(4,), spec=spec)
    assert_array_equal(a.compute(executor=executor), np.arange(12))


def test_asarray(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    assert_array_equal(
        a.compute(executor=executor), np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    )


def test_ones(spec, executor):
    a = xp.ones((3, 3), chunks=(2, 2), spec=spec)
    assert_array_equal(a.compute(executor=executor), np.ones((3, 3)))


def test_ones_like(spec, executor):
    a = xp.ones((3, 3), chunks=(2, 2), spec=spec)
    b = xp.ones_like(a)
    assert_array_equal(b.compute(executor=executor), np.ones_like(np.ones((3, 3))))


# Data type functions


def test_astype(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.astype(a, xp.int32)
    assert_array_equal(
        b.compute(executor=executor),
        np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
    )


# Elementwise functions


def test_add(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 1, 1], [1, 1, 1], [1, 1, 1]], chunks=(2, 2), spec=spec)
    c = xp.add(a, b)
    assert_array_equal(
        c.compute(executor=executor), np.array([[2, 3, 4], [5, 6, 7], [8, 9, 10]])
    )


def test_equal(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    c = xp.equal(a, b)
    assert_array_equal(c.compute(executor=executor), np.full((3, 3), True))


def test_negative(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.negative(a)
    assert_array_equal(
        b.compute(executor=executor),
        np.array([[-1, -2, -3], [-4, -5, -6], [-7, -8, -9]]),
    )


# Linear algebra functions


def test_matmul(spec, executor):
    a = xp.asarray(
        [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
        chunks=(2, 2),
        spec=spec,
    )
    b = xp.asarray(
        [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
        chunks=(2, 2),
        spec=spec,
    )
    c = xp.matmul(a, b)
    x = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
    y = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
    expected = np.matmul(x, y)
    assert_array_equal(c.compute(executor=executor), expected)


@pytest.mark.cloud
def test_matmul_cloud(executor):
    tmp_path = "gs://barry-zarr-test/matmul"
    spec = xp.Spec(tmp_path, max_mem=100000)
    try:
        a = xp.asarray(
            [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
            chunks=(2, 2),
            spec=spec,
        )
        b = xp.asarray(
            [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
            chunks=(2, 2),
            spec=spec,
        )
        c = xp.matmul(a, b)
        x = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
        y = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
        expected = np.matmul(x, y)
        assert_array_equal(c.compute(executor=executor), expected)
    finally:
        fs = fsspec.open(tmp_path).fs
        fs.rm(tmp_path, recursive=True)


def test_outer(spec, executor):
    a = xp.asarray([0, 1, 2], chunks=2, spec=spec)
    b = xp.asarray([10, 50, 100], chunks=2, spec=spec)
    c = xp.outer(a, b)
    assert_array_equal(c.compute(executor=executor), np.outer([0, 1, 2], [10, 50, 100]))


# Manipulation functions


def test_broadcast_arrays():
    a = xp.ones(30, chunks=(3,))
    b = xp.ones(30, chunks=(6,))
    a_b, b_b = xp.broadcast_arrays(a, b)

    assert_array_equal(a_b.compute(), np.ones(30))
    assert_array_equal(b_b.compute(), np.ones(30))

    a = xp.ones((1, 30), chunks=(1, 3))
    b = xp.ones(30, chunks=(6,))
    a_b, b_b = xp.broadcast_arrays(a, b)

    assert_array_equal(a_b.compute(), np.ones((1, 30)))
    assert_array_equal(b_b.compute(), np.ones((1, 30)))


def test_broadcast_to(spec, executor):
    a = xp.asarray([1, 2, 3], chunks=(2,), spec=spec)
    b = xp.broadcast_to(a, shape=(3, 3))
    assert_array_equal(
        b.compute(executor=executor),
        np.broadcast_to(np.array([1, 2, 3]), shape=(3, 3)),
    )


def test_permute_dims(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.permute_dims(a, (1, 0))
    assert_array_equal(
        b.compute(executor=executor),
        np.transpose(np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])),
    )


def test_reshape(spec, executor):
    a = xp.arange(12, chunks=4, spec=spec)
    b = xp.reshape(a, (3, 4))

    assert_array_equal(
        b.compute(executor=executor),
        np.arange(12).reshape((3, 4)),
    )


def test_squeeze_1d(spec, executor):
    a = xp.asarray([[1, 2, 3]], chunks=(1, 2), spec=spec)
    b = xp.squeeze(a, 0)
    assert_array_equal(b.compute(executor=executor), np.squeeze([[1, 2, 3]], 0))


def test_squeeze_2d(spec, executor):
    a = xp.asarray([[[1], [2], [3]]], chunks=(1, 2, 1), spec=spec)
    b = xp.squeeze(a, (0, 2))
    assert_array_equal(
        b.compute(executor=executor), np.squeeze([[[1], [2], [3]]], (0, 2))
    )


# Statistical functions


def test_mean_axis_0(spec, executor):
    a = xp.asarray(
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]], chunks=(2, 2), spec=spec
    )
    b = xp.mean(a, axis=0)
    assert_array_equal(
        b.compute(executor=executor),
        np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]).mean(axis=0),
    )


def test_sum(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.sum(a)
    assert_array_equal(
        b.compute(executor=executor), np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]).sum()
    )


def test_sum_axis_0(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.sum(a, axis=0)
    assert_array_equal(b.compute(executor=executor), np.array([12, 15, 18]))


# Utility functions


def test_all(spec, executor):
    a = xp.asarray(
        [[True, True, True], [True, True, True], [True, True, True]],
        chunks=(2, 2),
        spec=spec,
    )
    b = xp.all(a)
    assert_array_equal(
        b.compute(executor=executor),
        np.array([[True, True, True], [True, True, True], [True, True, True]]).all(),
    )


# Other


def test_regular_chunks(spec):
    a = xp.ones((5, 5), chunks=((2, 2, 1), (5,)), spec=spec)
    a.compute()
    with pytest.raises(ValueError):
        a = xp.ones((5, 5), chunks=((2, 1, 2), (5,)), spec=spec)
        a.compute()


def test_from_zarr(tmp_path, spec, executor):
    store = store = tmp_path / "source.zarr"
    create_zarr(
        [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        chunks=(2, 2),
        store=store,
    )
    a = xp.from_zarr(store, spec=spec)
    assert_array_equal(
        a.compute(executor=executor), np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    )


def test_to_zarr(tmp_path, spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    output = tmp_path / "output.zarr"
    xp.to_zarr(a, output, executor=executor)
    res = zarr.open(output)
    assert_array_equal(res[:], np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))


def test_map_blocks_with_kwargs(spec, executor):
    # based on dask test
    a = xp.asarray([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], chunks=5, spec=spec)
    b = xp.map_blocks(np.max, a, axis=0, keepdims=True, dtype=a.dtype, chunks=(1,))
    assert_array_equal(b.compute(executor=executor), np.array([4, 9]))


def test_multiple_ops(spec, executor):
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 1, 1], [1, 1, 1], [1, 1, 1]], chunks=(2, 2), spec=spec)
    c = xp.add(a, b)
    d = xp.negative(c)
    assert_array_equal(
        d.compute(executor=executor),
        np.array([[-2, -3, -4], [-5, -6, -7], [-8, -9, -10]]),
    )


def test_compute_is_idempotent(spec, executor):
    a = xp.ones((3, 3), chunks=(2, 2), spec=spec)
    b = xp.negative(a)
    assert_array_equal(b.compute(executor=executor), -np.ones((3, 3)))
    assert_array_equal(b.compute(executor=executor), -np.ones((3, 3)))


def test_default_spec(executor):
    # default spec works for small computations
    a = xp.ones((3, 3), chunks=(2, 2))
    b = xp.negative(a)
    assert_array_equal(
        b.compute(executor=executor),
        -np.ones((3, 3)),
    )


def test_default_spec_max_mem_exceeded():
    # default spec fails for large computations
    a = xp.ones((100000, 100000), chunks=(10000, 10000))
    with pytest.raises(ValueError):
        xp.negative(a)


def test_reduction_multiple_rounds(tmp_path, executor):
    spec = xp.Spec(tmp_path, max_mem=110)
    a = xp.ones((100, 10), dtype=np.uint8, chunks=(1, 10), spec=spec)
    b = xp.sum(a, axis=0, dtype=np.uint8)
    assert_array_equal(b.compute(executor=executor), np.ones((100, 10)).sum(axis=0))


def test_unify_chunks(spec, executor):
    a = xp.ones((10, 10), chunks=(10, 2), spec=spec)
    b = xp.ones((10, 10), chunks=(2, 10), spec=spec)
    c = xp.add(a, b)
    assert_array_equal(
        c.compute(executor=executor), np.ones((10, 10)) + np.ones((10, 10))
    )


def test_visualize(tmp_path):
    a = xp.ones((100, 10), dtype=np.uint8, chunks=(1, 10))
    b = xp.sum(a, axis=0)

    assert not (tmp_path / "myplan.dot").exists()
    assert not (tmp_path / "myplan.png").exists()
    assert not (tmp_path / "myplan.svg").exists()

    b.visualize(filename=tmp_path / "myplan")
    assert (tmp_path / "myplan.svg").exists()

    b.visualize(filename=tmp_path / "myplan", format="png")
    assert (tmp_path / "myplan.png").exists()

    b.visualize(filename=tmp_path / "myplan", format="dot")
    assert (tmp_path / "myplan.dot").exists()


def test_array_pickle(spec, executor):
    a = xp.asarray(
        [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
        chunks=(2, 2),
        spec=spec,
    )
    b = xp.asarray(
        [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
        chunks=(2, 2),
        spec=spec,
    )
    c = xp.matmul(a, b)

    # we haven't computed c yet, so pickle and unpickle, and check it still works
    c = pickle.loads(pickle.dumps(c))

    x = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
    y = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])
    expected = np.matmul(x, y)
    assert_array_equal(c.compute(executor=executor), expected)


mock_call_counter = 0


def mock_apply_blockwise(*args, **kwargs):
    # Raise an error on every 3rd call
    global mock_call_counter
    mock_call_counter += 1
    if mock_call_counter % 3 == 0:
        raise IOError("Test fault injection")
    return apply_blockwise(*args, **kwargs)


def test_retries(mocker, spec):
    # Inject faults into the primitive layer
    mocker.patch(
        "cubed.primitive.blockwise.apply_blockwise", side_effect=mock_apply_blockwise
    )

    executor = PythonDagExecutor()
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 1, 1], [1, 1, 1], [1, 1, 1]], chunks=(2, 2), spec=spec)
    c = xp.add(a, b)
    assert_array_equal(
        c.compute(executor=executor), np.array([[2, 3, 4], [5, 6, 7], [8, 9, 10]])
    )


def test_retries_lithops(mocker, spec):
    # Inject faults into the primitive layer
    # We need to use random faults, since we can't coordinate using object state
    def random_failure_apply_blockwise(*args, **kwargs):
        import random

        if random.random() < 0.2:
            raise IOError("Test fault injection")
        return apply_blockwise(*args, **kwargs)

    mocker.patch(
        "cubed.primitive.blockwise.apply_blockwise",
        side_effect=random_failure_apply_blockwise,
    )

    executor = LithopsDagExecutor(config=LITHOPS_LOCAL_CONFIG)
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 1, 1], [1, 1, 1], [1, 1, 1]], chunks=(2, 2), spec=spec)
    c = xp.add(a, b)
    assert_array_equal(
        c.compute(executor=executor), np.array([[2, 3, 4], [5, 6, 7], [8, 9, 10]])
    )


class TaskCounter(Callback):
    def on_compute_start(self, arr):
        self.value = 0

    def on_task_end(self, n=1):
        self.value += n


def test_callbacks(spec, executor):
    if not isinstance(executor, (PythonDagExecutor, LithopsDagExecutor)):
        pytest.skip(f"{type(executor)} does not support callbacks")

    task_counter = TaskCounter()

    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 1, 1], [1, 1, 1], [1, 1, 1]], chunks=(2, 2), spec=spec)
    c = xp.add(a, b)
    assert_array_equal(
        c.compute(executor=executor, callbacks=[task_counter]),
        np.array([[2, 3, 4], [5, 6, 7], [8, 9, 10]]),
    )

    assert task_counter.value == 4


def test_already_computed(spec):
    executor = PythonDagExecutor()

    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.asarray([[1, 1, 1], [1, 1, 1], [1, 1, 1]], chunks=(2, 2), spec=spec)
    c = xp.add(a, b)
    d = xp.negative(c)

    assert d.plan.num_tasks(d.name) == 8

    task_counter = TaskCounter()
    c.compute(executor=executor, callbacks=[task_counter])
    assert task_counter.value == 4

    # since c has already been computed, when computing d only 4 tasks are run, instead of 8
    task_counter = TaskCounter()
    d.compute(executor=executor, callbacks=[task_counter])
    assert task_counter.value == 4


def test_fusion(tmp_path, spec):
    executor = PythonDagExecutor()
    a = xp.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], chunks=(2, 2), spec=spec)
    b = xp.negative(a)
    c = xp.astype(b, np.float32)
    d = xp.negative(c)

    assert d.plan.num_tasks(d.name, optimize_graph=False) == 12
    assert d.plan.num_tasks(d.name, optimize_graph=True) == 4

    task_counter = TaskCounter()
    result = d.compute(executor=executor, callbacks=[task_counter])
    assert task_counter.value == 4

    assert_array_equal(
        result,
        np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]).astype(np.float32),
    )