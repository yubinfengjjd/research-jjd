"""Keep training entrypoints and Windows-only unittest tests out of pytest.

The complete managed-experiment suite runs separately on windows-latest via
unittest discovery. Generated-data trainer/evaluator scripts are not pytest
modules and share filenames across fixtures.
"""
collect_ignore = ["medimg-experiment/tests", "medimg-experiment/assets", "sci-figure-replica/tests"]
# Replica has its own conftest/import namespace and Windows/R runtime tests.
# Run it separately as documented in sci-figure-replica/README.md.
