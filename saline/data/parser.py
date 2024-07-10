import re

from dateutil.parser import parse as datetime_parse, ParserError
from time import time

from salt.utils.args import parse_input as parse_input_args


class EventTags:
    # salt/job/*...
    SALT_JOB = 1
    # salt/job/*/new
    SALT_JOB_NEW = 1
    # salt/job/*/ret/*
    SALT_JOB_RET = 2
    # [0-9]+
    SALT_JID = 2
    # minion/refresh/*
    SALT_MINION_REFRESH = 3
    # salt/batch/*/*
    SALT_BATCH = 4
    # salt/batch/*/start
    SALT_BATCH_START = 1
    # salt/batch/*/done
    SALT_BATCH_DONE = 2
    # salt/auth
    SALT_AUTH = 5
    # salt/key
    SALT_KEY = 6
    # salt/minion/*/start
    SALT_MINION_START = 7
    # salt/beacon/*/*...
    SALT_BEACON = 8
    # salt/run/*/*
    SALT_RUN = 9
    # salt/run/*/new
    SALT_RUN_NEW = 1
    # salt/run/*/ret
    SALT_RUN_RET = 2
    # salt/wheel/*/*
    SALT_WHEEL = 10
    # salt/wheel/*/new
    SALT_WHEEL_NEW = 1
    # salt/wheel/*/ret
    SALT_WHEEL_RET = 2
    # salt/stats/*
    SALT_STATS = 11


IGNORE_EVENTS = (
    (EventTags.SALT_WHEEL, EventTags.SALT_WHEEL_NEW, "wheel.key.list_all"),
    (EventTags.SALT_WHEEL, EventTags.SALT_WHEEL_RET, "wheel.key.list_all"),
)

IGNORE_NO_FUN_WARNING = (
    (EventTags.SALT_AUTH, None),
    (EventTags.SALT_BATCH, EventTags.SALT_BATCH_START),
    (EventTags.SALT_BATCH, EventTags.SALT_BATCH_DONE),
    (EventTags.SALT_MINION_START, None),
    (EventTags.SALT_MINION_REFRESH, None),
    (EventTags.SALT_STATS, None),
)

STATE_RESULTS = (
    (True, "succeeded"),
    (False, "failed"),
    (None, "notrun"),
    ("warnings", "warnings"),
)


def __salt_batch(match):
    if match.group(1) == "start":
        sub_tag = EventTags.SALT_BATCH_START
    else:
        sub_tag = EventTags.SALT_BATCH_DONE
    return "salt/batch/*/{}".format(match.group(1)), sub_tag


def __salt_beacon(match):
    return "salt/beacon/*/{}".format(match.group(1))


def __salt_run_wheel(match):
    tag_main = getattr(EventTags, "SALT_%s" % match.group(1).upper())
    tag_sub = getattr(
        EventTags, "SALT_%s_%s" % (match.group(1).upper(), match.group(2).upper())
    )
    return "salt/{}/*/{}".format(match.group(1), match.group(2)), tag_main, tag_sub


__TAG_PATTERNS = (
    (
        re.compile("salt/job/\d+/ret/(.*)"),
        "salt/job/*/ret/*",
        EventTags.SALT_JOB,
        EventTags.SALT_JOB_RET,
        1,
    ),
    (re.compile("\d+"), "JID", EventTags.SALT_JID, None, None),
    (
        re.compile("minion/refresh/(.+)"),
        "minion/refresh/*",
        EventTags.SALT_MINION_REFRESH,
        None,
        1,
    ),
    (
        re.compile("salt/job/\d+/new"),
        "salt/job/*/new",
        EventTags.SALT_JOB,
        EventTags.SALT_JOB_NEW,
        None,
    ),
    (
        re.compile("salt/batch/\d+/(start|done)"),
        __salt_batch,
        EventTags.SALT_BATCH,
        None,
        None,
    ),
    (
        re.compile("salt/minion/([^\/]+)/start"),
        "salt/minion/*/start",
        EventTags.SALT_MINION_START,
        None,
        1,
    ),
    (
        re.compile("salt/auth"),
        "salt/auth",
        EventTags.SALT_AUTH,
        None,
        None,
    ),
    (
        re.compile("salt/key"),
        "salt/key",
        EventTags.SALT_KEY,
        None,
        None,
    ),
    (
        re.compile("salt/beacon/[^\/]+/(.*)"),
        __salt_beacon,
        EventTags.SALT_BEACON,
        None,
        None,
    ),
    (
        re.compile("salt/(run|wheel)/\d+/(new|ret)"),
        __salt_run_wheel,
        None,
        None,
        None,
    ),
    (
        re.compile("salt/stats/[^\/]+"),
        "salt/stats/*",
        EventTags.SALT_STATS,
        None,
        None,
    ),
)

