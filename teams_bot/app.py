from bot_framework.bot.client import VkTeamsBot
from bot_framework.dispatcher import Dispatcher
from bot_framework.rabbitmq.broker import Broker
from teams_bot.config import settings

bot = VkTeamsBot(settings.bot_token)
dispatcher = Dispatcher(bot=bot)
broker = Broker(url=settings.broker_url)
