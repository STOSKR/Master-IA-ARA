"""Reproducibility helpers for deterministic local runs."""

import os
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class SeedReport:
    """Result metadata for seed initialization."""

    seed: int
    python_random_seeded: bool
    numpy_seeded: bool


def set_global_seed(seed: int) -> SeedReport:
    """Set deterministic seeds for standard random generators when available.

    The function only performs user-space operations and tolerates missing optional
    dependencies (for example NumPy not installed in early project phases).
    """

    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    numpy_seeded = False
    try:
        import numpy as np  # type: ignore[import-not-found]

        np.random.seed(seed)
        numpy_seeded = True
    except ImportError:
        numpy_seeded = False

    return SeedReport(seed=seed, python_random_seeded=True, numpy_seeded=numpy_seeded)
