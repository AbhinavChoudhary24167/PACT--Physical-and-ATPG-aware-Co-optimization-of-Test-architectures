"""Exact implemented-space comparisons; missing measurements remain unknown."""
import math

OBJECTIVES = ('routed_scan_path_cost_um', 'measured_E', 'measured_H8')


def implemented_point(row):
    if row.get('status') != 'QUALIFIED':
        return None
    values = []
    for name in OBJECTIVES:
        value = row.get(name)
        if value is None or value == '' or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number < 0:
            return None
        values.append(number)
    return tuple(values)


def dominates(left, right):
    return all(a <= b for a, b in zip(left, right)) and any(a < b for a, b in zip(left, right))


def pareto_rows(rows):
    """Separate fronts by design; preserve ties and unknown/failed outcomes."""
    points = [implemented_point(row) for row in rows]
    result = []
    for index, row in enumerate(rows):
        point = points[index]
        peers = [(other, candidate) for other, candidate in zip(rows, points)
                 if other['design'] == row['design'] and candidate is not None]
        membership = None if point is None else not any(dominates(other, point) for _, other in peers)
        coordinate_unique_vs_external = None
        architecture_unique_vs_external = None
        if point is not None and row['method'] == 'P0':
            external = [(other, candidate) for other, candidate in peers if other['method'] != 'P0']
            coordinate_unique_vs_external = not any(candidate == point for _, candidate in external)
            architecture_unique_vs_external = not any(other['architecture_hash'] == row['architecture_hash'] for other, _ in external)
        result.append(dict(row, implemented_nondominated=membership,
                           coordinate_unique_vs_external=coordinate_unique_vs_external,
                           architecture_unique_vs_external=architecture_unique_vs_external,
                           pareto_status='UNASSESSABLE' if point is None else ('NONDOMINATED' if membership else 'DOMINATED')))
    return result
