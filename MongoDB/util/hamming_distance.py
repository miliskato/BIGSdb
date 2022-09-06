from numba import njit
import numpy as np


@njit(parallel=True)
def hamming_distance(cgmlst_profiles_i: list, cgmlst_profiles_j: list) -> int:
    test_equal = cgmlst_profiles_i == cgmlst_profiles_j
    hamming_dist = np.count_nonzero(test_equal == False)
    return hamming_dist
