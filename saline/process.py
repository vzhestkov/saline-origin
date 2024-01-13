import atexit
import cherrypy
import contextlib
import logging
import os
import re
import signal
import sys
import traceback

import salt.ext.tornado.ioloop
import salt.transport.ipc
import salt.syspaths
import salt.utils.files

from cherrypy.process.wspbus import ChannelFailures
from multiprocessing import Pipe, Queue
from threading import Thread, Lock
from time import time, sleep
from queue import Empty as QueueEmpty

from saline import restapi
from saline.data.event import EventParser
from saline.data.merger import DataMerger

from salt.utils.process import (
    ProcessManager,
    SignalHandlingProcess,
    default_signals,
)

log = logging.getLogger(__name__)


class Saline(SignalHandlingProcess):
    """
    The Saline main process
    """

    def __init__(self, opts, **kwargs):
        """
        Create a Saline Events Collector instance

        :param dict opts: The Saline options
        """

        super().__init__()

        self.opts = opts
        self.req_queue = Queue()
        self.ret_queue = Queue()

    def start(self):
        """
        Start the main Saline routine
        """

        with default_signals(signal.SIGINT, signal.SIGTERM):
            log.info("Creating process manager")
            self.process_manager = ProcessManager(wait_for_kill=5)

            self.process_manager.add_process(
                EventsManager,
                args=(
                    self.opts,
                    self.req_queue,
                ),
            )
            self.process_manager.add_process(
                DataManager,
                args=(
                    self.opts,
                    self.ret_queue,
                ),
            )
            for i in range(int(self.opts["readers_subprocesses"])):
                self.process_manager.add_process(
                    EventsReader,
                    args=(
                        self.opts,
                        self.req_queue,
                        self.ret_queue,
                        i,
                    ),
                )
            self.process_manager.add_process(
                CherryPySrv,
                args=(self.opts,),
            )

        # Install the SIGINT/SIGTERM handlers if not done so far
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGINT, self._handle_signals)

        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGTERM, self._handle_signals)

        self.process_manager.run()

    def _handle_signals(self, signum, sigframe):
        # escalate the signals to the process manager
        self.process_manager._handle_signals(signum, sigframe)
        time.sleep(1)
        sys.exit(0)


class EventsManager(SignalHandlingProcess):
    """
    The Saline Events Manager process
    """

    def __init__(self, opts, queue, **kwargs):
        """
        Create a Saline Events Manager instance

        :param dict opts: The Saline options
        :param Queue queue: The queue to put the captured events to
        """

        super().__init__()

        self.name = "EventsManager"

        self.opts = opts
        self.queue = queue

        self._salt_events = None

    def run(self):
        """
        Saline Events Manager routine capturing the events from Sale Event Bus
        """

        log.info("Running Saline Events Manager")

        client_conf_path = os.path.join(salt.syspaths.CONFIG_DIR, "master")

        log.debug("Reading the client config: %s", client_conf_path)
        client_opts = salt.config.client_config(client_conf_path)

        log.debug(
            "Starting reading salt events from: %s (%s)",
            client_opts["sock_dir"],
            client_opts["transport"],
        )

        events_filter_re = re.compile(self.opts["events_regex_filter"])
        events_additional = []
        for add_filter in self.opts.get("events_additional", []):
            events_additional.append(re.compile(add_filter))

        with salt.utils.event.get_event(
            "master",
            sock_dir=client_opts["sock_dir"],
            transport=client_opts["transport"],
            opts=client_opts,
            raise_errors=True,
        ) as salt_events:
            self._selt_events = salt_events
            while True:
                try:
                    event = salt_events.get_event(full=True, auto_reconnect=True)
                except TypeError:
                    # Most probably cosmetic issue on handling the signal
                    event = None
                if event is None:
                    continue

                tag = event.get("tag")

                if events_filter_re.match(tag):
                    self.queue.put(event)
                    continue

                in_additional = False
                for filter_re in events_additional:
                    if filter_re.match(tag):
                        in_additional = True
                        break
                if in_additional:
                    self.queue.put(event)
                    continue

                log.debug("The event tag doesn't match the event filter: %s", tag)

    def _handle_signals(self, signum, sigframe):
        if self._salt_events is not None:
            self._salt_events.close()
        sys.exit(0)


