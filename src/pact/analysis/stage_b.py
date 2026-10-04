"""Exact measured Stage-B dominance in the frozen and expanded objective sets."""
import numpy as np

OBJECTIVES = ('routed_scan_path_cost_um', 'measured_E', 'measured_H4', 'measured_H8')


def point(row, four=True):
    keys = OBJECTIVES if four else (OBJECTIVES[0], OBJECTIVES[1], OBJECTIVES[3])
    return np.array([float(row[k]) for k in keys])


def dominates(a, b):
    return bool(np.all(a <= b) and np.any(a < b))


def relation(a, b):
    return 'dominating' if dominates(a, b) else ('dominated' if dominates(b, a) else 'nondominated')
