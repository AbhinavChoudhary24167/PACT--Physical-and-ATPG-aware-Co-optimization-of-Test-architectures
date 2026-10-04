"""Frozen two-objective role selection retained for qualification regressions."""
import math
from pact.phase0d.pareto import nondominated


def select(rows):
    """Exact two-objective frontier (constant third coordinate reuses Pareto utility)."""
    unique = {}
    for row in rows:
        sha = row['architecture_sha256']
        if sha in unique:
            assert all(math.isclose(a, b, abs_tol=1e-9, rel_tol=0) for a, b in
                       zip(row['objectives'], unique[sha]['objectives']))
            unique[sha]['source_runs'].extend(row['source_runs'])
        else:
            unique[sha] = dict(row, source_runs=list(row['source_runs']))
    archive = nondominated(unique.values(), key=lambda r: (*r['objectives'], 0))
    archive.sort(key=lambda r: (*r['objectives'], r['architecture_sha256']))
    low = [min(r['objectives'][i] for r in archive) for i in range(2)]
    span = [max(r['objectives'][i] for r in archive) - low[i] for i in range(2)]
    for row in archive:
        row['normalized_utopia_distance_squared'] = sum(
            ((row['objectives'][i] - low[i]) / span[i]) ** 2 if span[i] else 0
            for i in range(2))
    roles = {
        'physical_extreme': min(archive, key=lambda r: (*r['objectives'], r['architecture_sha256'])),
        'balanced': min(archive, key=lambda r: (r['normalized_utopia_distance_squared'],
                                              *r['objectives'], r['architecture_sha256'])),
        'activity_extreme': min(archive, key=lambda r: (r['objectives'][1], r['objectives'][0],
                                                     r['architecture_sha256'])),
    }
    selected = []
    for row in archive:
        selected_roles = [role for role, item in roles.items() if item is row]
        if selected_roles:
            selected.append(dict(row, selection_roles=selected_roles,
                                 rationale='Exact objective extremes or minimum squared normalized utopia distance; ties: physical, activity, SHA256.'))
    return archive, selected
