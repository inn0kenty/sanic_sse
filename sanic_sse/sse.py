"""Sse module.

This module add sse compability to sanic app
"""

import re
import io
import asyncio
import contextlib
import inspect
from http import HTTPStatus
from sanic import Sanic
from sanic.response import stream
from sanic.exceptions import abort
from .pub_sub import PubSub

# pylint: disable=bad-continuation


class Sse:
    """
    A :class: that knows how to publish, subscribe to, and stream server-sent events.
    """

    _DEFAULT_PING_INTERVAL = 15
    _DEFAULT_SEPARATOR = "\r\n"
    _LINE_SEP_EXPR = re.compile(r"\r\n|\r|\n")

    _DEFAULT_URL = "/sse"

    _HEADERS = {"Cache-Control": "no-cache"}

    def __init__(  # type: ignore
        self,
        app: Sanic = None,
        url: str = _DEFAULT_URL,
        ping_interval: int = _DEFAULT_PING_INTERVAL,
        before_request_func=None,
    ):
        """
        Application initialization

        :param `sanic.Sanic` app: Sanic application
        :param str url: sse event url
        :param int ping_interval: interval of ping message
        """
        self._ping_task = None
        self._before_request = None

        if app is not None:
            self.init_app(app, url, ping_interval, before_request_func)

    async def _ping(self):
        # periodically send ping to the browser. Any message that
        # starts with ":" colon ignored by a browser and could be used
        # as ping message.
        while True:
            await asyncio.sleep(self._ping_interval)
            await self._pubsub.publish(
                ": ping{0}{0}".format(self._DEFAULT_SEPARATOR).encode("utf-8")
            )

    @staticmethod
    def _prepare(data, event_id=None, event=None, retry=None):
        buffer = io.StringIO()
        if event_id is not None:
            buffer.write(Sse._LINE_SEP_EXPR.sub("", f"id: {event_id}"))
            buffer.write(Sse._DEFAULT_SEPARATOR)

        if event is not None:
            buffer.write(Sse._LINE_SEP_EXPR.sub("", f"event: {event}"))
            buffer.write(Sse._DEFAULT_SEPARATOR)

        for chunk in Sse._LINE_SEP_EXPR.split(data):
            buffer.write(f"data: {chunk}")
            buffer.write(Sse._DEFAULT_SEPARATOR)

        if retry is not None:
            if not isinstance(retry, int):
                raise TypeError("retry argument must be int")
            buffer.write(f"retry: {retry}")
            buffer.write(Sse._DEFAULT_SEPARATOR)

        buffer.write(Sse._DEFAULT_SEPARATOR)

        return buffer.getvalue().encode("utf-8")

    async def send(  # pylint: disable=too-many-arguments
        self,
        data: str,
        channel_id: str = None,
        event_id: str = None,
        event: str = None,
        retry: int = None,
    ):
        """Send data using EventSource protocol. This call is blocking
        :param str data: The data field for the message.
        :param str event_id: The event ID to set the EventSource object's last
            event ID value to.
        :param str event: The event's type. If this is specified, an event will
            be dispatched on the browser to the listener for the specified
            event name; the web site would use addEventListener() to listen
            for named events. The default event type is "message".
        :param int retry: The reconnection time to use when attempting to send
            the event. [What code handles this?] This must be an integer,
            specifying the reconnection time in milliseconds. If a non-integer
            value is specified, the field is ignored.
        """

        data = self._prepare(data, event_id, event, retry)

        await self._pubsub.publish(data, channel_id)

    def send_nowait(  # pylint: disable=too-many-arguments
        self,
        data: str,
        channel_id: str = None,
        event_id: str = None,
        event: str = None,
        retry: int = None,
    ):
        """Send data using EventSource protocol. This call is not blocking.
        :param str data: The data field for the message.
        :param str event_id: The event ID to set the EventSource object's last
            event ID value to.
        :param str event: The event's type. If this is specified, an event will
            be dispatched on the browser to the listener for the specified
            event name; the web site would use addEventListener() to listen
            for named events. The default event type is "message".
        :param int retry: The reconnection time to use when attempting to send
            the event. [What code handles this?] This must be an integer,
            specifying the reconnection time in milliseconds. If a non-integer
            value is specified, the field is ignored.
        """

        data = self._prepare(data, event_id, event, retry)

        self._pubsub.publish_nowait(data, channel_id)

    def set_before_request_callback(self, func):
        """
        Set function for callback before sse request. It can be used for authorizations purpose

        :param callable func: coroutine function with one parameter - request
        """
        if not callable(func):
            raise TypeError(f"{func} should be callable")
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"{func} should be coroutine function")
        if len(inspect.signature(func).parameters) != 1:
            raise ValueError(f"{func} should get only one parameter - request")

        self._before_request = func

    def init_app(
        self,
        app: Sanic,
        url: str = _DEFAULT_URL,
        ping_interval: int = _DEFAULT_PING_INTERVAL,
        before_request_func=None,
    ):
        """
        Application initialization

        :param `sanic.Sanic` app: Sanic application
        :param str url: sse event url
        :param int ping_interval: interval of ping message
        """
        self._url = url
        self._ping_interval = ping_interval

        if before_request_func is not None:
            self.set_before_request_callback(before_request_func)

        self._pubsub = PubSub()

        @app.listener("after_server_start")
        def _on_start(_, loop):
            self._ping_task = loop.create_task(self._ping())

        @app.listener("before_server_stop")
        async def _on_stop(_, __):
            self._ping_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ping_task

            await self._pubsub.close()

        app.sse_send = self.send
        app.sse_send_nowait = self.send_nowait

        @app.route(self._url, methods=["GET"])
        async def _(request):
            if self._before_request is not None:
                await self._before_request(request)

            channel_id = request.args.get("channel_id", None)
            try:
                channel_id = self._pubsub.register(channel_id=channel_id)
            except ValueError as exc:
                abort(HTTPStatus.BAD_REQUEST, str(exc))

            async def streaming_fn(response):
                try:
                    while True:
                        try:
                            data = await self._pubsub.get(channel_id)
                        except ValueError:
                            break
                        await response.write(data)
                        self._pubsub.task_done(channel_id)
                finally:
                    self._pubsub.delete(channel_id)

            return stream(
                streaming_fn, headers=self._HEADERS, content_type="text/event-stream"
            )
