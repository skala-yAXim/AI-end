from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class UserInfo:
    id: int
    name: str
    email: str
    
@dataclass
class FileInfo:
  id: int
  created_at: datetime
  updated_at: datetime
  original_file_name: str
  file_url: str
  file_size: str
    
@dataclass
class ProjectInfo:
    id: str
    created_at: datetime
    updated_at: datetime
    name: str
    start_date: str
    end_date: str
    description: str
    status: str
    files: List[FileInfo]

@dataclass
class TeamInfoResponse:
    id: str
    name: str
    description: str
    members: List[UserInfo]
    projects: List[ProjectInfo]