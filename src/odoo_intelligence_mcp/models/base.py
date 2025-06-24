from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from typing import Any


@dataclass
class BaseModel:
    id: int | None = dataclass_field(default=None)
    created_at: datetime = dataclass_field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = dataclass_field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data

    def update_timestamp(self) -> None:
        self.updated_at = datetime.now(UTC)
