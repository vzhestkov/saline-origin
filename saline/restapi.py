import cherrypy
import functools
import io
import logging
import os

import salt.utils.json
import salt.utils.yaml

from threading import Thread
from time import sleep

from salt.ext.tornado.iostream import StreamClosedError
from salt.netapi.rest_cherrypy.app import cors_tool, hypermedia_in, hypermedia_out


log = logging.getLogger(__name__)


def html_override_tool():
    """
    Bypass the normal handler and serve HTML for all URLs

    The ``app_path`` setting must be non-empty and the request must ask for
    ``text/html`` in the ``Accept`` header.
    """
    apiopts = cherrypy.config["apiopts"]
    request = cherrypy.request

    url_blacklist = (
        apiopts.get("app_path", "/app"),
        apiopts.get("static_path", "/static"),
    )

    if "app" not in cherrypy.config["apiopts"]:
        return

    if request.path_info.startswith(url_blacklist):
        return

    if request.headers.get("Accept") == "*/*":
        return

    try:
        wants_html = cherrypy.lib.cptools.accept("text/html")
    except cherrypy.HTTPError:
        return
    else:
        if wants_html != "text/html":
            return

    raise cherrypy.InternalRedirect(apiopts.get("app_path", "/app"))


tools_config = {
    "on_start_resource": [
        ("html_override", html_override_tool),
        #        ("salt_token", salt_token_tool),
    ],
    "before_request_body": [
        ("cors_tool", cors_tool),
        ("hypermedia_in", hypermedia_in),
        #        ("salt_auth", salt_auth_tool),
    ],
    "before_handler": [
        ("hypermedia_out", hypermedia_out),
        #        ("lowdata_fmt", lowdata_fmt),
        #        ("salt_ip_verify", salt_ip_verify_tool),
    ],
}

for hook, tool_list in tools_config.items():
    for idx, tool_config in enumerate(tool_list):
        tool_name, tool_fn = tool_config
        setattr(
            cherrypy.tools, tool_name, cherrypy.Tool(hook, tool_fn, priority=(50 + idx))
        )


class MainAdapter:
    """
    The main entry point to Saline's REST API
    """

    exposed = True

    _cp_config = {
        "tools.hypermedia_out.on": True,
        "tools.hypermedia_in.on": True,
    }

    def __init__(self):
        self.opts = cherrypy.config["salineopts"]
        self.apiopts = cherrypy.config["apiopts"]

    def GET(self):
        return {"return": "GET placeholder"}

    def POST(self, **kwargs):
        return {"return": "POST placeholder"}


class MetricsAdapter:
    """
    The metrics entry point of Saline to use with Prometheus
    """

    exposed = True

    def __init__(self):
        self.opts = cherrypy.config["salineopts"]

        self.channels_thread = Thread(target=self.run_channels)
        self.channels_thread.start()

        self.metrics_buf = None

    def run_channels(self):
        self.io_loop = salt.ext.tornado.ioloop.IOLoop()
        self.pub_uri = os.path.join(self.opts["sock_dir"], "publisher.ipc")
        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            self.subscriber = salt.transport.ipc.IPCMessageSubscriber(
                self.pub_uri, io_loop=self.io_loop
            )
            self.subscriber.callbacks.add(self.channel_event_handler)
            for _ in range(5):
                try:
                    self.subscriber.connect(callback=self.channel_connected)
                    break
                except StreamClosedError:
                    sleep(1)
            self.io_loop.run_sync(self.subscriber.read_async)

    def channel_connected(self, _):
        self.metrics_buf = ""

    def channel_event_handler(self, raw):
        if "metrics" in raw:
            self.metrics_buf = raw["metrics"]

    def GET(self):
        cherrypy.response.headers["Cache-Control"] = "no-cache"
        cherrypy.response.headers[
            "Content-Type"
        ] = "text/plain;version=0.0.4;charset=utf-8"

        if self.metrics_buf is not None:
            return self.metrics_buf

        raise cherrypy.HTTPError(500, "No metrics connection available")


class API:
    """
    Collect configuration and URL map for building the CherryPy app
    """

    url_map = {
        "index": MainAdapter,
        "metrics": MetricsAdapter,
    }

    def __init__(self):
        self.opts = cherrypy.config["salineopts"]
        self.apiopts = cherrypy.config["apiopts"]

        for url, cls in self.url_map.items():
            setattr(self, url, cls())

    def get_conf(self):
        """
        Combine the CherryPy configuration with the saline restapi config values
        pulled from the saline config and return the CherryPy configuration
        """

        conf = {
            "global": {
                "server.socket_host": self.apiopts.get("host", "0.0.0.0"),
                "server.socket_port": self.apiopts.get("port", 8216),
                "server.thread_pool": self.apiopts.get("thread_pool", 100),
                "server.socket_queue_size": self.apiopts.get("queue_size", 30),
                "max_request_body_size": self.apiopts.get(
                    "max_request_body_size", 1048576
                ),
                "debug": self.apiopts.get("debug", False),
                "log.access_file": self.apiopts.get("log_access_file", ""),
                "log.error_file": self.apiopts.get("log_error_file", ""),
            },
            "/": {
                "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
                "tools.trailing_slash.on": True,
                "tools.gzip.on": True,
                "tools.html_override.on": True,
                "tools.cors_tool.on": True,
            },
        }

        if "favicon" in self.apiopts:
            conf["/favicon.ico"] = {
                "tools.staticfile.on": True,
                "tools.staticfile.filename": self.apiopts["favicon"],
            }

        if self.apiopts.get("debug", False) is False:
            conf["global"]["environment"] = "production"

        # Serve static media if the directory has been set in the configuration
        if "static" in self.apiopts:
            conf[self.apiopts.get("static_path", "/static")] = {
                "tools.staticdir.on": True,
                "tools.staticdir.dir": self.apiopts["static"],
            }

        # Add to global config
        cherrypy.config.update(conf["global"])

        return conf


def get_app(opts):
    """
    Returns a WSGI app and a configuration dictionary
    """

    apiopts = opts.get("restapi", {})

    # Add Saline and Saline API config options to the main CherryPy config dict
    cherrypy.config["salineopts"] = opts
    cherrypy.config["apiopts"] = apiopts

    root = API()  # cherrypy app
    cpyopts = root.get_conf()  # cherrypy app opts

    return root, apiopts, cpyopts
