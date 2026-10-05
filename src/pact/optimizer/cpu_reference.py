"""Bound the independent unpacked oracle's memory without changing its model."""
import copy
import numpy as np
from .candidate_stateful import reference as full_reference


def reference(model, orders):
    """Execute the original independent oracle one complete pattern at a time.

    Patterns are independent in the registered load/capture/unload schedule.
    Every state, Boolean gate, source capacitance and spatial cell is still
    computed by the original oracle. E is the sum; H4/H8 are maxima over all
    cycles. No packed evaluator update kernel is used for reference scoring.
    """
    result = None
    per_pattern = 2*model.longest*3
    for p in range(len(model.load)):
        view = copy.copy(model)
        view.load, view.response = model.load[p:p+1], model.response[p:p+1]
        view.cycles = 2*model.longest
        view.constant_waves = {n: np.packbits(np.unpackbits(wave, bitorder='little')[p*per_pattern:(p+1)*per_pattern],
                                            bitorder='little') for n, wave in model.constant_waves.items()}
        score = full_reference(view, orders)
        if result is None:
            result = score.copy()
        else:
            if result[0] != score[0] or result[3] != score[3]:
                raise AssertionError('Physical geometry changed across reference patterns')
            result[1] += score[1]
            result[2] = max(result[2], score[2])
            result[4] = max(result[4], score[4])
    if result is None:
        raise ValueError('Empty reference workload')
    return result
