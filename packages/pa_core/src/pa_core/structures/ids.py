from __future__ import annotations

import hashlib
import json
from typing import Sequence


def build_structure_id(
    *,
    kind: str,
    start_bar_id: int,
    end_bar_id: int | None,
    confirm_bar_id: int | None,
    anchor_bar_ids: Sequence[int],
    rulebook_version: str,
    structure_version: str,
) -> str:
    payload = json.dumps(
        {
            "anchor_bar_ids": list(anchor_bar_ids),
            "kind": kind,
            "rulebook_version": rulebook_version,
            "start_bar_id": start_bar_id,
            "structure_version": structure_version,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{kind}-{start_bar_id}-{digest}"
