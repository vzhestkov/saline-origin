import logging
import os

import salt.config
import salt.syspaths
import salt.utils.immutabletypes as immutabletypes
import salt.utils.user

from salt.config import _validate_opts
from salt._logging import (
    DFLT_LOG_DATEFMT,
    DFLT_LOG_DATEFMT_LOGFILE,
    DFLT_LOG_FMT_CONSOLE,
    DFLT_LOG_FMT_JID,
    DFLT_LOG_FMT_LOGFILE,
)


log = logging.getLogger(__name__)

VALID_OPTS = immutabletypes.freeze(
    {
        # The path to the Saline configuration file
        "conf_file": str,
        # The path to a directory to pull in configuration file includes
        "default_include": str,
        # The type of hashing algorithm to use when doing file comparisons
        "hash_type": str,
        # The file to send logging data to
        "log_file": str,
        # The format to construct dates in log files
        "log_datefmt": str,
        # The dateformat for a given logfile
        "log_datefmt_logfile": str,
        # The format for console logs
        "log_fmt_console": str,
        # The format for a given log file
        "log_fmt_logfile": (tuple, str),
        # The level of verbosity at which to log
        "log_level": str,
        # The log level to log to a given file
        "log_level_logfile": (type(None), str),
        # A dictionary of logging levels
        "log_granular_levels": dict,
        # Perform pre-flight verification steps before daemon startup, such as checking configuration
        # files and certain directories.
        "verify_env": bool,
        # The user under which the daemon should run
        "user": str,
        # The number of event readers subprocesses
        "readers_subprocesses": int,
        # The events regex filter limiting the scope of events to watch
        "events_regex_filter": str,
        # The list of additional allowed events
        "events_additional": list,
        # The directory containing unix sockets
        "sock_dir": str,
        # IPC buffer size
        "ipc_write_buffer": int,
        # The rules to rename SLS and state IDs to avoide huge growth of metrics
        "rename_rules": dict,
        # The interval of checking if the minion is timed out to do the job
        "job_timeout_check_interval": int,
        # The amount of seconds to consider the job is timed out for the minion
        "job_timeout": int,
        # The interval of updating metrics for the jobs
        "job_metrics_update_interval": int,
        # The time interval to clean up the completed/timedout JIDs
        "job_cleanup_after": int,
        # The replacement of blank value of mods to prevent passing to Prometheus
        "set_highstate_mods_in_metrics": str,
        # Tell the loader to attempt to import *.pyx cython files if cython is available
        "cython_enable": bool,
    }
)

DEFAULT_SALINE_OPTS = immutabletypes.freeze(
    {
        "conf_file": os.path.join(salt.syspaths.CONFIG_DIR, "saline"),
        "default_include": "saline.d/*.conf",
        "extension_modules": os.path.join(salt.syspaths.CACHE_DIR, "saline", "extmods"),
        "hash_type": "sha256",
        "log_file": os.path.join(salt.syspaths.LOGS_DIR, "saline"),
        "log_datefmt": DFLT_LOG_DATEFMT,
        "log_datefmt_logfile": DFLT_LOG_DATEFMT_LOGFILE,
        "log_fmt_console": DFLT_LOG_FMT_CONSOLE,
        "log_fmt_logfile": DFLT_LOG_FMT_LOGFILE,
        "log_granular_levels": {},
        "log_level": "warning",
        "log_level_logfile": "warning",
        "verify_env": True,
        "user": salt.utils.user.get_user(),
        "readers_subprocesses": 3,
        "events_regex_filter": "salt/job/\d+/(new|ret/.+)",
        "events_additional": [
            "salt/auth",
            "salt/key",
            "salt/batch/\d+/(start|done)",
            "salt/(run|wheel)/\d+/(new|ret)",
        ],
        "sock_dir": "/run/saline",
        "ipc_write_buffer": 0,
        "rename_rules": {"sls": {}, "sid": {}},
        "job_timeout_check_interval": 120,
        "job_timeout": 1200,
        "job_metrics_update_interval": 3,
        "job_cleanup_after": 1200,
        "set_highstate_mods_in_metrics": "",
        "cython_enable": False,
    }
)


def saline_config(
    path,
    env_var="SALINE_CONFIG",
    defaults=None,
    ignore_config_errors=True,
    role="saline",
):
    """
    Reads in the Saline configuration file and sets up special options

    .. code-block:: python

        import saline.config
        saline_opts = saline.config.saline_config('/etc/salt/saline')
    """

    if defaults is None:
        defaults = DEFAULT_SALINE_OPTS.copy()

    if not os.environ.get(env_var, None):
        # No valid setting was given using the configuration variable.
        # Lets see is SALT_CONFIG_DIR is of any use
        salt_config_dir = os.environ.get("SALT_CONFIG_DIR", None)
        if salt_config_dir:
            env_config_file_path = os.path.join(salt_config_dir, "saline")
            if salt_config_dir and os.path.isfile(env_config_file_path):
                # We can get a configuration file using SALT_CONFIG_DIR, let's
                # update the environment with this information
                os.environ[env_var] = env_config_file_path

    overrides = salt.config.load_config(path, env_var, DEFAULT_SALINE_OPTS["conf_file"])
    default_include = overrides.get("default_include", defaults["default_include"])
    include = overrides.get("include", [])

    overrides.update(
        salt.config.include_config(
            default_include,
            path,
            verbose=False,
            exit_on_config_errors=not ignore_config_errors,
        )
    )
    overrides.update(
        salt.config.include_config(
            include, path, verbose=True, exit_on_config_errors=not ignore_config_errors
        )
    )

    opts = apply_saline_config(overrides, defaults)
    opts["__role"] = role
    salt.config.apply_sdb(opts)
    _validate_opts(opts)
    return opts


def apply_saline_config(overrides=None, defaults=None):
    """
    Returns minion configurations dict.
    """

    if defaults is None:
        defaults = DEFAULT_SALINE_OPTS.copy()
    if overrides is None:
        overrides = {}

    opts = defaults.copy()
    opts["__role"] = "saline"
    salt.config._adjust_log_file_override(overrides, defaults["log_file"])
    if overrides:
        opts.update(overrides)

    return opts
