"""Fail-closed capacitance classification for explicitly bound implementations."""
import hashlib
import json
import math
from pathlib import Path
import re


def binding(path):
    path=Path(path)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return dict(path=str(path.resolve()),sha256=h.hexdigest(),bytes=path.stat().st_size)


def checked(item):
    actual=binding(item['path'])
    if actual['sha256']!=item['sha256'] or actual['bytes']!=item['bytes']:
        raise ValueError('Missing-SPEF evidence binding changed: '+item['path'])
    return Path(item['path'])


def name_map(text):
    names={}; in_map=False
    for line in text.splitlines():
        fields=line.split()
        if not fields: continue
        if fields[0]=='*NAME_MAP': in_map=True; continue
        if in_map and re.fullmatch(r'\*\d+',fields[0]):
            if len(fields)!=2 or fields[0] in names:
                raise ValueError('Ambiguous SPEF NAME_MAP')
            names[fields[0]]=fields[1]
        elif in_map: in_map=False
    if len(set(names.values()))!=len(names):
        raise ValueError('Duplicate canonical SPEF names')
    return names


def classify(design, architecture, net, extracted, name_map_present, mapping, evidence):
    """Only positively proved single-driver/no-interconnect omissions may pass.

    A routed net, unknown parasitics, unknown pin load, identity mismatch or
    sink requiring interconnect cannot use this fallback. Pin load is always
    kept in the effective capacitance rather than replaced by wire zero.
    """
    e=evidence or {}
    record=dict(design=design,architecture=architecture,net=net,
        spef_name_map_present=name_map_present,spef_d_net_present=extracted is not None,
        odb_net_present=e.get('odb_net_present',False),driver=e.get('driver'),
        sink_count=e.get('sink_count'),sink_pin_capacitance=e.get('pin_cap_ff'),
        pin_capacitance=mapping.get('pin_cap_ff'),routing_status=e.get('routing_status','UNAVAILABLE'),
        wire_length=e.get('wire_length_um'),wire_geometry_present=e.get('wire_geometry_present'),
        routed_geometry_present=e.get('wire_geometry_present'),wire_capacitance=None,
        extracted_capacitance_source=None,fallback_used=False,classification='SPEF_UNRESOLVED',
        qualification_status='FAIL',reason='Positive zero-interconnect evidence unavailable',
        implementation_evidence=e)
    def fail(state,reason):
        record.update(classification=state,reason=reason)
        return record
    pin=mapping.get('pin_cap_ff')
    if pin is None or not math.isfinite(pin) or pin<0:
        return fail('SPEF_UNRESOLVED','Liberty sink/pin capacitance is unavailable or invalid')
    if extracted is not None:
        if any(not math.isfinite(extracted[k]) or extracted[k]<0 for k in ('ground_ff','coupling_ff')):
            return fail('SPEF_EXTRACTION_ERROR','Invalid extracted capacitance')
        record.update(classification='SPEF_COMPLETE',qualification_status='PASS',reason='Valid original D_NET record',
            wire_capacitance=extracted['ground_ff'],extracted_capacitance_source='Original SPEF ground capacitance',
            effective_capacitance=extracted['ground_ff']+pin)
        return record
    if not name_map_present or not e.get('odb_net_present') or not e.get('net_mapping_matches'):
        return fail('SPEF_MAPPING_ERROR','SPEF/ODB/source mapping identity is missing or disagrees')
    if not e.get('logical_net_present') or not e.get('logical_connection_matches'):
        return fail('SPEF_MAPPING_ERROR','Logical net/driver/sink connections do not match ODB')
    if e.get('driver_count')!=1 or not e.get('topology_valid') or not e.get('pin_cap_known'):
        return fail('SPEF_MAPPING_ERROR','Unique valid driver/sinks or exact Liberty loads are not established')
    if not math.isclose(pin,e.get('pin_cap_ff',float('nan')),rel_tol=1e-10,abs_tol=1e-10):
        return fail('SPEF_MAPPING_ERROR','Mapped sink-pin capacitance differs from independently parsed Liberty')
    if e.get('wire_geometry_present') or e.get('wire_present') or e.get('special_wire_count',1)>0 or e.get('global_wire_present'):
        return fail('SPEF_EXTRACTION_ERROR','Routed geometry is present without extracted capacitance')
    if e.get('sink_count')!=0 or e.get('terminal_count')!=1 or e.get('special_net'):
        return fail('SPEF_UNRESOLVED','A sink or special net may require interconnect; no zero-wire proof')
    if e.get('wire_length_um')!=0 or any(e.get(k)!=0 for k in ('cap_node_count','rseg_count','coupling_segment_count')):
        return fail('SPEF_UNRESOLVED','Wire/parasitic absence has not been established')
    if not e.get('extractor_expected_omission'):
        return fail('SPEF_UNRESOLVED','Expected extractor omission has not been independently reproduced')
    record.update(classification='SPEF_ZERO_WIRE_FALLBACK',qualification_status='PASS',fallback_used=True,
        reason='One exact driver, no sinks/ports, no wire/via/special/global geometry, no RC objects; same frozen OpenRCX omission reproduced',
        wire_capacitance=0.,effective_capacitance=pin,
        extracted_capacitance_source='Bound ODB/Liberty plus frozen-extractor no-interconnect reproducer')
    return record


