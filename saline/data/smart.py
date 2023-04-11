import re

from difflib import SequenceMatcher


class SmartMerger:
    def __init__(
        self,
        start_merging_on,
        new_rules_callback=None,
        new_rules_callback_opts=(),
        merge_callback=None,
        merge_callback_opts=(),
        match_quality=0.3,
        match_len_trashold=3,
        data=None,
    ):
        self._data = [] if data is None else data
        self._rules = []
        self._patterns = []
        self._replacements = []
        self._start_merging_on = start_merging_on
        self._match_quality = match_quality
        self._match_len_trashold = match_len_trashold
        self._new_rules_callback = new_rules_callback
        self._new_rules_callback_opts = new_rules_callback_opts
        self._merge_callback = merge_callback
        self._merge_callback_opts = merge_callback_opts
        self._in_merge = False

    def add(self, key, value=None):
        if key not in self._data:
            if isinstance(self._data, dict):
                self._data[key] = value
            else:
                self._data.append(value)
            if len(self._data) > self._start_merging_on and not self._in_merge:
                self.merge_values()

    def get(self, value):
        value = str(value)
        if value in self._data:
            return value
        for p, r in self._rules:
            if value == r or p.match(value):
                return r
        return value

    def in_replacements(self, value):
        return True if value in self._replacements else False

    def get_matches(self, a, b, match):
        ret = []
        i = 0
        la = len(a)
        lb = len(b)
        ms = list(filter(lambda x: x.size >= self._match_len_trashold, match))
        match_count = len(ms)
        for m in ms:
            if i == 0 and (m.a > 0 or m.b > 0):
                ret.append("")
            ret.append(a[m.a : m.a + m.size])
            i += 1
            if (
                i == match_count
                and i > 0
                and not (m.a + m.size == la and m.b + m.size == lb)
            ):
                ret.append("")
        return tuple(ret)

    def merge_values(self):
        if self._in_merge:
            return
        try:
            self._in_merge = True
            new_rules = self.get_new_rules()
            orig_items = list(
                self._data.keys() if isinstance(self._data, dict) else self._data
            )
            if not isinstance(new_rules, list):
                return
            if callable(self._new_rules_callback):
                self._new_rules_callback(new_rules, *self._new_rules_callback_opts)
            for p, r in new_rules:
                for i in orig_items:
                    if p.match(i) and i != r and not self.in_replacements(i):
                        if i in self._data and not (
                            callable(self._merge_callback)
                            and self._merge_callback(i, r, *self._merge_callback_opts)
                            is True
                        ):
                            if r not in self._data:
                                if isinstance(self._data, list):
                                    self._data.append(r)
                                    self._data.remove(i)
                                else:
                                    self._data[r] = self._data.pop(i, None)
        finally:
            self._in_merge = False

    def get_new_rules(self):
        matches = {}
        ret_rules = []
        seq_matcher = SequenceMatcher(None, None, None, False)
        items = list(self._data.keys() if isinstance(self._data, dict) else self._data)
        items.sort(key=lambda x: len(x), reverse=True)
        items_count = len(items)
        for i in range(items_count - 1):
            a = items[i]
            if a in self._replacements:
                continue
            la = len(a)
            seq_matcher.set_seq1(a)
            for j in range(items_count):
                if j == i:
                    continue
                b = items[j]
                if b in self._replacements:
                    continue
                lb = len(b)
                seq_matcher.set_seq2(b)
                match = self.get_matches(a, b, seq_matcher.get_matching_blocks())
                if match:
                    lm = len("".join(match))
                    mq = lm / max(la, lb)
                    if mq < self._match_quality:
                        continue
                    if match not in matches:
                        matches[match] = [1, mq]
                    else:
                        matches[match][0] += 1
                        matches[match][1] += mq
        mk = list(matches.keys())
        crexp = {k: re.compile(".*".join(map(lambda x: re.escape(x), k))) for k in mk}
        merged_counts = {}
        for k in mk:
            merged_counts[k] = sum(
                map(
                    lambda x: crexp[k].match(x) is not None,
                    self._data.keys() if isinstance(self._data, dict) else self._data,
                )
            )
        mk.sort(
            key=lambda k: matches[k][0] * matches[k][1] * merged_counts[k], reverse=True
        )
        full_merged_count = 0
        for k in mk:
            pattern = crexp[k]
            merged_count = merged_counts[k]
            replacement = "*".join(k)
            if replacement in self._replacements:
                continue
            if pattern in self._patterns:
                continue
            rs = (pattern, replacement)
            self._patterns.append(pattern)
            self._replacements.append(replacement)
            self._rules.append(rs)
            ret_rules.append(rs)
            full_merged_count += merged_count
            if (
                items_count - full_merged_count + len(ret_rules)
                < self._start_merging_on
            ):
                return ret_rules
        return ret_rules if ret_rules else None


class MergeWrapper:
    def __init__(
        self,
        data,
        start_merging_on,
        new_rules_callback=None,
        new_rules_callback_opts=(),
        merge_callback=None,
        merge_callback_opts=(),
        match_quality=0.7,
        match_len_trashold=3,
    ):
        self._data = data
        self._sm = SmartMerger(
            start_merging_on,
            new_rules_callback=new_rules_callback,
            new_rules_callback_opts=new_rules_callback_opts,
            merge_callback=merge_callback,
            merge_callback_opts=merge_callback_opts,
            match_quality=match_quality,
            match_len_trashold=match_len_trashold,
            data=self._data,
        )

    def __repr__(self):
        return f"<MergeWrapper: {self._data}>"

    def __dir__(self):
        self_attrs = super().__dir__()
        data_attrs = self._data.__dir__()
        return list(set([*self_attrs, *data_attrs]))

    def __getattr__(self, key):
        return getattr(self._data, key)

    def __iter__(self):
        return self._data.__iter__()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if isinstance(self._data, dict):
            if key not in self._data:
                self._sm.add(key, value)
        else:
            if value not in self._data:
                self._sm.add(value)
        self._data[key] = value

    def append(self, value):
        if value not in self._data:
            self._sm.add(value)
        self._data.append(value)

    def get_wrapped(self, value):
        return self._sm.get(value)
