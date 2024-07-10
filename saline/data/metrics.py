from threading import Lock


class Metrics:
    # Define Metric types
    TYPE_COUNTER = 1
    TYPE_GAUGE = 2
    # Define Metric IDs
    SALT_EVENTS_TOTAL = 1
    SALT_EVENTS_TAGS = 2
    SALT_EVENTS_TAGS_FUNCS = 3
    SALT_EVENTS_TRIMMED_COUNT = 4
    SALT_EVENTS_TRIMMED_TOTAL = 5
    SALT_STATE_APPLIES = 6
    SALT_STATE_APPLIES_STATUS = 7
    SALT_STATE_RESULTS = 8
    SALT_STATE_DURATION = 9
    SALT_STATE_JOBS = 10
    SALT_MINIONS = 11
    SALT_STATS_RUNS = 12
    SALT_STATS_MEAN = 13
    SALT_STATS_TOTAL = 14
    # IDs for internal metrics
    SALINE_INTERNAL_RIX_TOTAL = 100
    # Metric labels definitions
    LABEL_TAG = 1
    LABEL_FUN = 2
    LABEL_SLS = 3
    LABEL_SID = 4
    LABEL_STATUS = 5
    LABEL_MODS = 6
    LABEL_TEST = 7
    LABEL_MASTER_CMD = 50
    # IDs for labels of internal metrics
    LABEL_RIX = 100


TYPE_LABELS = {
    Metrics.TYPE_COUNTER: "counter",
    Metrics.TYPE_GAUGE: "gauge",
}


LABELS_STATUS = ((Metrics.LABEL_STATUS, "status"),)


LABELS_SLS_SID_FUN_STATUS = (
    (Metrics.LABEL_SLS, "sls"),
    (Metrics.LABEL_SID, "sid"),
    (Metrics.LABEL_FUN, "fun"),
    (Metrics.LABEL_STATUS, "status"),
)


LABELS_FUN_MODS_TEST_STATUS = (
    (Metrics.LABEL_FUN, "fun"),
    (Metrics.LABEL_MODS, "mods"),
    (Metrics.LABEL_TEST, "test"),
    (Metrics.LABEL_STATUS, "status"),
)


LABELS_SALT_STATS = (
    (Metrics.LABEL_MASTER_CMD, "cmd"),
)


METRICS = {
    Metrics.SALT_EVENTS_TOTAL: (
        Metrics.TYPE_COUNTER,
        "salt_events_total",
        "Total number of events processed",
        None,
    ),
    Metrics.SALT_EVENTS_TAGS: (
        Metrics.TYPE_COUNTER,
        "salt_events_tags",
        "Total number of events processed by tag masks",
        ((Metrics.LABEL_TAG, "tag"),),
    ),
    Metrics.SALT_EVENTS_TAGS_FUNCS: (
        Metrics.TYPE_COUNTER,
        "salt_events_tags_funcs",
        "Total number of events processed by tag masks and functions",
        ((Metrics.LABEL_TAG, "tag"), (Metrics.LABEL_FUN, "fun")),
    ),
    Metrics.SALT_EVENTS_TRIMMED_COUNT: (
        Metrics.TYPE_COUNTER,
        "salt_events_trimmed_count",
        "Total number of trimmed events",
        None,
    ),
    Metrics.SALT_EVENTS_TRIMMED_TOTAL: (
        Metrics.TYPE_COUNTER,
        "salt_events_trimmed_total",
        "Total number of trimmed values in the events",
        None,
    ),
    Metrics.SALT_STATE_APPLIES: (
        Metrics.TYPE_COUNTER,
        "salt_state_applies",
        "Total number of state apply events",
        None,
    ),
    Metrics.SALT_STATE_APPLIES_STATUS: (
        Metrics.TYPE_COUNTER,
        "salt_state_applies_status",
        "Total number of state apply events by status",
        LABELS_STATUS,
    ),
    Metrics.SALT_STATE_RESULTS: (
        Metrics.TYPE_COUNTER,
        "salt_state_results",
        "Total number of state apply results",
        LABELS_SLS_SID_FUN_STATUS,
    ),
    Metrics.SALT_STATE_DURATION: (
        Metrics.TYPE_COUNTER,
        "salt_state_duration",
        "Total time of state apply duration",
        LABELS_SLS_SID_FUN_STATUS,
    ),
    Metrics.SALT_STATE_JOBS: (
        Metrics.TYPE_GAUGE,
        "salt_state_jobs",
        "The statuses of salt state jobs",
        LABELS_FUN_MODS_TEST_STATUS,
    ),
    Metrics.SALINE_INTERNAL_RIX_TOTAL: (
        Metrics.TYPE_COUNTER,
        "saline_internal_rix_total",
        "Total number of events processed by specific reader",
        ((Metrics.LABEL_RIX, "rix"),),
    ),
    Metrics.SALT_MINIONS: (
        Metrics.TYPE_GAUGE,
        "salt_minions",
        "Total number of the salt minions by statuses",
        LABELS_STATUS,
    ),
    Metrics.SALT_STATS_RUNS: (
        Metrics.TYPE_COUNTER,
        "salt_master_stats_runs",
        "Total number of salt master internal cmd calls",
        LABELS_SALT_STATS,
    ),
    Metrics.SALT_STATS_MEAN: (
        Metrics.TYPE_GAUGE,
        "salt_master_stats_mean",
        "Mean time of execution of salt master internal cmd calls",
        LABELS_SALT_STATS,
    ),
    Metrics.SALT_STATS_TOTAL: (
        Metrics.TYPE_COUNTER,
        "salt_master_stats_total",
        "Total time of execution of salt master internal cmd calls",
        LABELS_SALT_STATS,
    ),
}


