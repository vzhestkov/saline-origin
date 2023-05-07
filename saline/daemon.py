import logging
import os
import pwd
import signal
import traceback

from salt.cli.daemons import DaemonsMixin
from salt.utils.process import HAS_PSUTIL, notify_systemd
from salt.utils.user import get_user
from salt.utils.verify import check_user, verify_env, verify_log

from saline.config.parser import SalineOptionParser


log = logging.getLogger(__name__)


class Saline(SalineOptionParser, DaemonsMixin):
    """
    Create a Saline server
    """

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        self.main_process.process_manager._handle_signals(signum, sigframe)
        super()._handle_signals(signum, sigframe)

    def prepare(self):
        super().prepare()

        try:
            if self.config["verify_env"]:
                confd = self.config.get("default_include")
                if confd:
                    # If 'default_include' is specified in config, then use it
                    if "*" in confd:
                        # Value is of the form "minion.d/*.conf"
                        confd = os.path.dirname(confd)
                    if not os.path.isabs(confd):
                        # If configured 'default_include' is not an absolute
                        # path, consider it relative to folder of 'conf_file'
                        # (/etc/salt by default)
                        confd = os.path.join(
                            os.path.dirname(self.config["conf_file"]), confd
                        )
                else:
                    confd = os.path.join(
                        os.path.dirname(self.config["conf_file"]), "saline.d"
                    )

                v_dirs = [
                    confd,
                ]

                verify_env(
                    v_dirs,
                    self.config["user"],
                )
        except OSError as error:
            self.environment_failure(error)

        verify_log(self.config)
        log.info("Setting up the Saline")

        # Bail out if we find a process running and it matches out pidfile
        if (HAS_PSUTIL and not self.claim_process_responsibility()) or (
            not HAS_PSUTIL and self.check_running()
        ):
            self.action_log_info("An instance is already running. Exiting")
            self.shutdown(1)

        # Late import so logging works correctly
        import saline.process

        self.main_process = saline.process.Saline(self.config)

        self.daemonize_if_required()
        self.set_pidfile()
        notify_systemd()

        sock_dir = self.config["sock_dir"]
        if not os.path.isdir(sock_dir):
            try:
                os.makedirs(sock_dir, 0o755)
            except OSError as exc:
                log.error("Could not create SOCK_DIR: %s", exc)

        saline_user = self.config["user"]
        if saline_user != get_user():
            try:
                pwnam = pwd.getpwnam(saline_user)
                uid = pwnam.pw_uid
                gid = pwnam.pw_gid
                os.chown(sock_dir, uid, gid)
            except KeyError:
                log.warning("Unable to get UID and GID for the user: %s", saline_user)

    def start(self):
        """
        Start the Saline.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        """

        super().start()

        if check_user(self.config["user"]):
            self.start_log_info()
            self.verify_hash_type()
            log.info("Saline is starting as user '%s'", get_user())
            self.main_process.start()

    def shutdown(self, exitcode=0, exitmsg=None):
        """
        If sub-classed, run any shutdown operations on this method.
        """

        self.shutdown_log_info()
        msg = "The Saline is shutdown."

        super(Saline, self).shutdown(
            exitcode, "{} {}".format(msg, exitmsg) if exitmsg is not None else msg
        )

    def shutdown_log_info(self):
        """
        Say daemon shutting down.

        :return:
        """

        log.info("The %s/%s is shut down", self.__class__.__name__, os.getpid())
