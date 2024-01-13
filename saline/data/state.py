import logging

from threading import Lock
from time import time


log = logging.getLogger(__name__)


class JobStatus:
    NEW = 0
    SUCCEEDED = 1
    FAILED = 2


class SaltJob:
    def __init__(self, jid, parent, lock):
        self._jid = jid
        self._parent = parent
        self._lock = lock
        self._req_ts = None
        self._last_resp_ts = None
        self._minions = set()
        self._minions_done = {}
        self._minions_timeout = {}
        self._completed = None

    def update(self, minions, ts, status):
        with self._lock:
            self._minions.update(minions)
        if status == JobStatus.NEW:
            self._req_ts = ts
        else:
            self._last_resp_ts = ts
            with self._lock:
                for minion in minions:
                    self._minions_timeout.pop(minion, None)
                    self._minions_done[minion] = ts
            if self._set_completed():
                self._parent.completed_jid(self._jid, ts)

    def get_minions(self):
        return self._minions.copy()

    def _set_completed(self):
        with self._lock:
            minions_count = len(self._minions)
            results_count = len(self._minions_done) + len(self._minions_timeout)
            self._completed = minions_count == results_count
        return self._completed

    def completed(self):
        if self._completed:
            return (
                self._last_resp_ts if self._last_resp_ts is not None else self._req_ts
            )
        return False

    def timeout_minion(self, minion, ts):
        with self._lock:
            if minion in self._minions_done:
                return
            self._minions_timeout[minion] = ts
        self._parent.timeout_jid_minion(self._jid, minion, ts)
        if self._set_completed():
            self._parent.completed_jid(self._jid, ts)

    def complete_with_timeout(self, timeout=1200, ts=None, before=None):
        if ts is None:
            ts = time()
        if before is None:
            before = ts - timeout
        if self._req_ts is not None and self._req_ts > before:
            return
        pending_minions = set()
        with self._lock:
            pending_minions = self._minions.copy()
            pending_minions.difference_update(self._minions_done.keys())
            pending_minions.difference_update(set(self._minions_timeout.keys()))
        for minion in pending_minions:
            self.timeout_minion(minion, ts)


