"""FF-boundary recorder for validated BASIC_SCAN capture responses."""
import numpy as np
from pact.scan.phase0c import parallel_schedule, verify_parallel_schedule


def record_test(arch, loads, captures, final_unload=True):
    names = sorted(c.name for c in arch.cells)
    if len(loads) != len(captures) or not loads: raise ValueError('Pattern/capture count mismatch')
    for record in [*loads,*captures]:
        if set(record) != set(names) or any(b not in (0,1) for b in record.values()):
            raise ValueError('Unknown/missing FF capture/load bit')
    state = dict.fromkeys(names,0)
    states,toggles,si,so,modes,boundaries = [],[],[],[],[],[]
    def append(before, inputs, outputs, mode):
        states.append([state[n] for n in names])
        toggles.append([before[n]^state[n] for n in names])
        si.append(inputs);so.append(outputs);modes.append(mode)
    def shift(target, mode):
        expected = verify_parallel_schedule(arch,target,state.copy())
        outputs = [[] for _ in arch.chains]
        for inputs in parallel_schedule(arch,target):
            before=state.copy(); out=[]
            for j,chain in enumerate(arch.chains):
                out.append(before[chain.cells[-1]]); outputs[j].append(out[-1])
                state[chain.cells[0]]=inputs[j]
                for left,right in zip(chain.cells,chain.cells[1:]): state[right]=before[left]
            append(before,list(inputs),out,mode)
        if outputs != expected['scan_out'] or state != target: raise ValueError('Shift proof failed')
    for i,(load,capture) in enumerate(zip(loads,captures)):
        start=len(states); shift(load,'load')
        before=state.copy(); state.update(capture)
        append(before,[-1]*len(arch.chains),[-1]*len(arch.chains),'capture')
        boundaries.append(dict(pattern=i,load_start=start,capture_cycle=len(states)-1))
    if final_unload: shift(dict.fromkeys(names,0),'final_unload_zero_fill')
    return dict(names=np.asarray(names),states_packed=np.packbits(states,axis=1),
        toggles_packed=np.packbits(toggles,axis=1),SI=np.asarray(si,dtype=np.int8),
        SO=np.asarray(so,dtype=np.int8),modes=np.asarray(modes)), boundaries
