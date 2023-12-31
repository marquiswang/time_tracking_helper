import argparse
import os
from datetime import datetime, timedelta

CHECK_INTERVAL = timedelta(minutes=5)
UNTRACKED_TIME_REMINDER_INTERVAL = timedelta(minutes=10)
DEFAULT_TRACKED_TIME_REMINDER_INTERVAL = timedelta(minutes=30)
TRACKED_TIME_REMINDER_INTERVALS = dict({
    "Sleep": (timedelta(hours=8), timedelta(minutes=30)),
    "Chinese": (timedelta(minutes=5), timedelta(minutes=15)),
    "Relaxation": (timedelta(minutes=15), timedelta(minutes=15)),
    "Hygiene": (timedelta(minutes=15), timedelta(minutes=5)),
})
PROJECTS = dict()

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

    key = (data['workspace_id'], data['project_id'])
    time_entry.project_name = PROJECTS[key]['name']

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


import time

from threading import Timer


class NotificationQueue:
    timer: Timer = Timer(0, lambda: _)


def schedule_new_reminder(last_checked_current_time_entry):
    current_time_entry = get_current_time_entry()
    if current_time_entry is None:
        print(f"Currently not tracking")
    else:
        print(f"Current time entry {current_time_entry}")
    current_id = current_time_entry.id if current_time_entry is not None else None
    queued_id = last_checked_current_time_entry.id if last_checked_current_time_entry is not None else None
    if NotificationQueue.timer.is_alive() and current_id != queued_id:
        print(f"Cancelling obsolete time notification for {last_checked_current_time_entry}")
        NotificationQueue.timer.cancel()
        time.sleep(1)

    now = datetime.now().astimezone().replace(microsecond=0)
    if current_time_entry is None:
        last_time_entry: TogglTimeEntry = get_last_time_entry()

        last_stop_time = datetime.fromisoformat(last_time_entry.stop.replace("Z", "+00:00"))
        next_interval = last_stop_time
        untracked_time = timedelta()
        while next_interval < now:
            next_interval += UNTRACKED_TIME_REMINDER_INTERVAL
            untracked_time += UNTRACKED_TIME_REMINDER_INTERVAL
        time_to_next_interval: timedelta = next_interval - now

        if not NotificationQueue.timer.is_alive():
            print(f"Scheduling untracked time notification in {time_to_next_interval} ({next_interval})")
            NotificationQueue.timer = Timer(time_to_next_interval.total_seconds(),
                                            lambda: send_untracked_time_notification(untracked_time))
            NotificationQueue.queued = True
            NotificationQueue.timer.start()
    else:
        start_time = datetime.fromisoformat(current_time_entry.start)
        intervals = TRACKED_TIME_REMINDER_INTERVALS.get(current_time_entry.project_name,
                                                        (timedelta(0), DEFAULT_TRACKED_TIME_REMINDER_INTERVAL))
        duration = intervals[0]
        interval = intervals[1]
        next_interval = start_time + duration
        while next_interval < now:
            next_interval += interval
            duration += interval
        time_to_next_interval: timedelta = next_interval - now

        if not NotificationQueue.timer.is_alive():
            print(f"Scheduling tracked time notification in {time_to_next_interval} ({next_interval})")
            NotificationQueue.timer = Timer(time_to_next_interval.total_seconds(),
                                            lambda: send_tracked_time_notification(current_time_entry, duration))
            NotificationQueue.timer.start()
        else:
            print("Not rescheduling time entry, already scheduled")

    return current_time_entry


def send_untracked_time_notification(untracked_time):
    current_time_entry = get_current_time_entry()
    if current_time_entry is not None:
        print(f"Cancelling untracked time notification, detected new time entry for {current_time_entry}")
    else:
        print(f"Sending untracked time notification for {untracked_time} of untracked time")
        pushcuts_post(PUSHCUTS_NOT_TRACKING_SHORTCUT, f"Untracked Time", f"{untracked_time}")


def send_tracked_time_notification(time_entry, duration):
    current_time_entry = get_current_time_entry()
    if current_time_entry is None or current_time_entry.id != time_entry.id:
        print(f"Cancelling tracked time notification {time_entry}, new time entry {current_time_entry}")
    else:
        print(f"Sending tracked time notification for {current_time_entry}: {duration}")
        pushcuts_post(PUSHCUTS_TRACKING_SHORTCUT,
                      f"Tracking for {duration}",
                      f"{current_time_entry}")


def start_reminders():
    current_time_entry = None
    while True:
        try:
            current_time_entry = schedule_new_reminder(current_time_entry)
        except Exception as error:
            print(error)
        time.sleep(CHECK_INTERVAL.total_seconds())


import statistics

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='Time Tracking Helper',
        description='Helps track time with Toggl using reminders and smartness')

    parser.add_argument('--start', action='store_true')
    parser.add_argument('--test', action='store_true')

    args = parser.parse_args()

    for project in get_projects():
        PROJECTS[(project['workspace_id'], project['id'])] = project

    if args.test:
        data = toggl_api('time_entries')
        time_entries = [TogglTimeEntry(**entry) for entry in data]

        time_entry_samples = {}
        for time_entry in time_entries:
            if not time_entry.stop:
                continue

            time_entry.project_name = PROJECTS[(time_entry.workspace_id, time_entry.project_id)]['name']
            samples = time_entry_samples.setdefault(time_entry.project_name, {'samples':[]})
            start_time = datetime.fromisoformat(time_entry.start)
            stop_time = datetime.fromisoformat(time_entry.stop.replace("Z", "+00:00"))
            duration = stop_time - start_time
            samples['samples'].append(duration.total_seconds())

        for sample in time_entry_samples.values():
            samples_ = sample['samples']
            sample['mean'] = timedelta(seconds=statistics.mean(samples_))
            sample['median'] = timedelta(seconds=statistics.median(samples_))
            if len(samples_) > 1:
                sample['stdev'] = timedelta(seconds=statistics.stdev(samples_))
            else:
                sample['stdev'] = timedelta(0)

        print(time_entry_samples)

    if args.start:
        start_reminders()