class MetricsLabeledEntry:
    def __init__(self, labels_defs, labels, lock):
        self.value = 0
        self._lock = lock
        ls = []
        i = 0
        for li, lv in labels_defs:
            ls.append(
                '%s="%s"'
                % (
                    lv,
                    str(labels[i]).replace('"', '\\"'),
                )
            )
            i += 1
        self.labels = ",".join(ls)

    def inc(self, inc_by=1):
        return self.set(inc_by=inc_by)

    def set(self, value=None, inc_by=None):
        old_value = self.value
        if value is not None:
            self.value = value
        elif inc_by is not None:
            self.value += inc_by
        return old_value


class MetricsEntry:
    def __init__(self, metric, lock):
        self.mtype, self.label, self.doc, self._labels_defs = METRICS[metric]
        self._lock = lock
        self.value = None
        # The entries with None in the value are labeled
        if self._labels_defs is None:
            # If there is no labels definitions set it as non labeled
            self.value = 0
        else:
            self._labels = {}

    def __str__(self):
        b = []
        b.append(f"# HELP {self.label} {self.doc}")
        b.append(f"# TYPE {self.label} {TYPE_LABELS[self.mtype]}")
        if self.value is None:
            for le in self._labels.values():
                v = "%.3f" % le.value if isinstance(le.value, float) else le.value
                b.append(f"{self.label}{{{le.labels}}} {v}")
        else:
            v = "%.3f" % self.value if isinstance(self.value, float) else self.value
            b.append(f"{self.label} {v}")
        b.append("")
        return "\n".join(b)

    def _set_labeled(self, labels, value=None, inc_by=None):
        with self._lock:
            if labels in self._labels:
                le = self._labels[labels]
            else:
                le = MetricsLabeledEntry(self._labels_defs, labels, self._lock)
                self._labels[labels] = le
        return le.set(value, inc_by)

    def inc(self, labels, inc_by):
        return self.set(labels, inc_by=inc_by)

    def set(self, labels, value=None, inc_by=None):
        old_value = None
        if self.value is None:
            # The entries with None in the value are labeled
            if labels is None:
                raise KeyError
            old_value = self._set_labeled(labels, value, inc_by)
        else:
            if labels is not None:
                raise KeyError
            with self._lock:
                old_value = self.value
                if value is not None:
                    self.value = value
                elif inc_by is not None:
                    self.value += inc_by
        return old_value

    def move(self, src_labels, dst_labels):
        if self.value is not None:
            return
        value = None
        with self._lock:
            if src_labels in self._labels:
                value = self._labels.pop(src_labels).value
        if value is None:
            return
        self._set_labeled(dst_labels, inc_by=value)


class MetricsCollection:
    def __init__(self):
        self._epoch = 0
        self._lock = Lock()
        self.metrics = {}

    def get_epoch(self):
        return self._epoch

    def inc(self, metric, labels=None, inc_by=1):
        return self.set(metric, labels, inc_by=inc_by)

    def set(self, metric, labels=None, value=None, inc_by=None):
        with self._lock:
            if metric in self.metrics:
                me = self.metrics[metric]
            else:
                me = MetricsEntry(metric, self._lock)
                self.metrics[metric] = me
        if value is not None:
            old_value = me.set(labels, value)
            if old_value != value:
                self._epoch += 1
            return old_value
        elif inc_by is not None:
            old_value = me.inc(labels, inc_by)
            self._epoch += 1
            return old_value

    def move(self, metrics, src_labels, dst_labels):
        if not isinstance(metrics, (list, tuple)):
            metrics = [metrics]
        for metric in metrics:
            if metric not in self.metrics:
                continue
            self.metrics[metric].move(src_labels, dst_labels)

    def get_buf(self):
        buf = ""
        with self._lock:
            buf = "".join(map(str, self.metrics.values()))
        return buf