class DataManager(SignalHandlingProcess):
    """
    The Saline Data Manager process
    """

    def __init__(self, opts, queue, **kwargs):
        """
        Create a Saline Data Manager instance

        :param dict opts: The Saline options
        :param Queue queue: The queue to get the processed events from
        """

        super().__init__()

        self.name = "DataManager"

        self.opts = opts
        self.queue = queue

        self.metrics_epoch = None
        self.datamerger = None

        self.server_thread = None
        self.maintenance_thread = None

        self._close_lock = Lock()

    def run(self):
        """
        Saline Data Manager routine merging the processed events to the Data Merger
        """

        log.info("Running Saline Data Manager")

        self.datamerger = DataMerger(self.opts)

        self.server_thread = Thread(target=self.start_server)
        self.server_thread.start()

        self._job_timeout_check_interval = self.opts.get(
            "job_timeout_check_interval", 120
        )
        self._job_timeout = self.opts.get("job_timeout", 1200)
        self._job_metrics_update_interval = self.opts.get(
            "job_metrics_update_interval", 5
        )

        self._job_jids_cleanup_interval = self.opts.get("job_jids_cleanup_interval", 30)

        self._maintenance_stop = False
        self.maintenance_thread = Thread(target=self.start_maintenance)
        self.maintenance_thread.start()

        self.start_datamerger()

    def _handle_signals(self, signum, sigframe):
        # self.io_loop.stop()
        self.stop_maintenance()
        sys.exit(0)

    def start_datamerger(self):
        while True:
            data = self.queue.get()
            self.datamerger.add(data)

    def start_maintenance(self):
        ts = time()
        run_complete_after = ts + self._job_timeout_check_interval
        run_job_metrics_update_after = ts + self._job_metrics_update_interval
        run_job_jids_cleanup_after = ts + self._job_jids_cleanup_interval
        while True:
            sleep(1)
            if self._maintenance_stop:
                break
            ts = time()
            if ts > run_complete_after:
                run_complete_after = ts + self._job_timeout_check_interval
                self.datamerger.jobs.complete_with_timeout(self._job_timeout, ts=ts)
            if ts > run_job_metrics_update_after:
                run_job_metrics_update_after = ts + self._job_metrics_update_interval
                self.datamerger.jobs_metrics_update()
            if ts > run_job_jids_cleanup_after:
                run_job_jids_cleanup_after = ts + self._job_jids_cleanup_interval
                self.datamerger.cleanup_job_jids()

    def stop_maintenance(self):
        if self.maintenance_thread is not None:
            self._maintenance_stop = True
            self.maintenance_thread.join()
            self.maintenance_thread = None

    def start_server(self):
        self.io_loop = salt.ext.tornado.ioloop.IOLoop()
        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            pub_uri = os.path.join(self.opts["sock_dir"], "publisher.ipc")
            self.publisher = salt.transport.ipc.IPCMessagePublisher(
                {"ipc_write_buffer": self.opts.get("ipc_write_buffer", 0)},
                pub_uri,
                io_loop=self.io_loop,
            )
            with salt.utils.files.set_umask(0o177):
                self.publisher.start()
            atexit.register(self.close)
            with contextlib.suppress(KeyboardInterrupt):
                try:
                    self.io_loop.run_sync(self.metrics_publisher)
                finally:
                    # Make sure the IO loop and respective sockets are closed and destroyed
                    self.close()

    @salt.ext.tornado.gen.coroutine
    def metrics_publisher(self):
        last_update = time()
        while True:
            epoch = self.datamerger.get_metrics_epoch()
            cur_time = time()
            if (
                epoch != self.metrics_epoch
                or self.metrics_epoch is None
                or cur_time - last_update > 110
            ):
                self.metrics_epoch = epoch
                last_update = cur_time
                self.publisher.publish({"metrics": self.datamerger.get_metrics()})
            yield salt.ext.tornado.gen.sleep(3)

    def close(self):
        try:
            self._close_lock.acquire()
            atexit.unregister(self.close)
            if self.publisher is not None:
                self.publisher.close()
                self.publisher = None
            if self.io_loop is not None:
                self.io_loop.close()
                self.io_loop = None
        finally:
            self._close_lock.release()


