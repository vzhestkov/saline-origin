import logging

from threading import Lock
from time import time

from saline.data.parser import EventTags
from saline.data.state import JobStatus


log = logging.getLogger(__name__)


class Minion:
    def __init__(self, name, lock):
        self._name = name
        if lock is None:
            lock = Lock()
        self._lock = lock
        self._request_last = 0
        self._request_count = 0
        self._response_last = 0
        self._response_count = 0
        self._offline_last = None
        self._offline_count = 0
        self._seen_last = 0
        self._seen_count = 0
        self._updates = 0
        self._pending_jobs = {}
        self._completed_jobs = {}
        self._offline_jobs = {}

    def name(self):
        return self._name

    def update(self, ts, status, jid=None, job=None):
        if ts is None:
            ts = time()
        if status == JobStatus.NEW:
            self._request_last = max(ts, self._request_last)
            self._request_count += 1
            if jid is not None and job is not None:
                with self._lock:
                    if jid not in self._pending_jobs:
                        self._pending_jobs[jid] = (job, ts)
        elif status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            with self._lock:
                self._seen_last = max(ts, self._seen_last)
                self._seen_count += 1
                self._response_last = max(ts, self._response_last)
                self._response_count += 1
            if jid is not None:
                with self._lock:
                    job, req_ts = self._pending_jobs.pop(jid, (job, ts))
                    if jid in self._completed_jobs:
                        log.warning(
                            "Duplicated return from '%s' on jid: %s after %.3f seconds",
                            self._name,
                            jid,
                            ts - self._completed_jobs[jid][1],
                        )
                        self._completed_jobs[jid][0] += 1
                        self._completed_jobs[jid][1] = ts
                    else:
                        self._completed_jobs[jid] = [1, ts]
        self._updates += 1

    def offline(self, ts):
        if ts is None:
            ts = time()
        self._offline_last = ts
        self._offline_count += 1
        pending_jobs = {}
        with self._lock:
            pending_jobs = self._pending_jobs
            self._pending_jobs = {}
            self._offline_jobs.update(pending_jobs)
        for _, (job, _) in pending_jobs.items():
            job.timeout_minion(self._name, ts)

    def cleanup_jid(self, jid):
        self._completed_jobs.pop(jid, None)
        self._pending_jobs.pop(jid, None)
        self._offline_jobs.pop(jid, None)

    def is_offline(self):
        return (
            True
            if self._offline_last is not None
            and (
                self._response_last is None or self._offline_last > self._response_last
            )
            else False
        )

    def update_last_seen_time(self, ts):
        with self._lock:
            self._seen_last = max(ts, self._seen_last)
            self._seen_count += 1

    def get_last_seen_time(self):
        return self._seen_last


class MinionsCollection:
    def __init__(self):
        self._minions = {}
        self._lock = Lock()

    def get(self, name):
        with self._lock:
            if name not in self._minions:
                self._minions[name] = Minion(name, self._lock)
        return self._minions[name]

    def update(self, minions, ts=None, **kwargs):
        if ts is None:
            ts = time()
        if not isinstance(minions, (list, tuple)):
            minions = [minions]
        with_tag = kwargs.pop("with_tag", None)
        if with_tag in (
            EventTags.SALT_AUTH,
            EventTags.SALT_MINION_START,
            EventTags.SALT_MINION_REFRESH,
        ):
            for minion in minions:
                self.get(minion).update_last_seen_time(ts)
            return
        for minion in minions:
            self.get(minion).update(ts, **kwargs)

    def offline(self, minions, ts=None):
        if ts is None:
            ts = time()
        if not isinstance(minions, (list, tuple)):
            minions = [minions]
        for minion in minions:
            self.get(minion).offline(ts)

    def get_count(self):
        return len(self._minions)

    def get_stats(self, ts=None):
        if ts is None:
            ts = time()

        stats = {
            "seen": self.get_count(),
            "active_1m": 0,
            "active_5m": 0,
            "active_15m": 0,
            "active_1h": 0,
            "active_24h": 0,
            "active_ever": 0,
            "active_never": 0,
            "offline": 0,
        }

        with self._lock:
            for minion in self._minions.values():
                if minion.is_offline():
                    stats["offline"] += 1
                last_seen = minion.get_last_seen_time()
                if last_seen != 0:
                    last_seen = ts - last_seen
                    if last_seen <= 60:
                        stats["active_1m"] += 1
                    if last_seen <= 300:
                        stats["active_5m"] += 1
                    if last_seen <= 900:
                        stats["active_15m"] += 1
                    if last_seen <= 3600:
                        stats["active_1h"] += 1
                    if last_seen <= 86400:
                        stats["active_24h"] += 1
                    stats["active_ever"] += 1

        stats["active_never"] = stats["seen"] - stats["active_ever"]

        return stats
