from dataclasses import dataclass
from datetime import timedelta


@dataclass
class TogglTimeEntry:
    id: int
    workspace_id: int
    project_id: int
    task_id: int
    billable: bool
    start: str
    stop: str
    duration: int
    description: str
    tags: [str]
    tag_ids: [str]
    duronly: bool
    at: str
    server_deleted_at: str
    user_id: int
    uid: int
    wid: int
    pid: int

    project_name: str = ""
    duration_delta: timedelta = None