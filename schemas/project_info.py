from dataclasses import dataclass
from typing import Optional


@dataclass
class ProjectInfo:
    id: str
    name: str
    start_date: str
    end_date: str
    description: str
    progress: int