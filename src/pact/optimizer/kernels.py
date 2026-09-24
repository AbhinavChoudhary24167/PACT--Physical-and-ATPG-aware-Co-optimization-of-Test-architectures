"""Compiled exact shift kernels; no dense FF-by-FF arrays.

For position j and clock t, toggle(t,j) = d[t-j+m-1]. A move changes
only a few diagonals d and a few spatial weight columns. Updating those
contributions costs O(P*L*s), not O(P*N*L). Spatial max reduction is O(P*L*B).
No fastmath: reproducible finite floating arithmetic and exact binary XOR.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def coefficient(patterns, order, p, r, longest):
    m = len(order)
    if r < 0:
        if p == 0:
            return 0
        return patterns[p-1, order[-r-1]] ^ patterns[p-1, order[-r]]
    a = patterns[p, order[longest-1-r]] if r >= longest-m else 0
    if r == 0:
        b = patterns[p-1, order[0]] if p else 0
    else:
        b = patterns[p, order[longest-r]] if r-1 >= longest-m else 0
    return a ^ b


@njit(cache=True)
def diagonals(patterns, order, longest):
    m = len(order)
    d = np.empty((len(patterns), longest+m-1), np.int8)
    for p in range(len(patterns)):
        for r in range(1-m, longest):
            d[p, r+m-1] = coefficient(patterns, order, p, r, longest)
    return d


@njit(cache=True)
def add_chain(field, d, bins, weights):
    m = len(bins)
    for p in range(len(d)):
        for j in range(m):
            b = bins[j]
            for t in range(field.shape[1]):
                if d[p, t-j+m-1]:
                    field[p,t,b,0] += weights[j,0]
                    field[p,t,b,1] += weights[j,1]


@njit(cache=True)
def update_diagonals(field, d, patterns, order, bins, weights, dirty_r):
    m, longest = len(order), field.shape[1]
    for r in dirty_r:
        idx = r+m-1
        for p in range(len(patterns)):
            new = coefficient(patterns, order, p, r, longest)
            delta = int(new)-int(d[p,idx])
            if delta:
                for j in range(max(0,-r), min(m,longest-r)):
                    t, b = r+j, bins[j]
                    field[p,t,b,0] += delta*weights[j,0]
                    field[p,t,b,1] += delta*weights[j,1]
            d[p,idx] = new


@njit(cache=True)
def update_columns(field, d, bins, weights, positions, new_bins, new_weights):
    m = len(bins)
    for z in range(len(positions)):
        j = positions[z]
        old_b, new_b = bins[j], new_bins[z]
        for p in range(len(d)):
            for t in range(field.shape[1]):
                if d[p,t-j+m-1]:
                    field[p,t,old_b,0] -= weights[j,0]
                    field[p,t,old_b,1] -= weights[j,1]
                    field[p,t,new_b,0] += new_weights[z,0]
                    field[p,t,new_b,1] += new_weights[z,1]
        bins[j] = new_b
        weights[j] = new_weights[z]


@njit(cache=True)
def reduce_field(field):
    total0=0.;total1=0.;peak0=0.;peak1=0.
    for p in range(field.shape[0]):
        for t in range(field.shape[1]):
            for b in range(100):
                total0 += field[p,t,b,0]
                total1 += field[p,t,b,1]
            for y in range(9):
                for x in range(9):
                    b = y*10+x
                    v0=field[p,t,b,0]+field[p,t,b+1,0]+field[p,t,b+10,0]+field[p,t,b+11,0]
                    v1=field[p,t,b,1]+field[p,t,b+1,1]+field[p,t,b+10,1]+field[p,t,b+11,1]
                    peak0=max(peak0,v0);peak1=max(peak1,v1)
    return np.array([total0,peak0,total1,peak1])
