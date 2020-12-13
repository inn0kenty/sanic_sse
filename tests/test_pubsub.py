# pylint: disable=missing-docstring, protected-access

import asyncio
import pytest
from sanic_sse.pub_sub import PubSub


def test_pubsub_register_and_unregister():
    pubsub = PubSub()

    client_id = pubsub.register()

    assert len(pubsub._channels[None]) == 1
    assert isinstance(client_id, str)

    client_id2 = pubsub.register()

    assert len(pubsub._channels[None]) == 2

    assert client_id != client_id2

    pubsub.delete(client_id)
    assert client_id not in pubsub._channels[None]
    assert len(pubsub._channels[None]) == 1

    pubsub.delete(client_id2)

    assert client_id2 not in pubsub._channels[None]


@pytest.mark.asyncio
async def test_publish_subscribing():
    pubsub = PubSub()

    data = "some_data"
    channel_id1 = pubsub.register()
    channel_id2 = pubsub.register()

    await pubsub.publish(data)

    async def handel(channel_id):
        data1 = await pubsub.get(channel_id)
        assert data1 == data
        pubsub.task_done(channel_id)

    await asyncio.gather(*[handel(_) for _ in [channel_id1, channel_id2]])


@pytest.mark.asyncio
async def test_publish_nowait():
    pubsub = PubSub()

    data = "some_data"
    channel_id1 = pubsub.register()
    channel_id2 = pubsub.register()

    pubsub.publish(data)

    async def handel(channel_id):
        data1 = await pubsub.get(channel_id)
        assert data1 == data
        pubsub.task_done(channel_id)

    await asyncio.gather(*[handel(_) for _ in [channel_id1, channel_id2]])


@pytest.mark.asyncio
async def test_stop():
    pubsub = PubSub()

    channel_id = pubsub.register()

    await pubsub.close()

    with pytest.raises(ValueError):
        await pubsub.get(channel_id)


@pytest.mark.asyncio
async def test_publish_to_channel():
    pubsub = PubSub()

    client_id1 = pubsub.register("1")
    client_id2 = pubsub.register("2")

    data = "test data"

    await pubsub.publish(data, "1")

    assert not pubsub._channels["1"][client_id1].empty()
    assert pubsub._channels["2"][client_id2].empty()

    await pubsub.get(client_id1)

    await pubsub.publish(data, "2")

    assert pubsub._channels["1"][client_id1].empty()
    assert not pubsub._channels["2"][client_id2].empty()

    await pubsub.get(client_id2)

    await pubsub.publish(data)

    assert not pubsub._channels["1"][client_id1].empty()
    assert not pubsub._channels["2"][client_id2].empty()