class EventsReader(SignalHandlingProcess):
    """
    The Saline Events Reader process
    """

    def __init__(self, opts, req_queue, ret_queue, idx, **kwargs):
        """
        Create a Saline Events Reader instance

        :param dict opts: The Saline options
        :param Queue queue: The queue to put the captured events to
        """

        super().__init__()

        self._idx = idx
        self.name = "EventsReader-%s" % idx

        self.opts = opts
        self.req_queue = req_queue
        self.ret_queue = ret_queue

        self._exit = False

        self.event_parser = EventParser(self.opts)

    def run(self):
        """
        Saline Events Reader routine processing the captured Salt Events
        """

        log.info("Running Saline Events Reader: %s", self.name)

        while True:
            try:
                event = self.req_queue.get(timeout=1)
            except QueueEmpty:
                continue
            except (ValueError, OSError):
                return
            if self._exit:
                return
            parsed_data = self.event_parser.parse(event.get("tag"), event.get("data"))
            if parsed_data is not None:
                parsed_data["rix"] = self._idx
                self.ret_queue.put(parsed_data)

    def _handle_signals(self, signum, sigframe):
        self._exit = True
        sys.exit(0)


class CherryPySrv(SignalHandlingProcess):
    """
    The Saline CherryPy Server process
    """

    def __init__(self, opts, **kwargs):
        """
        Create a Saline CherryPy Server instance

        :param dict opts: The Saline options
        """

        super().__init__()

        self.name = "CherryPySrv"

        self.opts = opts

    def run(self):
        """
        Turn on the Saline CherryPy Server components
        """

        log.info("Running Saline CherryPy Server")

        self.cherrypy_server(self.opts)

    def cherrypy_server(self, opts):
        """
        Saline CherryPy Server routine processing the external requests

        :param dict opts: The Saline options
        """

        root, apiopts, conf = restapi.get_app(opts)

        if not apiopts.get("disable_ssl", False):
            if "ssl_crt" not in apiopts or "ssl_key" not in apiopts:
                log.error(
                    "Not starting Saline CherryPy Server. Options 'ssl_crt' and "
                    "'ssl_key' are required if SSL is not disabled."
                )
                return None

        if "ssl_crt" in apiopts and "ssl_key" in apiopts:
            self.verify_certs(apiopts["ssl_crt"], apiopts["ssl_key"])

            cherrypy.server.ssl_module = "builtin"
            cherrypy.server.ssl_certificate = apiopts["ssl_crt"]
            cherrypy.server.ssl_private_key = apiopts["ssl_key"]
            if "ssl_chain" in apiopts.keys():
                cherrypy.server.ssl_certificate_chain = apiopts["ssl_chain"]

        # Prevent propagating CherryPy logging to main saline log
        # in case if distinct log files specified in the config
        if apiopts.get("log_access_file", None) is not None:
            cherrypy.log.access_log.propagate = False
        if apiopts.get("log_error_file", None) is not None:
            cherrypy.log.error_log.propagate = False

        try:
            cherrypy.quickstart(root, apiopts.get("root_prefix", "/"), conf)
        # except (ChannelFailures, TypeError):
        except Exception:
            log.critical(
                "Suppressing most probably cosmetic exception: %s",
                traceback.format_exc(),
            )

    def verify_certs(self, *cert_files):
        """
        Sanity checking for the specified SSL certificates
        """

        for cert_file in cert_files:
            if not os.path.exists(cert_file):
                raise Exception("Could not find a certificate: {}".format(cert_file))

    def _handle_signals(self, signum, sigframe):
        logging.raiseExceptions = False
        self.stop_cherrypy()
        sys.exit(0)

    @cherrypy.expose
    def stop_cherrypy(self):
        cherrypy.engine.exit()
