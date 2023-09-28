import os
from datetime import datetime

import requests

TOGGL_API_TOKEN = os.environ['TOGGL_API_TOKEN']
PUSHCUT_API_TOKEN = os.environ['PUSHCUT_API_TOKEN']

PUSHCUTS_TRACKING_SHORTCUT = "Time Tracking"
PUSHCUTS_NOT_TRACKING_SHORTCUT = "Start Tracking"

def get_projects():
    json = toggl_api('projects')
    return json

def get_current_time_entry():
    json = toggl_api('time_entries/current')

    if json is None:
        return None

    projects: dict[tuple[int, int], object] = {}
    for project in get_projects():
        projects[(project['workspace_id'], project['id'])] = project

    key = (json['workspace_id'], json['project_id'])
    project_name = projects[key]['name']
    json['project_name'] = project_name

    start_time = datetime.fromisoformat(json['start'])
    now = datetime.now().astimezone().replace(microsecond=0)
    duration = now - start_time

    json['duration_formatted'] = duration
    return json

def get_last_time_entry():
    json = toggl_api('time_entries')[0]

    start_time = datetime.fromisoformat(json['stop'].replace("Z", "+00:00"))
    now = datetime.now().astimezone().replace(microsecond=0)
    duration = now - start_time

    json['untracked_duration_formatted'] = duration
    return json


def toggl_api(endpoint):
    r = requests.get(f"https://api.track.toggl.com/api/v9/me/{endpoint}", auth=(TOGGL_API_TOKEN, 'api_token'))
    return r.json()

def pushcuts_post(shortcut, title, text):
    r = requests.post(f"https://api.pushcut.io/{PUSHCUT_API_TOKEN}/notifications/{shortcut}", json={'title': title, 'text': text})
    return r.json()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    current_time_entry = get_current_time_entry()
    if current_time_entry is None:
        last_time_entry = get_last_time_entry()
        pushcuts_post(PUSHCUTS_NOT_TRACKING_SHORTCUT, f"Untracked Time", f"{last_time_entry['untracked_duration_formatted']}")
        print(last_time_entry)
    else:
        pushcuts_post(PUSHCUTS_TRACKING_SHORTCUT, f"Tracking for {current_time_entry['duration_formatted']}", f"{current_time_entry['project_name']} - {current_time_entry['description']}")
        print(current_time_entry)

