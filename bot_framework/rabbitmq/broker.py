from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from teams_bot.config import settings


class Broker:
    connection: AbstractRobustConnection

    def __init__(self, url: str) -> None:
        self.url = url
        self.queue_name = "test_queue"
        self.routing_key = "test_queue"

    async def connect(self) -> None:
        self.connection = await connect_robust(settings.broker_url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange("direct", auto_delete=True)
        self.queue = await self.channel.declare_queue(self.queue_name, exclusive=True)
        await self.queue.bind(self.exchange, self.routing_key)

    async def close(self) -> None:
        await self.connection.close()

    async def execute(self) -> AbstractIncomingMessage:
        await self.exchange.publish(
            Message(
                bytes("Hello", "utf-8"),
                content_type="text/plain",
                headers={"foo": "bar"},
            ),
            self.routing_key,
        )

        # Receiving message
        incoming_message = await self.queue.get(timeout=5)
        await incoming_message.ack()
        return incoming_message
