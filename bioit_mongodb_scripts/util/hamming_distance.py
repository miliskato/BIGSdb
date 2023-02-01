from tempfile import NamedTemporaryFile
from typing import Callable

import SharedArray as sa
import numba as nb
import numpy as np
import yaml

from bioit_mongodb_scripts.config import MONGO_CONFIG


def getDistance(data: np.array, func_name:str, pool: object, start=0) -> np.array:
    """
    Main function to call to compute the hamming distance in parallel and return the half matrix
    :param data: the array containing all the cgmlst profiles to compute the distances on
    :param func_name: the name of the function to use to compute the distances
    :param pool: a pool of thread to compute the distances in parallel
    :param start: from which cgmlst profiles do the distances need to be computed?
    :return: an array (matrix like) containing the different computed distances
    """
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    with NamedTemporaryFile(dir=config_data["temp_dir"], prefix='HCC_') as file :
        prefix = 'file://{0}'.format(file.name)
        func = eval(func_name)
        mat_buf = '{0}.mat.sa'.format(prefix)
        mat = sa.create(mat_buf, shape=data.shape, dtype=data.dtype)
        mat[:] = data[:]
        dist_buf = '{0}.dist.sa'.format(prefix)
        dist = sa.create(dist_buf, shape = [mat.shape[0] - start, mat.shape[0]], dtype = np.int32)
        dist[:] = 0
        __parallel_dist(mat_buf, func, dist_buf, mat.shape, pool, start)
        sa.delete(mat_buf)
        sa.delete(dist_buf)
    return dist



def __parallel_dist(mat_buf: str, func: Callable, dist_buf:str, mat_shape: tuple, pool:object, start:int =0) -> None:
    """
    This function take as input a matrix stored in the buffer and containing the cgmlst profiles. This function
    distribute jobs on the pool of threads to start the computation in parallel.
    :param mat_buf: string with the name of teh matrix buffer to use to compute the hamming distances in parallel
    :param func: the function to use to compute the distances (hamming_dist).
    :param dist_buf: the matrix buffer where the computed distances will be stored.
    :param mat_shape: the shape of the matrix containing the cgmlst
    :param pool: the pool of threads to compute the distance in parallel
    :param start: from which cgmlst profile must the distance start to be computed.
    :return: None
    """
    n_pool = len(pool._pool)
    tot_cmp = (mat_shape[0] * mat_shape[0] - start * start)/n_pool
    s, indices = start, []
    for _ in np.arange(n_pool) :
        e = np.sqrt(s * s + tot_cmp)
        indices.append([s, e])
        s = e
    indices = (np.array(indices)+0.5).astype(int)
    for _ in pool.imap_unordered(__dist_wrapper, [[func, mat_buf, dist_buf, s, e, start] for s, e in indices ]) :
        pass
    return

def __dist_wrapper(data:list) -> None :
    """
    Wrapper to start computing the distances.
    :param data: a list of all the parameters to pass to the dist_wrapper
    :return: None
    """
    func, mat_buf, dist_buf, s, e, start = data
    mat = sa.attach(mat_buf)
    dist = sa.attach(dist_buf)
    if e > s :
        d = func(mat, s, e)
        dist[(s-start):(e-start)] = d
    del mat, dist

@nb.jit(nopython=True)
def hamming_dist(mat: np.ndarray, s: int, e: int):
    """
    hamming distances computation function. Compute the hamming distances for the line of the distance matrix between
    indices s and e
    :param mat: matrix to store the distances in
    :param s: starting line to compute the distances
    :param e: ending line to compute the distances
    :return:
    """
    dist = np.zeros((e-s, mat.shape[0]), dtype=np.int32 )
    n_loci = mat.shape[1]
    for i in range(s, e):
        for j in range(i):
            hamming = 0
            for k in range(n_loci) :
                if mat[j, k] != '0':
                    if mat[i, k] != '0':
                        if mat[i, k] != mat[j, k]:
                            hamming += 1
            dist[i - s, j] = int(hamming)
    return dist
