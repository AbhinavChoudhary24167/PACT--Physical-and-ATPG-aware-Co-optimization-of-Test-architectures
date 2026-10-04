"""Run unchanged extraction/simulation/analysis with the new gate adapter."""
import argparse
import physical_effect as frozen
from pact_generalization import ROOT

original_run=frozen.run


def run(command,folder,name):
    if name=='export':
        assert command[-2]==ROOT/'scripts/physical_effect_export.py'
        command=[*command[:-2],ROOT/'scripts/pact_generalization_export.py',command[-1]]
    return original_run(command,folder,name)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--design',required=True)
    a=p.parse_args()
    frozen.run=run
    frozen.execute(a.design)
