"""Compile repaired source-net topology once, update outgoing loads locally."""
from copy import deepcopy
import numpy as np
from pact.analysis.phase2cr_loads import CAP_PER_UM, validate, construct_with_audit
from pact.analysis.phase2a_shift import fixed_bins
from pact.scan.validate import validate_scan
from . import kernels


def add_long_chain(field,d,bins,weights,deadline):
    """Toeplitz product via FFT, tiled over patterns and 10 spatial bins.

    Used for long chains to avoid O(P*L*m) startup. Work O(P*B*L*log L)
    per chain; temporary memory O(P*L + B_tile*L), never m by L.
    """
    import time
    from scipy.fft import rfft,irfft,next_fast_len
    m=len(bins);length=field.shape[1];size=next_fast_len(d.shape[1]+m-1)
    transitions=rfft(d,n=size,axis=1)
    for start in range(0,100,10):
        mapping=np.zeros((m,10,2))
        keep=np.flatnonzero((bins>=start)&(bins<start+10))
        mapping[keep,bins[keep]-start]=weights[keep]
        transfer=rfft(mapping,n=size,axis=0)
        for p in range(len(d)):
            if deadline is not None and time.perf_counter()>=deadline:raise TimeoutError('FFT initialization deadline')
            value=irfft(transitions[p,:,None,None]*transfer,n=size,axis=0)
            field[p,:,start:start+10,:]+=value[m-1:m-1+length]


class PlacedCosts:
    def __init__(self, architecture, graph, loads, bounds):
        validate_scan(architecture)
        # The strict repaired exporter is K=2. Generic inputs use the explicit
        # compiled-array constructor below rather than silently relaxing it.
        validate(architecture, graph, loads)
        construct_with_audit(architecture, graph, loads)  # ownership check once
        self.names = tuple(c.name for c in architecture.cells)
        self.index = {n:i for i,n in enumerate(self.names)}
        self.xy = np.array([(c.x_um,c.y_um) for c in architecture.cells])
        self.bins = fixed_bins(self.xy,bounds).astype(np.int32)
        self.inputs = np.array([graph['scan_ports']['test_si'],graph['scan_ports']['test_si_1']])
        self.outputs = np.array([graph['scan_ports']['test_so'],graph['scan_ports']['test_so_1']])
        g = deepcopy(graph)
        ep = g['scan_endpoints']['chain0_so']
        source, child = ep['original_source_net'],ep['output_net']
        g['nets'][source]['sinks'].remove(dict(master=ep['buffer_master'],pin=ep['input_pin'],xy=ep['buffer_xy']))
        g['transparent'][source].remove(child)
        g['nets'][child]['ports'].append(ep['port_xy'])
        def cone(roots):
            todo, seen, pin, wire = list(roots),set(),0.,0.
            while todo:
                name=todo.pop()
                if name in seen: continue
                seen.add(name); net=g['nets'][name]
                pts=np.array([net['driver_xy']]+[s['xy'] for s in net['sinks']]+net['ports'])
                pin += sum(loads[s['master'],s['pin']] for s in net['sinks'])
                wire += np.ptp(pts,axis=0).sum()
                todo.extend(g['transparent'].get(name,[]))
            return pin,wire
        self.base = np.array([cone(g['FFs'][n]['roots'].values()) for n in self.names])
        boxes=[]
        for n in self.names:
            net=g['nets'][g['FFs'][n]['roots']['Q']]
            pts=np.array([net['driver_xy']]+[s['xy'] for s in net['sinks']]+net['ports'])
            boxes.append([*pts.min(axis=0),*pts.max(axis=0)])
        self.boxes=np.asarray(boxes)
        self.si=np.array([loads[g['FFs'][n]['master'],'SI'] for n in self.names])
        self.buffer_xy=np.asarray(ep['buffer_xy'])
        self.branch=np.array(cone([child]))+np.array([loads[ep['buffer_master'],ep['input_pin']],0.])
        self.scope='qualified_repaired_M3_M5'

    @classmethod
    def generic(cls, architecture, patterns, inputs, outputs, bounds, base_pin, base_wire, si, boxes):
        """Explicit functional source arrays; direct SO topology for arbitrary K."""
        validate_scan(architecture)
        self=cls.__new__(cls)
        self.names=tuple(c.name for c in architecture.cells)
        self.index={n:i for i,n in enumerate(self.names)}
        self.xy=np.array([(c.x_um,c.y_um) for c in architecture.cells])
        self.bins=fixed_bins(self.xy,bounds).astype(np.int32)
        self.inputs=np.asarray(inputs,float);self.outputs=np.asarray(outputs,float)
        self.base=np.column_stack((base_pin,base_wire)).astype(float)
        self.si=np.asarray(si,float);self.boxes=np.asarray(boxes,float)
        self.buffer_xy=None;self.branch=np.zeros(2)
        self.scope='generic_direct_SO_M3_M5'
        n,k=len(self.names),len(architecture.chains)
        for value,shape in ((self.inputs,(k,2)),(self.outputs,(k,2)),(self.base,(n,2)),(self.si,(n,)),(self.boxes,(n,4))):
            if value.shape!=shape or not np.all(np.isfinite(value)): raise ValueError('Invalid compiled placed arrays')
        if np.any(self.base<0) or np.any(self.si<0) or np.any(self.boxes[:,:2]>self.boxes[:,2:]): raise ValueError('Invalid load/bbox')
        return self

    def weight(self, node, successor, chain):
        pin,wire=self.base[node]
        if successor>=0:
            point=self.xy[successor];pin+=self.si[successor]
        elif chain==0 and self.buffer_xy is not None:
            point=self.buffer_xy;pin+=self.branch[0];wire+=self.branch[1]
        else: point=self.outputs[chain]
        x0,y0,x1,y1=self.boxes[node]
        wire+=max(x1,point[0])-min(x0,point[0])+max(y1,point[1])-min(y0,point[1])-(x1-x0+y1-y0)
        return pin+CAP_PER_UM*wire,wire

    def edge(self, order, chain, position):
        if position==-1: a,b=self.inputs[chain],self.xy[order[0]]
        elif position==len(order)-1: a,b=self.xy[order[-1]],self.outputs[chain]
        else: a,b=self.xy[order[position]],self.xy[order[position+1]]
        return float(abs(a[0]-b[0])+abs(a[1]-b[1]))


