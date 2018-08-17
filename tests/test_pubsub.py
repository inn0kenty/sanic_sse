# pylint: disable=missing-docstring, protected-access

import asyncio
import pytest
from sanic_sse.pub_sub import PubSub


def test_pubsub_create():
    pubsub = PubSub()

    assert pubsub.size() == 0


def test_pubsub_register_and_unregister():
    pubsub = PubSub()

    channel_id = pubsub.register()

    assert pubsub.size() == 1
    assert isinstance(channel_id, str)

    channel_id2 = pubsub.register()

    assert pubsub.size() == 2

    assert channel_id != channel_id2

    pubsub.delete(channel_id)
    assert channel_id not in pubsub._channels
    assert pubsub.size() == 1

    pubsub.delete(channel_id2)

    assert channel_id2 not in pubsub._channels


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

    pubsub.publish_nowait(data)

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


def test_already_reg():
    pubsub = PubSub()

    channel_id = pubsub.register("1")
    assert channel_id == "1"

    with pytest.raises(ValueError):
        pubsub.register("1")


@pytest.mark.asyncio
async def test_publish_to_channel():
    pubsub = PubSub()

    channel_id1 = pubsub.register("1")
    channel_id2 = pubsub.register("2")

    data = "test data"

    await pubsub.publish(data, channel_id=channel_id1)

    assert not pubsub._channels[channel_id1].empty()
    assert pubsub._channels[channel_id2].empty()

    await pubsub.get(channel_id1)

    await pubsub.publish(data, channel_id=channel_id2)

    assert pubsub._channels[channel_id1].empty()
    assert not pubsub._channels[channel_id2].empty()

    await pubsub.get(channel_id2)

    await pubsub.publish(data)

    assert not pubsub._channels[channel_id1].empty()
    assert not pubsub._channels[channel_id2].empty()