class StateJob:
    def __init__(self, state_fun_args, minions=None):
        self._lock = Lock()
        self.state_fun_args = state_fun_args
        self._jids = {}
        self._completed_jids = {}
        self._completed_jids_cout = 0
        self._minions = minions
        self._minions_targets = set()
        self._minions_succeeded = {}
        self._minions_failed = {}
        self._minions_timeout = {}
        self._minions_ever_succeeded = set()
        self._minions_ever_failed = set()
        self._minions_ever_timeout = set()
        self._minions_pending = {}

    def update(self, minions, status, jid, ts):
        if not isinstance(minions, (list, tuple)):
            minions = [minions]
        job = None
        with self._lock:
            if jid in self._completed_jids:
                job = self._completed_jids[jid][0]
            elif jid in self._jids:
                job = self._jids[jid]
            else:
                job = SaltJob(jid, self, self._lock)
                self._jids[jid] = job
        self._minions.update(minions, ts=ts, status=status, jid=jid, job=job)
        self._minions_targets.update(minions)
        if job is not None:
            job.update(minions, ts=ts, status=status)
        if status == JobStatus.SUCCEEDED:
            with self._lock:
                for minion in minions:
                    self._minions_succeeded[minion] = ts
                    self._minions_failed.pop(minion, None)
                    self._minions_timeout.pop(minion, None)
                self._minions_ever_succeeded.update(minions)
        elif status == JobStatus.FAILED:
            with self._lock:
                for minion in minions:
                    self._minions_failed[minion] = ts
                    self._minions_succeeded.pop(minion, None)
                    self._minions_timeout.pop(minion, None)
                self._minions_ever_failed.update(minions)
        elif status == JobStatus.NEW:
            for minion in minions:
                with self._lock:
                    if minion not in self._minions_pending:
                        self._minions_pending[minion] = set([jid])
                    self._minions_pending[minion].add(jid)
        if status != JobStatus.NEW:
            for minion in minions:
                with self._lock:
                    if minion in self._minions_pending:
                        self._minions_pending[minion].discard(jid)
                        if len(self._minions_pending[minion]) == 0:
                            self._minions_pending.pop(minion)

    def timeout_jid_minion(self, jid, minion, ts):
        with self._lock:
            self._minions_timeout[minion] = ts
            if minion in self._minions_pending:
                self._minions_pending[minion].discard(jid)
                if len(self._minions_pending[minion]) == 0:
                    self._minions_pending.pop(minion)
                self._minions_succeeded.pop(minion, None)
                self._minions_failed.pop(minion, None)
            self._minions_ever_timeout.update([minion])

    def completed_jid(self, jid, ts):
        with self._lock:
            completed_job = self._completed_jids.get(jid, None)
            if completed_job is not None:
                completed_job = completed_job[0]
            job = self._jids.pop(jid, completed_job)
            self._completed_jids[jid] = (job, ts)

    def complete_with_timeout(self, timeout=1200, ts=None, before=None):
        if ts is None:
            ts = time()
        if before is None:
            before = ts - timeout
        pending_jids = list(self._jids.keys())
        for jid in pending_jids:
            job = self._jids.get(jid, None)
            if job is not None:
                job.complete_with_timeout(timeout=timeout, ts=ts, before=before)

    def cleanup_jids(self, cleanup_interval, ts=None):
        if ts is None:
            ts = time()

        cleanup_before = ts-cleanup_interval

        jids_to_cleanup = set()

        with self._lock:
            for jid, job_data in self._completed_jids.items():
                job_ts = job_data[1]
                if job_ts <= ts:
                    jids_to_cleanup.add(jid)

        for jid in jids_to_cleanup:
            job_data = self._completed_jids.pop(jid, None)
            if job_data is not None:
                job = job_data[0]
                self._completed_jids_cout += 1
                if self._minions is not None:
                    for minion in job.get_minions():
                        self._minions.get(minion).cleanup_jid(jid)

    def get_stats(self):
        stats = {}
        with self._lock:
            stats = {
                "pending_jids": len(self._jids),
                "completed_jids": len(self._completed_jids),
                "targeted": len(self._minions_targets),
                "pending": len(self._minions_pending),
                "succeeded": len(self._minions_succeeded),
                "failed": len(self._minions_failed),
                "timedout": len(self._minions_timeout),
                "ever_succeeded": len(self._minions_ever_succeeded),
                "ever_failed": len(self._minions_ever_failed),
                "ever_timedout": len(self._minions_ever_timeout),
            }
            all_succeeded = self._minions_ever_succeeded.copy()
            all_succeeded.difference_update(self._minions_ever_failed)
            all_succeeded.difference_update(self._minions_ever_timeout)
            all_failed = self._minions_ever_failed.copy()
            all_failed.difference_update(self._minions_ever_succeeded)
            all_failed.difference_update(self._minions_ever_timeout)
            all_timeout = self._minions_ever_timeout.copy()
            all_timeout.difference_update(self._minions_ever_succeeded)
            all_timeout.difference_update(self._minions_ever_failed)
            stats.update({
                "all_succeeded": len(all_succeeded),
                "all_failed": len(all_failed),
                "all_timedout": len(all_timeout),
            })
        return stats


class StateJobCollection:
    def __init__(self, minions):
        self._state_jobs = {}
        self._minions = minions
        self._lock = Lock()

    def get(self, state_fun_args):
        job = None
        with self._lock:
            if state_fun_args in self._state_jobs:
                job = self._state_jobs[state_fun_args]
            else:
                job = StateJob(
                    state_fun_args, self._minions
                )
                self._state_jobs[state_fun_args] = job
        return job

    def jobs(self):
        with self._lock:
            for job in self._state_jobs.values():
                yield job

    def complete_with_timeout(self, timeout=1200, ts=None, before=None):
        if ts is None:
            ts = time()
        if before is None:
            before = ts - timeout
        keys = list(self._state_jobs.keys())
        for state_fun_args in keys:
            state_job = self._state_jobs.get(state_fun_args, None)
            if state_job is not None:
                state_job.complete_with_timeout(timeout=timeout, ts=ts, before=before)
