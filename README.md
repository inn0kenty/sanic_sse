# Sanic Server-Sent Events extension

A Sanic extension for HTML5 [server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) support, inspired by [flask-sse](https://github.com/singingwolfboy/flask-sse) and [aiohttp-sse](https://github.com/aio-libs/aiohttp-sse).

## Install

Installation process as simple as:

```bash
$ pip install sanic_sse
```

## Example

Server example:

```python
from http import HTTPStatus
from sanic import Sanic
from sanic.response import json, json_dumps
from sanic.exceptions import abort
from sanic_sse import Sse

# This function is optional callback before sse request
# You can use it for authorization purpose or something else
async def before_sse_request(request):
    if request.headers.get("Auth", "") != "some_token":
        abort(HTTPStatus.UNAUTHORIZED, "Bad auth token")


sanic_app = Sanic()

# The default sse url is /sse but you can set it via init argument url.
Sse(
    sanic_app, url="/events", before_request_func=before_sse_request
)  # or you can use init_app method


@sanic_app.route("/send", methods=["POST"])
async def send_event(request):
    # if channel_id is None than event will be send to all subscribers
    channel_id = request.json.get("channel_id")

    # optional arguments: event_id - str, event - str, retry - int
    # data should always be str
    # also you can use sse_send_nowait for send event without waiting
    try:
        await request.app.sse_send(json_dumps(request.json), channel_id=channel_id)
    except KeyError:
        abort(HTTPStatus.NOT_FOUND, "channel not found")

    return json({"status": "ok"})


if __name__ == "__main__":
    sanic_app.run(host="0.0.0.0", port=8000)
```

Client example (powered by [sseclient-py](https://github.com/mpetazzoni/sseclient) and [requests](https://github.com/requests/requests)):

```python
import json
import pprint
import requests
import sseclient

url = "http://127.0.0.1:8000/events"
# you may set channel_id parameter to receive special events
# url = "http://127.0.0.1:8000/events?channel_id=foo"

response = requests.get(url, stream=True)
client = sseclient.SSEClient(response)
for event in client.events():
    print(event.id)
    print(event.event)
    print(event.retry)
    pprint.pprint(json.loads(event.data))
```

## Requirements

- [python](https://www.python.org/) 3.5+
- [sanic](https://github.com/channelcat/sanic) 0.7.0+
