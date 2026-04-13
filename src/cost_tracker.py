from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostTracker:
    total_units: int = 0
    events: list[str] = field(default_factory=list)

    def record(self, label: str, units: int) -> None:
        # Guard against negative units: recording a negative cost is
        # nonsensical and would silently corrupt the running total.
        # Clamp to zero so callers with bad data don't undermine accounting.
        safe_units = max(0, units)
        self.total_units += safe_units
        self.events.append(f'{label}:{safe_units}')
