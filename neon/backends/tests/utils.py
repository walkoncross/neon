# ----------------------------------------------------------------------------
# Copyright 2015 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
# pylint: skip-file

from neon.backends.backend import Tensor
from tests.utils import allclose_with_out
import numpy as np


def call_func(f, backend, tensors):
    """
    Call and evaluate a function with corresponding tensors, returns a numpy array.

    Arguments:
        f (lambda): Usage f(backend, *tensors)
        backend (Backend or numpy): one of (np, NervanaGPU, NervanaCPU)
        tensors (list): list of tensors

    Returns:
        numpy.ndarray: the evaluated result of f
    """
    if backend == np:
        return f(backend, *tensors)
    else:
        op_tree = f(backend, *tensors)
        op_tree_val = backend.empty(op_tree.shape)
        op_tree_val[:] = op_tree
        return op_tree_val.get()


def tensors_allclose(a_tensors, b_tensors, rtol=0, atol=1e-7):
    """
    For each backends, calls f with its tensors, and returns the results to
    allclose.

    Arguments:
        a_tensors: list of tensors, or a tensor
        b_tensors: (another) list of tensors, or a tensor
        rtol (float, optional): Relative tolerance.
        atol (float, optional): Absolute tolerance.
    Returns:
        bool: If the tensors of fs is all close
    """
    # deal with individual tensor
    if type(a_tensors) is not list and type(b_tensors) is not list:
        a_tensors = [a_tensors]
        b_tensors = [b_tensors]
    results = []
    for a_tensor, b_tensor in zip(a_tensors, b_tensors):
        if isinstance(a_tensor, Tensor):
            a_tensor = a_tensor.asnumpyarray()
        if isinstance(b_tensor, Tensor):
            b_tensor = b_tensor.asnumpyarray()
        results.append(allclose_with_out(a_tensor.astype(b_tensor.dtype),
                                         b_tensor,
                                         rtol=rtol, atol=atol))

    return all(results)


def funcs_allclose(f, backends, backend_tensors, rtol=0, atol=1e-7):
    """
    For each backends, calls f with its tensors, and assert the results to be
    all close.

    Arguments:
        f (lambda): Usage f(backend, *tensors)
        backend (Backend or numpy): one of (np, NervanaGPU, NervanaCPU)
        tensors (list): list of tensors
        rtol (float, optional): Relative tolerance.
        atol (float, optional): Absolute tolerance.

    Returns:
        bool: If the results of fs is close
    """
    # call funcs to get results
    results = []
    for backend, tensors in zip(backends, backend_tensors):
        results.append(call_func(f, backend, tensors))

    # assert results to be equal
    return tensors_allclose(results, rtol=rtol, atol=atol)


def gen_backend_tensors(backends, tensor_dims, flags=None, dtype=np.float32):
    """
    Generates random number for all backends.

    Arguments:
        backends (list): List of backends, one of (np, NervanaGPU, NervanaCPU)
        tensor_dims (list): List of dimensions of the tensors, for example
                            [(1, 2), (3, 4), (5, 6)]
        dtype (data-type): One of (np.float16, np.float32), must be the same
                           as backend.dtype if backend is one of the nervana
                           backends
        flags (list or str): If list is provided, specifies the flag for each
                             tensor. If str is provided, will be applied to all
                             tensors. Flags is one of the following:
                             ('zeros', 'pos_ones', 'neg_ones', 'pos_rand',
                              'neg_rand', 'rand', None)

    Returns:
        List of lists of tensors, corresponding to the backends.
        For example:
        [[np.ndarray, np.ndarray, np.ndarray],
         [GPUTensor, GPUTensor, GPUTensor],
         [CPUTensor, CPUTensor, CPUTensor]]
    """

    tensor_num = len(tensor_dims)
    if flags is not None:
        assert len(flags) == tensor_num

    # init
    backend_tensors = [[] for i in range(tensor_num)]

    # generate
    idx = 0
    for tensor_dim, flag in zip(tensor_dims, flags):
        assert flag in ('zeros', 'pos_ones', 'neg_ones', 'pos_rand', 'neg_rand',
                        'rand', None)

        # numpy standard value
        if flag == 'zeros':
            tensor = np.zeros(tensor_dim)
        elif flag == 'pos_ones':
            tensor = np.ones(tensor_dim)
        elif flag == 'neg_ones':
            tensor = -np.ones(tensor_dim)
        elif flag == 'pos_rand':
            tensor = np.random.rand(*tensor_dim)
        elif flag == 'neg_rand':
            tensor = -np.random.rand(*tensor_dim)
        elif flag == 'rand' or flag is None:
            tensor = -np.random.randn(*tensor_dim)
        else:
            raise NotImplementedError
        tensor = tensor.astype(dtype)

        # copy to different backends
        for backend, tensors in zip(backends, backend_tensors):
            if backend == np:
                tensors.append(tensor)
            else:
                assert(backend.default_dtype == dtype)
                tensors.append(backend.array(tensor, name='x%s' % idx))
        idx += 1

    return backend_tensors


class BackendPool():
    """
    Cache and reuse backend for testing. Useful for testing multiple expressions
    per backend. A backend is identified by the backend module and dtype.
    """
    pools = {}

    @staticmethod
    def get_backend(backend_module, dtype):
        """
        Arguments:
            backend_module: NervanaGPU or NervanaCPU
            dtype: np.float32, np.float16, etc

        Returns:
            Backend: the corresponding backend with certain default_dtype
        """
        if backend_module not in BackendPool.pools:
            BackendPool.pools[backend_module] = dict()
        pool = BackendPool.pools[backend_module]

        if dtype not in pool:
            pool[dtype] = backend_module(default_dtype=dtype)

        be = pool[dtype]
        return be
