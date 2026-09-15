"""Test package bootstrap.

Importing the package first runs :mod:`backend.tests.helpers`, which configures
the throwaway database, disables live network lookups and puts ``backend`` on
``sys.path`` before any test module body executes.
"""

from . import helpers  # noqa: F401  (import for side effects)
