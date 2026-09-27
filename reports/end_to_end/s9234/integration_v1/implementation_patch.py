"""Run with openroad -python -exit; changes scan connectivity only."""
import argparse
from pathlib import Path
import sys
p = argparse.ArgumentParser()
p.add_argument("--repository", type=Path, required=True)
p.add_argument("--source", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.repository / "src"))
from pact.integration.implementation import apply
apply(Path(__file__).resolve().parent, a.repository, a.source, a.output)
