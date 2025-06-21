from vkt_bot.bot_framework.bot.client import VkTeamsBot
from vkt_bot.bot_framework.dispatcher import Dispatcher
from vkt_bot.bot_framework.rabbitmq.broker import Broker
from vkt_bot.teams_bot.config import settings

bot = VkTeamsBot(settings.bot_token)
dispatcher = Dispatcher(bot=bot)
broker = Broker(url=settings.broker_url)
