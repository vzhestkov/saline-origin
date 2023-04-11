from saline import config

from salt.features import setup_features
from salt.utils.parsers import MasterOptionParser, OptionParserMeta


class SalineOptionParser(
    MasterOptionParser, metaclass=OptionParserMeta
):  # pylint: disable=no-init

    description = "The Saline reads events from the Salt Master event bus"
    epilog = ""

    # ConfigDirMixIn config filename attribute
    _config_filename_ = "saline"
    # LogLevelMixIn attributes
    _default_logging_logfile_ = config.DEFAULT_SALINE_OPTS["log_file"]
    _setup_mp_logging_listener_ = True

    def setup_config(self):
        opts = config.saline_config(
            self.get_config_file_path(),  # pylint: disable=no-member
            ignore_config_errors=False,
        )
        setup_features(opts)
        return opts
