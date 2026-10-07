"""Catalog service for AI Library."""

import sys

# Keep a single canonical module object even if tests/import machinery resolve
# this package via its workspace path.
sys.modules.setdefault("services.catalog.src.catalog", sys.modules[__name__])
