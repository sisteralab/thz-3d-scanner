from __future__ import annotations

from typing import Any


def group_rotation_blocks_by_frequency(data: Any) -> list[list[dict[str, Any]]]:
    blocks = [
        item for item in data if isinstance(item, dict) and "rotation_angle" in item
    ]
    if not blocks:
        return []

    groups: dict[tuple[Any, Any, Any, Any], list[dict[str, Any]]] = {}
    for item in blocks:
        key = (
            item.get("freq_1"),
            item.get("freq_2"),
            item.get("amp_1"),
            item.get("amp_2"),
        )
        groups.setdefault(key, []).append(item)

    grouped_data = []
    for items in groups.values():
        items.sort(key=lambda block: float(block.get("rotation_angle", 0.0)))
        grouped_data.append(items)
    return grouped_data
