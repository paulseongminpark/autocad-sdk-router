#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_ops.db -- database / transform write ops (CAD OS Layer, Lane E family
split).

No patch op in this family has a live native write handler yet. Placeholder
family module so a future database/transform write op lands here without
touching entities.py / blocks.py / tables.py.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

WRITE_OP_MAP: Dict[str, str] = {}


def build_job_args(native_op: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No db-family native op is wired yet; always None (not our native_op)."""
    return None


def ir_op_for(ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """No IR entity kind regenerates a database/transform op yet; always None."""
    return None
