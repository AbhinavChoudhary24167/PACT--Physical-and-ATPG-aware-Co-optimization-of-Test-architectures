#!/usr/bin/env python3
"""Recompute predeclared placement-distinctness after partial campaign resumes."""
from phase0b_pipeline import qualify_seeds


if __name__ == "__main__":
    for design in ("s5378", "s9234", "s15850"):
        qualify_seeds(design)
