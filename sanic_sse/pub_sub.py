"""PubSub module

This module contains PubSub class that implement publish/subscriber protocol
"""

import asyncio
import uuid
from collections import defaultdict
from typing import Dict


class _StopMessage:  # pylint: disable=too-few-public-methods
    pass


class PubSub:
    """
    Implementation of publish/subscriber protocol
    """

    def __init__(self):
        self._channels = defaultdict(dict)

    def publish(self, data: str, channel_id: str = None):
        """
        Publish data to all subscribers or to channel with provided channel_id.
        This call is blocking.

        :param str data: The data to publush
        :param str channel_id: If given then data will be send only to channel with that id
        """

        return asyncio.gather(
            *[client.put(data) for client in self._channels[channel_id].values()]
        )

    def register(self, channel_id: str = None):
        """
        Register new subscriber

        Return identifier of subscriber (str)
        """

        client_id = str(uuid.uuid4())
        q = asyncio.Queue()

        self._channels[channel_id][client_id] = q
        if channel_id:
            self._channels[None][client_id] = q

        return client_id

    def delete(self, client_id: str, channel_id: str = None):
        """
        Delete subscriber by given channel_id

        :param str client_id: Identifier of client
        :param str channel_id: Identifier of channel
        """
        try:
            del self._channels[channel_id][client_id]
            if len(self._channels[channel_id]) == 0:
                del self._channels[channel_id]
            if channel_id:
                del self._channels[None][client_id]
        except KeyError:
            return False

        return True

    async def get(self, client_id: str, channel_id: str = None):
        """
        Return data for given subscriber. This call is blocking.

        :param str client_id: Identifier of client
        :param str channel_id: Identifier of channel

        Return received data (str)
        """

        data = await self._channels[channel_id][client_id].get()
        if isinstance(data, _StopMessage):
            self.delete(client_id, channel_id)
            raise ValueError("Stop message received")

        return data

    def task_done(self, client_id: str, channel_id: str = None):
        """
        Notify that current data was processed

        :param str client_id: Identifier of client
        :param str channel_id: Identifier of channel
        """
        self._channels[channel_id][client_id].task_done()

    async def close(self):
        """
        Close all subscribers
        """
        await self.publish(_StopMessage())
