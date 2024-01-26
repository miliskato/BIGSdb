import logging
import numba as nb
import numpy as np

def get_distance(data: np.array, func_name: str, start: int = 0) -> np.array:
    """
    Main function to call to compute the hamming distance in parallel and return the half matrix
    :param data: the array containing all the cgmlst profiles to compute the distances on
    :param func_name: the name of the function to use to compute the distances
    :param pool: a pool of thread to compute the distances in parallel
    :param start: from which cgmlst profiles do the distances need to be computed?
    :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
    :return: an array (matrix like) containing the different computed distances
    """

    func = eval(func_name)
    logging.getLogger('numba').setLevel(logging.WARNING)
    dist = np.zeros((data.shape[0] - start, data.shape[0]), dtype=np.int32)
    for i in range(start, data.shape[0]):
        for j in range(0, i):
            dist[i - start, j] = func(data, i, j)
    return dist

@nb.jit(nopython=True)
def hamming_dist(mat: np.ndarray, line1: int, line2: int) -> int:
    """
    hamming distances computation function. Compute the hamming distances between two lines
    :param mat: matrix to store the distances in
    :param line1: starting line to compute the distances
    :param line2: ending line to compute the distances
    :return:
    """
    n_loci = mat.shape[1]
    hamming = 0
    for k in range(n_loci):
        if mat[line2, k] != '0' and mat[line1, k] != '0' and mat[line2, k] != mat[line1, k]:
            hamming += 1
    return hamming