__STATE_TAGS_DIV = "_|-"


def get_tag_mask(tag, return_all=False, return_minion_id=False):
    tag_minion_id = None
    for pattern, repl, tag_main, tag_sub, tag_minion_group in __TAG_PATTERNS:
        match = pattern.match(tag)
        if match:
            if callable(repl):
                tag = repl(match)
                if isinstance(tag, tuple):
                    if len(tag) == 3:
                        tag, tag_main, tag_sub = tag
                    else:
                        tag, tag_sub = tag
            else:
                tag = repl
            if tag_minion_group is not None:
                tag_minion_id = match.group(tag_minion_group)
            break
    if return_all:
        if return_minion_id:
            return tag, tag_main, tag_sub, tag_minion_id
        return tag, tag_main, tag_sub
    else:
        if return_minion_id:
            return tag, tag_minion_id
        return tag


def get_timestamp(ts):
    """
    Get unix timestamp from Salt timestamp
    """

    try:
        ts = datetime_parse("%sZ" % ts).timestamp()
    except ParserError:
        # Return current time if not possible to parse the timestamp
        ts = time()
    return ts


def get_trimmed(data):
    """
    Generator returning the trimmed value pathes from Salt data
    """

    l = [(data, "")]
    while l:
        i, p = l.pop(0)
        if isinstance(i, dict):
            for k, v in i.items():
                l.append((v, '%s["%s"]' % (p, k.replace('"', '\\"'))))
        elif isinstance(i, (list, tuple)):
            for k, v in enumerate(i):
                l.append((v, "%s[%s]" % (p, k)))
        elif isinstance(i, str) and i == "VALUE_TRIMMED":
            yield p


def split_state_tags(tags, name=None):
    """
    Get get state ID and state function by state return key
    """

    mod, tags = tags.split(__STATE_TAGS_DIV, 1)
    tags, fun = tags.rsplit(__STATE_TAGS_DIV, 1)

    id_ = None

    if name:
        div_name = "%s%s" % (__STATE_TAGS_DIV, name)
        if div_name in tags:
            id_ = tags.replace(div_name, "")

    if id_ is None:
        id_, name = tags.split(__STATE_TAGS_DIV, 1)

    return id_, "%s.%s" % (mod, fun), name


def parse_duration(dur):
    if isinstance(dur, (int, float)):
        return dur
    if isinstance(dur, str) and dur.endswith(" ms"):
        try:
            return float(dur[0:-3])
        except ValueError:
            return None
    return None


def parse_state_fun_args(fun_args):
    args = []
    kwargs = {}

    for arg in fun_args:
        if isinstance(arg, dict):
            arg.pop("__kwarg__", None)
            for key, val in arg.items():
                kwargs[key] = val
        else:
            pkwargs = parse_input_args([arg], condition=False)[1]
            if pkwargs:
                kwargs.update(pkwargs)
            else:
                args.append(arg)

    args = kwargs.pop("mods", args)
    if not isinstance(args, list):
        args = [args]
    args = (
        *[
            x if x.startswith("/") else x.replace("/", ".")
            for x in args
        ],
    )

    return args, kwargs
