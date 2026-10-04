"""Read-only H8 diagnostics. Field residuals are additive; maxima are not."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def canonical_json(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(rows[0])
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def match_architecture(design, architecture_hash, entries):
    """Match full canonical identity, never a label or an ambiguous short hash."""
    matches = [r for r in entries if r['design'] == design and
               r['architecture_sha256'] == architecture_hash]
    if len(matches) != 1:
        raise ValueError(f'Expected one architecture: {design}/{architecture_hash}; got {len(matches)}')
    return matches[0]


def source_index(nets):
    result = {}
    for name, net in sorted(nets.items()):
        source = net['source']
        if source in result:
            raise ValueError('Ambiguous physical source identity: ' + source)
        result[source] = name
    return result


def compare_bins(predicted, measured, pred_bounds, meas_bounds):
    """Per-bin temporal maxima plus aligned snapshots at both global peaks."""
    predicted, measured = np.asarray(predicted), np.asarray(measured)
    if predicted.shape != measured.shape or predicted.ndim != 2 or predicted.shape[1] != 64:
        raise ValueError('Expected aligned cycle x 64 fields')
    if not np.allclose(pred_bounds, meas_bounds, rtol=0, atol=1e-10):
        raise ValueError('Spatial bounds differ; no silent rebinning')
    pcycle, pbin = map(int, np.unravel_index(predicted.argmax(), predicted.shape))
    mcycle, mbin = map(int, np.unravel_index(measured.argmax(), measured.shape))
    p, m = predicted.max(axis=0), measured.max(axis=0)
    pr = np.argsort(np.argsort(-p, kind='stable'), kind='stable') + 1
    mr = np.argsort(np.argsort(-m, kind='stable'), kind='stable') + 1
    rows = []
    for b in range(64):
        rows.append(dict(bin_x=b % 8, bin_y=b // 8,
            predicted_value=float(p[b]), measured_value=float(m[b]), residual=float(m[b]-p[b]),
            predicted_rank=int(pr[b]), measured_rank=int(mr[b]),
            predicted_at_measured_peak_cycle=float(predicted[mcycle, b]),
            measured_at_measured_peak_cycle=float(measured[mcycle, b]),
            residual_at_measured_peak_cycle=float(measured[mcycle, b]-predicted[mcycle, b]),
            predicted_at_predicted_peak_cycle=float(predicted[pcycle, b]),
            measured_at_predicted_peak_cycle=float(measured[pcycle, b]),
            predicted_cycle_total=float(predicted[:, b].sum()),
            measured_cycle_total=float(measured[:, b].sum())))
    return rows, dict(pred_peak_bin=pbin, meas_peak_bin=mbin,
        pred_peak_cycle=pcycle, meas_peak_cycle=mcycle, peak_moved=pbin != mbin,
        pred_h8=float(p[pbin]), meas_h8=float(m[mbin]),
        top_predicted_bins=[int(b) for b in np.argsort(-p, kind='stable')[:8]],
        top_measured_bins=[int(b) for b in np.argsort(-m, kind='stable')[:8]])


def decompose_net(pred_counts, meas_counts, pred_cap, meas_cap, pred_bin, meas_bin, cycles):
    """Ordered exact substitution: activity, C, source location, unmatched nets.

    Matched sources: (Nm-Np)Cp + Nm(Cm-Cp), followed by source-bin movement.
    This is an algebraic diagnostic, not unique physical causal attribution.
    Missing C on a switched net fails; absent nets use an explicit unmatched term.
    """
    fields = {k: np.zeros((cycles, 64)) for k in ('activity', 'capacitance', 'geometry', 'unmatched')}
    if pred_counts is None and meas_counts is None:
        raise ValueError('Both net observations missing')
    for counts, cap, bin_id in ((pred_counts, pred_cap, pred_bin), (meas_counts, meas_cap, meas_bin)):
        if counts is not None:
            if len(counts) != cycles:
                raise ValueError('Cycle alignment mismatch')
            if bin_id is None or not 0 <= bin_id < 64:
                raise ValueError('Invalid source bin')
            if cap is not None and (not np.isfinite(cap) or cap < 0):
                raise ValueError('Invalid capacitance')
            if cap is None and np.any(counts):
                raise ValueError('Switched net missing capacitance')
    if pred_counts is None:
        fields['unmatched'][:, meas_bin] = np.asarray(meas_counts) * (meas_cap or 0.)
    elif meas_counts is None:
        fields['unmatched'][:, pred_bin] = -np.asarray(pred_counts) * (pred_cap or 0.)
    else:
        p, m = np.asarray(pred_counts, dtype=float), np.asarray(meas_counts, dtype=float)
        pc, mc = pred_cap or 0., meas_cap or 0.
        fields['activity'][:, pred_bin] = (m-p)*pc
        fields['capacitance'][:, pred_bin] = m*(mc-pc)
        if pred_bin != meas_bin:
            fields['geometry'][:, pred_bin] -= m*mc
            fields['geometry'][:, meas_bin] += m*mc
    return fields


def ordering(a, b, tolerance=1e-8):
    if abs(a-b) <= tolerance:
        return 'tie'
    return 'A<B' if a < b else 'A>B'


def pair_classification(pred_a, pred_b, meas_a, meas_b):
    p, m = ordering(pred_a, pred_b), ordering(meas_a, meas_b)
    return 'predicted_tie' if p == 'tie' and m != 'tie' else (
        'reversal' if p != m and p != 'tie' and m != 'tie' else 'correct')
