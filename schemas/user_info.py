from dataclasses import dataclass
from typing import List

from schemas.project_info import ProjectInfo

@dataclass
class UserInfo:
    id: int
    name: str
    email: str
    team_id: str
    team_name: str
    projects: List[ProjectInfo]
    