def resolve(folder,mapping,spef,names,totals,evidence_path):
    """Emit every missing switched-net diagnosis before accepting or rejecting."""
    folder=Path(folder); evidence_path=Path(evidence_path)
    bundle=json.loads(evidence_path.read_text())
    from pact.scan.model import ScanArchitecture
    root_manifest=json.loads((folder.parents[1]/'manifest.json').read_text())
    row=next(r for r in root_manifest['rows'] if r['design']==folder.parent.name and r['role']==folder.name)
    if row['design']!=bundle['design'] or ScanArchitecture.from_json(Path(row['architecture']['path'])).sha256()!=bundle['architecture']:
        raise ValueError('Missing-SPEF evidence design/architecture differs from measurement')
    for item in bundle['bindings'].values(): checked(item)
    for name,key in (('net_mapping.json','mapping'),('extracted.spef','SPEF')):
        if binding(folder/name)['sha256']!=bundle['bindings'][key]['sha256']:
            raise ValueError('Evidence does not bind this activity '+name)
    maps=name_map((folder/'extracted.spef').read_text())
    rows=[]; counts=dict(spef_complete_switched_nets=0,spef_zero_wire_fallback_nets=0,
        spef_mapping_error_nets=0,spef_extraction_error_nets=0,spef_unresolved_nets=0)
    result=dict(spef)
    for i,n in enumerate(names):
        if not totals[i]: continue
        row=classify(bundle['design'],bundle['architecture'],n,spef.get(n),n in maps.values(),
            mapping['nets'][n],bundle['nets'].get(n))
        key={'SPEF_COMPLETE':'spef_complete_switched_nets','SPEF_ZERO_WIRE_FALLBACK':'spef_zero_wire_fallback_nets',
            'SPEF_MAPPING_ERROR':'spef_mapping_error_nets','SPEF_EXTRACTION_ERROR':'spef_extraction_error_nets',
            'SPEF_UNRESOLVED':'spef_unresolved_nets'}[row['classification']]
        counts[key]+=1
        if n not in spef:
            rows.append(row)
            if row['qualification_status']=='PASS':
                result[n]=dict(ground_ff=0.,coupling_ff=0.,declared_ff=0.,resistors=0,capacitors=0,
                    classification=row['classification'])
    diagnostic=dict(schema='pact_missing_spef_diagnostics_v1',design=bundle['design'],architecture=bundle['architecture'],
        evidence=binding(evidence_path),records=rows,counters=counts,
        status='PASS' if not any(r['qualification_status']!='PASS' for r in rows) else 'FAIL',
        invariant='Missing SPEF data is not zero capacitance; only bound positive no-interconnect proof permits wire zero')
    (folder/'missing_spef_diagnostics.json').write_text(json.dumps(diagnostic,indent=2,sort_keys=True)+'\n')
    if diagnostic['status']!='PASS' or any(counts[k] for k in ('spef_mapping_error_nets','spef_extraction_error_nets','spef_unresolved_nets')):
        raise ValueError('Missing switched-net SPEF remains unqualified; see missing_spef_diagnostics.json')
    return result,diagnostic
