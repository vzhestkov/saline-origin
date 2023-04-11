import logging

from time import time

from saline.data.metrics import Metrics, MetricsCollection
from saline.data.minion import MinionsCollection
from saline.data.parser import EventTags
from saline.data.smart import MergeWrapper
from saline.data.state import StateJobCollection, JobStatus


log = logging.getLogger(__name__)


class DataMerger:
    def __init__(self, opts):
        self.opts = opts
        self.metrics = MetricsCollection()
        self.minions = MinionsCollection()
        self.jobs = StateJobCollection(self.minions)
        self.states_mods = {}
        self._state_statuses = (
            "succeeded",
            "failed",
            "notrun",
            "warning",
        )
        self._status_tgt = {
            True: "succeeded",
            False: "failed",
            None: "notrun",
        }
        self._sls_id_fun = MergeWrapper(
            {},
            self.opts.get("merge_rules", {}).get("sls", {}).get("start_merging_on", 70),
            new_rules_callback=self._new_merge_rules,
            new_rules_callback_opts=("sls",),
            merge_callback=self._merge_sls,
        )
        self._state_funcs = (
            "state.apply",
            "state.high",
            "state.highstate",
            "state.low",
            "state.pkg",
            "state.template",
            "state.template_str",
            "state.test",
            "state.top",
            "state.single",
            "state.sls",
            "state.sls_id",
        )

    def _get_sls_id_fun_status(self, sls, sid, fun, status):
        (sls, sid, fun) = (str(sls), str(sid), str(fun))
        sls = self._sls_id_fun.get_wrapped(sls)
        if sls not in self._sls_id_fun:
            self._sls_id_fun[sls] = MergeWrapper(
                {},
                self.opts.get("merge_rules", {})
                .get("sid", {})
                .get("start_merging_on", 150),
                new_rules_callback=self._new_merge_rules,
                new_rules_callback_opts=("sid",),
                merge_callback=self._merge_sls_sid,
                merge_callback_opts=(sls,),
            )
            sls = self._sls_id_fun.get_wrapped(sls)
        sid = self._sls_id_fun[sls].get_wrapped(sid)
        if sid not in self._sls_id_fun[sls]:
            self._sls_id_fun[sls][sid] = {}
            sid = self._sls_id_fun[sls].get_wrapped(sid)
        if fun not in self._sls_id_fun[sls][sid]:
            self._sls_id_fun[sls][sid][fun] = []
        if status not in self._sls_id_fun[sls][sid][fun]:
            self._sls_id_fun[sls][sid][fun].append(status)
        return (sls, sid, fun, status)

    def _new_merge_rules(self, new_rules, rule_for):
        for pattern, replacement in new_rules:
            log.info(
                "New merging rule for '%s' was automatically applied: %s -> %s",
                rule_for,
                pattern.pattern,
                replacement,
            )

    def _move_metrics(self, src_labels, dst_labels):
        self.metrics.move(
            (
                Metrics.SALT_STATE_RESULTS,
                Metrics.SALT_STATE_DURATION,
            ),
            src_labels,
            dst_labels,
        )

    def _merge_sls(self, src_sls, dst_sls):
        for sid in list(self._sls_id_fun[src_sls].keys()):
            self._merge_sls_sid(sid, sid, src_sls, dst_sls)
        self._sls_id_fun.pop(src_sls, None)
        return True

    def _merge_sls_sid(self, src_sid, dst_sid, src_sls, dst_sls=None):
        if dst_sls is None:
            dst_sls = src_sls
        else:
            if dst_sls not in self._sls_id_fun:
                self._sls_id_fun[dst_sls] = MergeWrapper(
                    {},
                    self.opts.get("merge_rules", {})
                    .get("sid", {})
                    .get("start_merging_on", 150),
                    new_rules_callback=self._new_merge_rules,
                    new_rules_callback_opts=("sid",),
                    merge_callback=self._merge_sls_sid,
                    merge_callback_opts=(dst_sls,),
                )
        if dst_sid not in self._sls_id_fun[dst_sls]:
            self._sls_id_fun[dst_sls][dst_sid] = {}
        for fun in self._sls_id_fun[src_sls][src_sid]:
            if fun not in self._sls_id_fun[dst_sls][dst_sid]:
                self._sls_id_fun[dst_sls][dst_sid][fun] = []
            for status in self._sls_id_fun[src_sls][src_sid][fun]:
                self._move_metrics(
                    (src_sls, src_sid, fun, status), (dst_sls, dst_sid, fun, status)
                )
            self._sls_id_fun[dst_sls][dst_sid][fun] = list(
                set(
                    [
                        *self._sls_id_fun[src_sls][src_sid][fun],
                        *self._sls_id_fun[dst_sls][dst_sid][fun],
                    ]
                )
            )
        self._sls_id_fun[src_sls].pop(src_sid, None)
        return True

    def _store_per_minion_state_data(self, minions, status, jid, ts, state_fun_args):
        if state_fun_args is None:
            log.warning("Ignoring state data for %s from jid: %s", minions, jid)
            return
        job = self.jobs.get(state_fun_args)
        job.update(minions, status, jid, ts)

    def _add_state(self, data, tag_sub, ts):
        minions = []
        if "minions" in data:
            minions = data["minions"]
        elif "id" in data:
            minions = [data["id"]]
        jid = data.get("jid")
        if len(minions) == 0:
            log.warning(
                "Neither 'minions' nor 'id' is specified in event '%s' with jid: %s",
                data.get("tag"),
                jid,
            )
        if tag_sub == EventTags.SALT_JOB_NEW:
            self._store_per_minion_state_data(
                minions,
                JobStatus.NEW,
                jid,
                ts,
                data.get("state_fun_args"),
            )
            return
        self.metrics.inc(Metrics.SALT_STATE_APPLIES)
        state_status = None
        errors = data.get("errors")
        if errors:
            self.metrics.inc(Metrics.SALT_STATE_APPLIES_STATUS, ("errors",))
            state_status = JobStatus.FAILED
        elif data.get("test", False):
            self.metrics.inc(Metrics.SALT_STATE_APPLIES_STATUS, ("test",))
            if "return" in data and isinstance(data["return"], dict):
                for rtag in data["return"].keys():
                    ret = data["return"][rtag]
                    duration = ret.get("duration", 0.0)
                    sls_id_fun_status = self._get_sls_id_fun_status(
                        ret.get("__sls__"), ret.get("__id__"), ret.get("fun"), "notrun"
                    )
                    self.metrics.inc(
                        Metrics.SALT_STATE_RESULTS,
                        sls_id_fun_status,
                    )
                    self.metrics.inc(
                        Metrics.SALT_STATE_DURATION,
                        sls_id_fun_status,
                        inc_by=duration,
                    )
            state_status = JobStatus.SUCCEEDED
        else:
            for s in self._state_statuses:
                vl = data.get(s)
                if vl:
                    self.metrics.inc(Metrics.SALT_STATE_APPLIES_STATUS, (s,))
                    if s == "failed":
                        state_status = JobStatus.FAILED
            if "return" in data and isinstance(data["return"], dict):
                for rtag in data["return"].keys():
                    ret = data["return"][rtag]
                    result = ret.get("result")
                    status = self._status_tgt[result]
                    if "warning" in ret:
                        status = "%s_with_warning" % status
                    duration = ret.get("duration", 0.0)
                    sls_id_fun_status = self._get_sls_id_fun_status(
                        ret.get("__sls__"), ret.get("__id__"), ret.get("fun"), status
                    )
                    self.metrics.inc(
                        Metrics.SALT_STATE_RESULTS,
                        sls_id_fun_status,
                    )
                    self.metrics.inc(
                        Metrics.SALT_STATE_DURATION,
                        sls_id_fun_status,
                        inc_by=duration,
                    )
            if state_status != JobStatus.FAILED:
                state_status = JobStatus.SUCCEEDED
        self._store_per_minion_state_data(
            minions,
            state_status,
            jid,
            ts,
            data.get("state_fun_args"),
        )

    def add(self, data):
        rix = data.get("rix")
        if rix is not None:
            self.metrics.inc(Metrics.SALINE_INTERNAL_RIX_TOTAL, (rix,))
        jid = data.get("jid")
        self.metrics.inc(Metrics.SALT_EVENTS_TOTAL)
        ts = data.get("ts")
        tag_main = data.get("tag_main")
        tag_sub = data.get("tag_sub")
        tag_mask = data.get("tag_mask")
        self.metrics.inc(Metrics.SALT_EVENTS_TAGS, (tag_mask,))
        fun = data.get("fun")
        if fun:
            self.metrics.inc(Metrics.SALT_EVENTS_TAGS_FUNCS, (tag_mask, fun))
            if (
                tag_main == EventTags.SALT_JOB
                and tag_sub in (EventTags.SALT_JOB_NEW, EventTags.SALT_JOB_RET)
            ):
                if fun in self._state_funcs and data.get("offline", False) is False:
                    self._add_state(data, tag_sub, ts)
                else:
                    minions = []
                    if "minions" in data:
                        minions = data["minions"]
                    elif "id" in data:
                        minions = [data["id"]]
                    if data.get("offline", False):
                        self.minions.offline(minions, ts)
                    else:
                        self.minions.update(
                            minions,
                            ts,
                            status=JobStatus.NEW
                            if tag_sub == EventTags.SALT_JOB_NEW
                            else JobStatus.SUCCEEDED
                            if data.get("success", False)
                            else JobStatus.FAILED,
                            jid=jid,
                        )
        else:
            self.metrics.inc(Metrics.SALT_EVENTS_TAGS_FUNCS, (tag_mask, "-"))
        if tag_main == EventTags.SALT_BATCH and tag_sub in (
            EventTags.SALT_BATCH_START,
            EventTags.SALT_BATCH_DONE,
        ):
            down_minions = data.get("down_minions", [])
            if down_minions:
                self.minions.offline(down_minions, ts)
        trimmed = data.get("trimmed")
        if trimmed:
            log.warning(
                "The event %s with jid: %s contains trimmed data: %s",
                data.get("tag"),
                jid,
                ", ".join(trimmed),
            )
            self.metrics.inc(Metrics.SALT_EVENTS_TRIMMED_COUNT)
            self.metrics.inc(Metrics.SALT_EVENTS_TRIMMED_TOTAL, inc_by=len(trimmed))

    def get_metrics(self):
        return self.metrics.get_buf()

    def get_metrics_epoch(self):
        return self.metrics.get_epoch()

    def jobs_metrics_update(self):
        ts = time()

        highstate_mods = self.opts.get("set_highstate_mods_in_metrics", "")

        stats = self.minions.get_stats(ts)
        for key, val in stats.items():
            self.metrics.set(Metrics.SALT_MINIONS, (key,), val)

        for job in self.jobs.jobs():
            state_fun, state_mods, state_test = job.state_fun_args
            state_mods = ", ".join(state_mods)

            if state_mods == "" and highstate_mods != "":
                state_mods = highstate_mods

            stats = job.get_stats()
            for key, val in stats.items():
                self.metrics.set(
                    Metrics.SALT_STATE_JOBS,
                    (state_fun, state_mods, state_test, key),
                    val,
                )

    def cleanup_job_jids(self):
        ts = time()
        for job in self.jobs.jobs():
            job.cleanup_jids(self.opts.get("job_cleanup_after", 1200), ts)
