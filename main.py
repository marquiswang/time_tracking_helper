import os
from datetime import datetime

import requests

from time_entry import TogglTimeEntry

TOGGL_API_TOKEN = os.environ['TOGGL_API_TOKEN']
PUSHCUT_API_TOKEN = os.environ['PUSHCUT_API_TOKEN']

PUSHCUTS_TRACKING_SHORTCUT = "Time Tracking"
PUSHCUTS_NOT_TRACKING_SHORTCUT = "Start Tracking"


def get_projects():
    json = toggl_api('projects')
    return json


def get_current_time_entry() -> TogglTimeEntry:
    data = toggl_api('time_entries/current')

    if data is None:
        return None

    time_entry = TogglTimeEntry(**data)

    projects: dict[tuple[int, int], object] = {}
    for project in get_projects():
        projects[(project['workspace_id'], project['id'])] = project

    key = (data['workspace_id'], data['project_id'])
    time_entry.project_name = projects[key]['name']

    start_time = datetime.fromisoformat(data['start'])
    now = datetime.now().astimezone().replace(microsecond=0)
    time_entry.duration_delta = now - start_time
    return time_entry

def get_last_time_entry() -> TogglTimeEntry:
    data = toggl_api('time_entries')[0]
    return TogglTimeEntry(**data)


def toggl_api(endpoint):
    r = requests.get(f"https://api.track.toggl.com/api/v9/me/{endpoint}", auth=(TOGGL_API_TOKEN, 'api_token'))
    return r.json()


def pushcuts_post(shortcut, title, text):
    r = requests.post(f"https://api.pushcut.io/{PUSHCUT_API_TOKEN}/notifications/{shortcut}",
                      json={'title': title, 'text': text})
    return r.json()

if __name__ == '__main__':
    current_time_entry = get_current_time_entry()
    if current_time_entry is None:
        last_time_entry: TogglTimeEntry = get_last_time_entry()

        start_time = datetime.fromisoformat(last_time_entry.stop.replace("Z", "+00:00"))
        now = datetime.now().astimezone().replace(microsecond=0)
        untracked_time = now - start_time

        pushcuts_post(PUSHCUTS_NOT_TRACKING_SHORTCUT, f"Untracked Time", f"{untracked_time}")
    else:
        pushcuts_post(PUSHCUTS_TRACKING_SHORTCUT,
                      f"Tracking for {current_time_entry.duration_delta}",
                      f"{current_time_entry.project_name} - {current_time_entry.description}")
