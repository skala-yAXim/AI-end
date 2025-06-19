from dataclasses import dataclass
from typing import List

from schemas.project_info import ProjectInfo

@dataclass
class TeamInfo:
  id: int
  name: str
  description: str
  weekly_template: str
  members: List[str]
  projects: List[ProjectInfo]