"""Only positively established zero-interconnect omissions may qualify."""
import copy
import gzip
import struct
import numpy as np
import pytest
from pact.activity.spef_evidence import classify,name_map
from pact.activity.compact import read_counts
from pact.analysis.phase2b_reference import parse_spef


def evidence():
    return dict(odb_net_present=True,net_mapping_matches=True,logical_net_present=True,
        logical_connection_matches=True,driver_count=1,topology_valid=True,pin_cap_known=True,
        pin_cap_ff=0.,sink_count=0,terminal_count=1,special_net=False,wire_geometry_present=False,
        wire_present=False,special_wire_count=0,global_wire_present=False,wire_length_um=0.,
        cap_node_count=0,rseg_count=0,coupling_segment_count=0,extractor_expected_omission=True,
        driver=dict(id='buffer/Z',master='BUF_X1'),routing_status='NO_INTERCONNECT_ONE_TERMINAL')


def classify_missing(e):
    return classify('unseen','architecture_sha','n',None,True,dict(pin_cap_ff=0.),e)


def test_normal_switched_spef_keeps_ground_and_pin_contributions():
    text='*C_UNIT 1 FF\n*NAME_MAP\n*1 n\n*D_NET *1 2\n*CAP\n1 *1:1 2\n*END\n'
    extracted=parse_spef(text)['n']
    assert name_map(text)=={'*1':'n'}
    r=classify('d','arch','n',extracted,True,dict(pin_cap_ff=7.),{})
    assert r['classification']=='SPEF_COMPLETE' and r['qualification_status']=='PASS'
    assert r['effective_capacitance']==9.
    assert not r['fallback_used']


def test_positive_one_driver_no_wire_omission_is_explicit():
    r=classify_missing(evidence())
    assert r['classification']=='SPEF_ZERO_WIRE_FALLBACK' and r['qualification_status']=='PASS'
    assert r['wire_capacitance']==0. and r['effective_capacitance']==0.
    assert r['fallback_used']


@pytest.mark.parametrize('change,expected',[
    ({'wire_geometry_present':True,'wire_present':True,'wire_length_um':12.},'SPEF_EXTRACTION_ERROR'),
    ({'net_mapping_matches':False},'SPEF_MAPPING_ERROR'),
    ({'odb_net_present':False},'SPEF_MAPPING_ERROR'),
    ({'logical_connection_matches':False},'SPEF_MAPPING_ERROR'),
    ({'sink_count':1,'terminal_count':2},'SPEF_UNRESOLVED'),
    ({'cap_node_count':2},'SPEF_UNRESOLVED'),
    ({'pin_cap_known':False},'SPEF_MAPPING_ERROR'),
    ({'extractor_expected_omission':False},'SPEF_UNRESOLVED')])
def test_unsupported_omissions_fail_closed(change,expected):
    e=evidence();e.update(change)
    r=classify_missing(e)
    assert r['classification']==expected and r['qualification_status']=='FAIL'
    assert not r['fallback_used'] and r['wire_capacitance'] is None


def test_independent_liberty_mapping_disagreement_fails():
    e=evidence();e['pin_cap_ff']=3.
    assert classify_missing(e)['classification']=='SPEF_MAPPING_ERROR'


def test_reused_cache_must_match_every_complete_compressed_count(tmp_path):
    path=tmp_path/'counts.gz';cache=tmp_path/'cache.u8'
    path.write_bytes(gzip.compress(b'PACTCN01'+struct.pack('<II',1,2)+struct.pack('<I',1)+b'n'+b'\x01\x02PACTDONE'))
    cache.write_bytes(b'\x01\x02')
    a,_=read_counts(path,['n'],2,existing_mmap=cache)
    assert a.tolist()==[[1],[2]] and not a.flags.writeable
    del a
    cache.write_bytes(b'\x01\x03')
    with pytest.raises(ValueError,match='differs'):
        read_counts(path,['n'],2,existing_mmap=cache)
