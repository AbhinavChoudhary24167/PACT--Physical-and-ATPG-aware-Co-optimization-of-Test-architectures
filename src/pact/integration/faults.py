"""Optional existing FAN stuck-at replay, never ATPG regeneration."""
from pathlib import Path
import re
import subprocess
from .permutation import file_hash, write
from pact.test.pattern_parser import parse_fan_pat


def parse_fault_report(text):
    faults = set(re.findall(r'^#\s+(SA[01])\s+DT\s+(.+?)\s*$', text, re.M))
    total = re.search(r'number of faults:\s*(\d+)', text)
    coverage = re.search(r'fault coverage\s*[:=]?\s*([\d.]+)', text, re.I)
    if not faults or total is None or coverage is None:
        raise ValueError('FAN did not provide nonempty detected-fault list, total and coverage')
    return faults, int(total[1]), float(coverage[1])


def parse_statistics(text):
    def number(label):
        found = re.search(label+r'\s+(\d+(?:\.\d+)?)', text, re.I)
        if not found:
            raise ValueError(f'FAN statistics missing {label}')
        return float(found[1])
    return dict(coverage=number('fault coverage'), detected=int(number(r'DT \(detected\)')),
                total=int(number(r'FU \(full\)')), patterns=int(number('#Patterns')))


def replay_faults(fan_root, design, original, recovered, netlist, output, timeout=180):
    exe = fan_root/'bin/opt/fan'
    lib = fan_root/'techlib/mod_nangate45.mdt'
    if not exe.is_file() or not lib.is_file():
        return dict(status='BLOCKED', reason='FAN executable or modified Nangate library unavailable')
    results = []
    output.mkdir(parents=True, exist_ok=True)
    for label, patterns in (('original', original), ('remapped', recovered)):
        paths = [lib.resolve(), netlist.resolve(), patterns.resolve()]
        if any(re.search(r'\s|["\r\n]', str(p)) for p in paths):
            raise ValueError('FAN command parser adapter requires paths without whitespace/quotes')
        script = output/f'{label}.script'
        script.write_text('\n'.join((f'read_lib {paths[0]}', f'read_netlist {paths[1]}',
                          'build_circuit --frame 1', f'read_pattern {paths[2]}',
                          'set_fault_type saf', 'add_fault -a', 'run_fault_sim',
                          'report_statistics', 'exit'))+'\n', encoding='utf-8')
        run = subprocess.run([str(exe.resolve()), '-f', str(script.resolve())], cwd=fan_root,
                             capture_output=True, text=True, timeout=timeout)
        (output/f'{label}.stdout.txt').write_text(run.stdout, encoding='utf-8')
        (output/f'{label}.stderr.txt').write_text(run.stderr, encoding='utf-8')
        if run.returncode or '**ERROR' in run.stdout+run.stderr:
            raise ValueError(f'FAN {label} replay failed; inspect saved logs')
        results.append(parse_statistics(run.stdout))
    old, new = results
    if old['patterns'] != len(parse_fan_pat(original).patterns) or new['patterns'] != len(parse_fan_pat(recovered).patterns):
        raise ValueError('FAN did not simulate every supplied pattern')
    # The qualified FAN reporter is probed separately from successful simulation:
    # its known SDFF/negative-gate-ID dereference can crash on a complete list.
    probe = output/'detected_fault_probe.script'
    probe.write_text((output/'original.script').read_text().replace('exit\n','report_fault -s DT\nexit\n'))
    detail = subprocess.run([str(exe.resolve()), '-f', str(probe.resolve())], cwd=fan_root,
                            capture_output=True, text=True, timeout=timeout)
    (output/'detected_fault_probe.stdout.txt').write_text(detail.stdout,encoding='utf-8')
    (output/'detected_fault_probe.stderr.txt').write_text(detail.stderr,encoding='utf-8')
    write(output/'detected_fault_probe.execution.json', dict(exit_code=detail.returncode,
          command=[str(exe.resolve()), '-f', str(probe.resolve())]))
    lost = added = None
    sets_status = 'BLOCKED'
    reason = f'FAN report_fault -s DT terminated with exit {detail.returncode}; complete detected-fault identity list unavailable'
    if detail.returncode == 0 and '**ERROR' not in detail.stdout+detail.stderr:
        old_set,_,_ = parse_fault_report(detail.stdout)
        second = output/'remapped_faults.script'
        second.write_text((output/'remapped.script').read_text().replace('exit\n','report_fault -s DT\nexit\n'))
        detailed_new = subprocess.run([str(exe.resolve()), '-f', str(second.resolve())], cwd=fan_root,
                                     capture_output=True, text=True, timeout=timeout)
        (output/'remapped_faults.stdout.txt').write_text(detailed_new.stdout,encoding='utf-8')
        (output/'remapped_faults.stderr.txt').write_text(detailed_new.stderr,encoding='utf-8')
        if detailed_new.returncode == 0 and '**ERROR' not in detailed_new.stdout+detailed_new.stderr:
            new_set,_,_ = parse_fault_report(detailed_new.stdout)
            lost,added = sorted(old_set-new_set),sorted(new_set-old_set)
            write(output/'original.detected_faults.json', sorted(old_set))
            write(output/'remapped.detected_faults.json', sorted(new_set))
            sets_status = 'PASS' if not lost and not added else 'FAIL'
            reason = None
    coverage_status = 'PASS' if old == new else 'FAIL'
    result = dict(status='FAIL' if coverage_status == 'FAIL' or sets_status == 'FAIL' else sets_status,
                  coverage_equivalence=coverage_status, detected_fault_set_equivalence=sets_status, reason=reason,
                  scope='FAN BASIC_SCAN single-frame stuck-at on original functional netlist; remapped PPI recovered by cycle replay',
                  original_detected_faults=old['detected'], remapped_detected_faults=new['detected'],
                  original_total_faults=old['total'], remapped_total_faults=new['total'],
                  original_coverage=old['coverage'], PACT_coverage=new['coverage'], difference=new['coverage']-old['coverage'],
                  lost_faults=lost, unexpected_new_differences=added,
                  executable_sha256=file_hash(exe), library_sha256=file_hash(lib),
                  netlist_sha256=file_hash(netlist), original_patterns_sha256=file_hash(original),
                  recovered_patterns_sha256=file_hash(recovered))
    write(output/'result.json', result)
    return result
