import sys, gzip, logging, click
import pandas as pd, numpy as np
import numpy as np, numba as nb, os
from tempfile import NamedTemporaryFile
import SharedArray as sa
from multiprocessing import Pool #, set_start_method
from scipy.spatial import distance as ssd
from scipy.cluster.hierarchy import linkage


logging.basicConfig(format='%(asctime)s | %(message)s', stream=sys.stdout, level=logging.INFO)

def prepare_mat(profile_file) :
    mat = pd.read_csv(profile_file, sep='\t', header=None, dtype=str).values
    allele_columns = np.array([i == 0 or (not h.startswith('#')) for i, h in enumerate(mat[0])])
    mat = mat[1:, allele_columns]
    try :
        mat = mat.astype(int)
        mat = mat[mat.T[0] > 0]
        names = mat.T[0]
    except :
        names = mat.T[0].copy()
        mat.T[0] = np.arange(1, mat.shape[0]+1)
        mat = mat.astype(int)
    mat[mat < 0] = 0
    return mat, names

mat, names = prepare_mat("/home/bebergk/subset_profiles")

def getDistance(data, func_name, pool, start=0):
    with NamedTemporaryFile(dir='.', prefix='HCC_') as file :
        prefix = 'file://{0}'.format(file.name)
        func = eval(func_name)
        mat_buf = '{0}.mat.sa'.format(prefix)
        mat = sa.create(mat_buf, shape = data.shape, dtype = data.dtype)
        mat[:] = data[:]
        dist_buf = '{0}.dist.sa'.format(prefix)
        dist = sa.create(dist_buf, shape = [mat.shape[0] - start, mat.shape[0]], dtype = np.int32)
        dist[:] = 0
        __parallel_dist(mat_buf, func, dist_buf, mat.shape, pool, start)
        sa.delete(mat_buf)
        sa.delete(dist_buf)
        #os.unlink(dist_buf[7:])
    return dist



def __parallel_dist(mat_buf, func, dist_buf, mat_shape, pool, start=0) :
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

def __dist_wrapper(data) :
    func, mat_buf, dist_buf, s, e, start = data
    mat = sa.attach(mat_buf)
    dist = sa.attach(dist_buf)
    if e > s :
        d = func(mat[:, 1:], s, e)
        dist[(s-start):(e-start)] = d
    del mat, dist

@nb.jit(nopython=True)
def dual_dist(mat, s, e):
    dist = np.zeros((e-s, mat.shape[0]), dtype=np.int32 )
    n_loci = mat.shape[1]
    for i in range(s, e) :
        for j in range(i) :
            hamming = 0
            for k in range(n_loci) :
                if mat[j, k] > 0 :
                    if mat[i, k] > 0 :
                        if mat[i, k] != mat[j, k]:
                            hamming += 1
            dist[i - s, j] = int(hamming)
    return dist
start = 0
pool = Pool(4)
allowed_missing = 0.05
dist = getDistance(mat, 'dual_dist', pool, start)
print(dist)

from scipy.spatial import distance
print(distance.hamming(mat[3], mat[8])*len(mat[1]))
