from dataclasses import dataclass
from typing import List

@dataclass
class ProjectInfo:
    id: str
    name: str
    start_date: str
    end_date: str
    description: str

@dataclass
class UserInfo:
    id: int
    name: str
    email: str
    team_id: str
    team_name: str
    projects: List[ProjectInfo]
    