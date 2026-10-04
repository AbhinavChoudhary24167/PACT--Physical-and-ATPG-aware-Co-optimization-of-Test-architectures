"""Net-name changes are allowed only after exact functional-source checks."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from pact_generalization_identity import identity_map


def fixture(tmp_path,buffer_master='BUF_X2',extra='',data='data'):
    lib=tmp_path/'library.lib'
    lib.write_text('''library(x) {
cell(SDFF_X1) { pin(D) { direction : input; } pin(CK) { direction : input; }
pin(SI) { direction : input; } pin(SE) { direction : input; } pin(Q) { direction : output; } }
cell(BUF_X2) { pin(A) { direction : input; } pin(Z) { direction : output; function : "A"; } }
cell(INV_X1) { pin(A) { direction : input; } pin(ZN) { direction : output; function : "!A"; } }
}''')
    source=tmp_path/'source.v'
    placed=tmp_path/'placed.v'
    original='''module sample(CK,test_si,test_se,data,other,test_so);
input CK; input test_si; input test_se; input data; input other; output test_so;
SDFF_X1 a (.SI(test_si),.SE(test_se),.Q(n),.D(data),.CK(CK));
SDFF_X1 b (.SI(n),.SE(test_se),.Q(test_so),.D(data),.CK(CK));
endmodule
'''
    source.write_text(original)
    bufpin='ZN' if buffer_master=='INV_X1' else 'Z'
    placed.write_text(original.replace('.Q(n)', '.Q(renamed)').replace('.D(data)',f'.D({data})',1)
        .replace('endmodule',f'{buffer_master} repair (.A(renamed),.{bufpin}(n));\n'+extra+'\nendmodule'))
    return source,placed,SimpleNamespace(pseudo_primary_inputs=('a','b')),lib


def test_buffer_size_and_net_label_preserve_identity(tmp_path):
    records,proof=identity_map(*fixture(tmp_path))
    assert proof['status']=='PASS' and proof['Q_net_renames']=={'a':{'source':'n','placed':'renamed'}}
    assert [r['physical_instance'] for r in records]==['a','b']


def test_functional_data_change_rejected(tmp_path):
    with pytest.raises(ValueError,match='Changed functional source'):
        identity_map(*fixture(tmp_path,data='other'))


def test_inversion_parity_change_rejected(tmp_path):
    with pytest.raises(ValueError,match='Changed functional source'):
        identity_map(*fixture(tmp_path,buffer_master='INV_X1'))


def test_ambiguous_alias_rejected(tmp_path):
    with pytest.raises(ValueError,match='ambiguous signal driver'):
        identity_map(*fixture(tmp_path,extra='BUF_X2 duplicate (.A(renamed),.Z(n));'))
