"""Small adversarial fixtures for physical accounting and weighted statistics."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.stats import spearmanr, kendalltau, pearsonr

ROOT=Path(__file__).resolve().parents[2]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class Inst:
    def __init__(self,name,master): self.name=name;self.master=master;self.terms={}
    def getName(self): return self.name
    def getMaster(self): return SimpleNamespace(getName=lambda:self.master)
    def getLocation(self): return (0,0)
    def findITerm(self,pin): return self.terms.get(pin)

class Net:
    def __init__(self,name,length): self.name=name;self.length=length;self.terms=[]
    def getName(self): return self.name
    def getITerms(self): return self.terms
    def getBTerms(self): return []
    def getWire(self): return None if self.length is None else SimpleNamespace(getLength=lambda:self.length)
    def getCapNodes(self): return []
    def getRSegs(self): return []

def connect(inst,pin,net,direction):
    term=SimpleNamespace(getNet=lambda:net,getIoType=lambda:direction,
        getInst=lambda:inst,getMTerm=lambda:SimpleNamespace(getName=lambda:pin))
    inst.terms[pin]=term;net.terms.append(term)

def physical_fixture():
    ff=Inst('ff','SDFF_X1');buf=Inst('b','BUF_X1');inv=Inst('i','INV_X1');logic=Inst('g','AND2_X1')
    nets={n:Net(n,l) for n,l in [('q',100),('bq',20),('iq',10),('qn',3)]}
    for inst,pin,net,direction in [(ff,'Q','q','OUTPUT'),(ff,'QN','qn','OUTPUT'),
        (ff,'SI','q','INPUT'),(ff,'D','q','INPUT'),(buf,'A','q','INPUT'),
        (buf,'Z','bq','OUTPUT'),(inv,'A','bq','INPUT'),(inv,'ZN','iq','OUTPUT'),
        (logic,'A1','bq','INPUT'),(logic,'A2','iq','INPUT'),(ff,'RN','qn','INPUT')]:
        connect(inst,pin,nets[net],direction)
    block=SimpleNamespace(getDbUnitsPerMicron=lambda:1,getInsts=lambda:[ff,buf,inv,logic],findNet=nets.get)
    arch={'cells':[{'name':'ff','x_um':0,'y_um':0}]}
    return block,arch,nets

def test_full_fanout_tree_not_scan_distance_and_no_sink_multiplication(monkeypatch):
    monkeypatch.setitem(sys.modules,'odb',SimpleNamespace())
    module=load('phase2a_extract_odb');block,arch,nets=physical_fixture()
    result=module.extract(block,arch)
    assert result['FFs']['ff']['wire_length_um']==133
    assert result['summary']['unique_driven_nets']==4
    assert result['summary']['connected_QN_outputs']==1
    assert result['summary']['transparent_branches']==2
    # Removing a functional branch's routed wire must fail, not silently become zero.
    nets['iq'].length=None
    with pytest.raises(AssertionError,match='Missing routed wire'): module.extract(block,arch)

def test_weighted_rank_statistics_match_replicated_sample():
    module=load('phase2a_validate')
    x=np.array([1.,2.,2.,4.]);y=np.array([4.,1.,1.,3.]);weights=np.array([1,2,1,3])
    result=module.weighted_corr(x,y,weights)
    xx=np.repeat(x,weights);yy=np.repeat(y,weights)
    assert result['spearman']==pytest.approx(spearmanr(xx,yy).statistic)
    assert result['kendall_tau_b']==pytest.approx(kendalltau(xx,yy).statistic)
    assert result['pearson']==pytest.approx(pearsonr(xx,yy).statistic)
    assert module.correlations([1,2,3],[5,5,5])==dict(spearman=None,kendall_tau_b=None,pearson=None)