class ShiftState:
    """One mutable exact field; rejected changes are inverted, never copied.

    Chain capacities are fixed. A patch is a dict of chain -> (positions, nodes),
    with s changed positions. Physical deltas inspect at most 2s+K boundaries.
    Binary transition diagonals and per-position bin/weight arrays are retained.
    """
    def __init__(self, costs, patterns, orders, deadline=None):
        import time
        self.costs=costs;self.patterns=patterns
        self.orders=[np.asarray(o,np.int32).copy() for o in orders]
        self.longest=max(map(len,orders))
        field_bytes=len(patterns)*self.longest*100*2*8
        if field_bytes>1024**3:
            raise ValueError(f'Exact field needs {field_bytes/1024**3:.2f} GiB; increase K or reduce input pattern count explicitly (1 GiB field limit)')
        self.field=np.zeros((len(patterns),self.longest,100,2))
        self.ds=[];self.bins=[];self.weights=[]
        self.physical=0.
        for ci,o in enumerate(self.orders):
            if deadline is not None and time.perf_counter()>=deadline: raise TimeoutError('Activity initialization deadline')
            d=kernels.diagonals(patterns,o,self.longest)
            b=costs.bins[o].copy()
            w=np.array([costs.weight(int(n),int(o[j+1]) if j+1<len(o) else -1,ci) for j,n in enumerate(o)])
            if len(o)>1024:add_long_chain(self.field,d,b,w,deadline)
            else:kernels.add_chain(self.field,d,b,w)
            self.ds.append(d);self.bins.append(b);self.weights.append(w)
            self.physical+=sum(costs.edge(o,ci,j) for j in range(-1,len(o)))
        self.metrics=kernels.reduce_field(self.field)

    def change(self, patch):
        undo={}
        for ci,(positions,nodes) in patch.items():
            o=self.orders[ci];positions=np.asarray(positions,np.int32)
            undo[ci]=(positions,o[positions].copy())
            edges=sorted(set(int(j) for p in positions for j in (p-1,p)))
            before=sum(self.costs.edge(o,ci,j) for j in edges)
            o[positions]=nodes
            self.physical+=sum(self.costs.edge(o,ci,j) for j in edges)-before
            rs=sorted({int(r) for j in positions for r in (self.longest-1-j,self.longest-j,-j,-j-1) if 1-len(o)<=r<self.longest})
            kernels.update_diagonals(self.field,self.ds[ci],self.patterns,o,self.bins[ci],self.weights[ci],np.asarray(rs,np.int32))
            touched=np.asarray([j for j in edges if j>=0],np.int32)
            weights=np.array([self.costs.weight(int(o[j]),int(o[j+1]) if j+1<len(o) else -1,ci) for j in touched])
            kernels.update_columns(self.field,self.ds[ci],self.bins[ci],self.weights[ci],touched,self.costs.bins[o[touched]].copy(),weights)
        return undo

    def score(self):
        self.metrics=kernels.reduce_field(self.field)
        return np.r_[self.physical,self.metrics]

    @property
    def bytes(self):
        return self.field.nbytes+sum(a.nbytes for group in (self.orders,self.ds,self.bins,self.weights) for a in group)
