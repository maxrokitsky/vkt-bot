from vkt_bot.config import settings
from vkteams_client import VKTeams
from vkt_dispatcher import Dispatcher


bot = VKTeams(settings.bot_token)
dispatcher = Dispatcher(bot=bot)
