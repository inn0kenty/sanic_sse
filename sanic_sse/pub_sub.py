"""PubSub module

This module contains PubSub class that implement publish/subscriber protocol
"""

import asyncio
import uuid
from typing import Dict


class _StopMessage:  # pylint: disable=too-few-public-methods
    pass


class PubSub:
    """
    Implementation of publish/subscriber protocol
    """

    def __init__(self):
        self._channels: Dict[str, asyncio.Queue] = {}

    def publish_nowait(self, data: str, channel_id: str = None):
        """
        Publish data to all subscribers or to channel with provided channel_id.
        This call is not blocking.

        :param str data: The data to publush
        :param str channel_id: If given then data will be send only to channel with that id
        """

        if channel_id is not None:
            self._channels[channel_id].put_nowait(data)
        else:
            asyncio.gather(*[channel.put(data) for channel in self._channels.values()])

    async def publish(self, data: str, channel_id: str = None):
        """
        Publish data to all subscribers or to channel with provided channel_id.
        This call is blocking.

        :param str data: The data to publush
        :param str channel_id: If given then data will be send only to channel with that id
        """

        if channel_id is not None:
            await self._channels[channel_id].put(data)
        else:
            await asyncio.gather(
                *[channel.put(data) for channel in self._channels.values()]
            )

    def register(self, channel_id: str = None):
        """
        Register new subscriber

        Return identifier of subscriber (str)
        """
        if channel_id is None:
            channel_id = str(uuid.uuid4())

        if channel_id in self._channels:
            raise ValueError(f"Given channel id {channel_id} is already in use")
        self._channels[channel_id] = asyncio.Queue()

        return channel_id

    def delete(self, channel_id: str):
        """
        Delete subscriber by given channel_id

        :param str channel_id: Identifier of subscriber
        """
        try:
            del self._channels[channel_id]
        except KeyError:
            return False

        return True

    async def get(self, channel_id: str):
        """
        Return data for given subscriber. This call is blocking.

        :param str channel_id: Identifier of subscriber

        Return received data (str)
        """

        data = await self._channels[channel_id].get()
        if isinstance(data, _StopMessage):
            self.delete(channel_id)
            raise ValueError("Stop message received")

        return data

    def task_done(self, channel_id):
        """
        Notify that current data was processed

        :param str channel_id: Identifier of subscriber
        """
        self._channels[channel_id].task_done()

    async def close(self):
        """
        Close all subscribers
        """
        await self.publish(_StopMessage())

    def size(self):
        """
        Return count of subscribers
        """
        return len(self._channels)
