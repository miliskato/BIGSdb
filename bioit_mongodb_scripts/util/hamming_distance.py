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
    dist = np.zeros((data.shape[0] - start, data.shape[0] - start), dtype=np.int32)
    for i in range(start, data.shape[0]):
        for j in range(start, i):
            d = func(data, i, j)
            dist[i - start, j - start] = d[j - i]
    return dist

@nb.jit(nopython=True)
def hamming_dist(mat: np.ndarray, s: int, e: int) -> np.ndarray:
    """
    hamming distances computation function. Compute the hamming distances for the line of the distance matrix between
    indices s and e
    :param mat: matrix to store the distances in
    :param s: starting line to compute the distances
    :param e: ending line to compute the distances
    :return:
    """
    dist = np.zeros((e-s, mat.shape[0]), dtype=np.int32)
    n_loci = mat.shape[1]
    for i in range(s, e):
        for j in range(i):
            hamming = 0
            for k in range(n_loci):
                if mat[j, k] != '0':
                    if mat[i, k] != '0':
                        if mat[i, k] != mat[j, k]:
                            hamming += 1
            dist[i - s, j - s] = int(hamming)
    return dist
