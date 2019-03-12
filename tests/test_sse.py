# pylint: disable=missing-docstring, protected-access
import asyncio
import contextlib
import pytest
from sanic import Sanic
from sanic.exceptions import InvalidUsage
from sanic_sse import Sse


def test_create():
    sanic_app = Sanic()
    sse = Sse(sanic_app)

    assert sse._url == Sse._DEFAULT_URL
    assert sse._ping_task is None
    assert sse._ping_interval == Sse._DEFAULT_PING_INTERVAL


@pytest.mark.asyncio
async def test_listeners():
    sanic_app = Sanic()
    sse = Sse()
    sse.init_app(sanic_app)

    sanic_app.listeners["after_server_start"][0](sanic_app, asyncio.get_event_loop())

    assert sse._ping_task is not None

    await sanic_app.listeners["before_server_stop"][0](
        sanic_app, asyncio.get_event_loop()
    )

    assert sse._ping_task.cancelled()


def test_prepate():
    data = "test data"
    event_id = "1"
    event = "2"
    retry = 3

    result = Sse._prepare(data, event_id=event_id, event=event, retry=retry)

    assert (
        result
        == f"id: {event_id}\r\nevent: {event}\r\ndata: {data}\r\nretry: {retry}\r\n\r\n".encode()
    )

    with pytest.raises(TypeError):
        Sse._prepare(data, retry="3")


@pytest.mark.asyncio
async def test_ping():
    sanic_app = Sanic()
    sse = Sse(sanic_app, ping_interval=0.1)

    channel_id = sse._pubsub.register()

    sanic_app.listeners["after_server_start"][0](sanic_app, asyncio.get_event_loop())

    await asyncio.sleep(0)

    data = await sse._pubsub.get(channel_id)

    assert data == b": ping\r\n\r\n"

    await sanic_app.listeners["before_server_stop"][0](
        sanic_app, asyncio.get_event_loop()
    )


@pytest.mark.asyncio
async def test_send():
    sanic_app = Sanic()
    sse = Sse(sanic_app)

    channel_id = sse._pubsub.register()

    data = "test data"
    event_id = "1"
    event = "2"
    retry = 3

    await sanic_app.sse_send(  # pylint: disable=no-member
        data, event_id=event_id, event=event, retry=retry
    )

    await asyncio.sleep(0)

    result = await sse._pubsub.get(channel_id)

    assert (
        result
        == f"id: {event_id}\r\nevent: {event}\r\ndata: {data}\r\nretry: {retry}\r\n\r\n".encode()
    )


@pytest.mark.asyncio
async def test_send_nowait():
    sanic_app = Sanic()
    sse = Sse(sanic_app)

    channel_id = sse._pubsub.register()

    data = "test data"
    event_id = "1"
    event = "2"
    retry = 3

    sanic_app.sse_send_nowait(  # pylint: disable=no-member
        data, event_id=event_id, event=event, retry=retry
    )

    await asyncio.sleep(0)

    result = await sse._pubsub.get(channel_id)

    assert (
        result
        == f"id: {event_id}\r\nevent: {event}\r\ndata: {data}\r\nretry: {retry}\r\n\r\n".encode()
    )


@pytest.mark.asyncio
async def test_before_request_callback():
    sanic_app = Sanic()

    async def test_func(request):
        assert "channel_id" in request.args

    Sse(sanic_app, before_request_func=test_func)

    class Request:  # pylint: disable=too-few-public-methods
        args = {"channel_id": "1"}

    await sanic_app.router.routes_all["/sse"].handler(Request())


@pytest.mark.asyncio
async def test_before_request_callback_bad():
    sanic_app = Sanic()

    def test_func1(_):
        assert True

    with pytest.raises(TypeError):
        Sse(sanic_app, before_request_func=test_func1)

    async def test_func2(_, __):
        assert True

    with pytest.raises(ValueError):
        Sse(sanic_app, before_request_func=test_func2)

    test_func3 = ""
    with pytest.raises(TypeError):
        Sse(sanic_app, before_request_func=test_func3)


@pytest.mark.asyncio
async def test_streaming_fn():
    sanic_app = Sanic()

    sse = Sse(sanic_app)

    class Request:  # pylint: disable=too-few-public-methods
        args = {"channel_id": "1"}

    counter = 0

    class Response:  # pylint: disable=too-few-public-methods
        @staticmethod
        async def write(data):
            nonlocal counter
            counter += 1
            assert data == b"data: test\r\n\r\n"

    str_response = await sanic_app.router.routes_all["/sse"].handler(Request())

    fut = asyncio.ensure_future(str_response.streaming_fn(Response()))

    await sanic_app.sse_send("test")  # pylint: disable=no-member
    await sse._pubsub.close()

    fut.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await fut

    assert counter == 1


@pytest.mark.asyncio
async def test_register_two_subscribers():
    sanic_app = Sanic()

    Sse(sanic_app)

    class Request:  # pylint: disable=too-few-public-methods
        args = {"channel_id": "1"}

    await sanic_app.router.routes_all["/sse"].handler(Request())

    with pytest.raises(InvalidUsage):
        await sanic_app.router.routes_all["/sse"].handler(Request())


@pytest.mark.asyncio
async def test_transport_closed():
    sanic_app = Sanic()

    sse = Sse(sanic_app)

    class Request:  # pylint: disable=too-few-public-methods
        args = {"channel_id": "1"}

    class Response:  # pylint: disable=too-few-public-methods
        @staticmethod
        def write(data):
            raise Exception

    str_response = await sanic_app.router.routes_all["/sse"].handler(Request())

    fut = asyncio.ensure_future(str_response.streaming_fn(Response()))

    await sanic_app.sse_send("test")  # pylint: disable=no-member

    fut.cancel()
    with contextlib.suppress(Exception):
        await fut

    assert sse._pubsub.size() == 0
