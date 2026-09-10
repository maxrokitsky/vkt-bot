import structlog

main_logger = structlog.get_logger("vkteams_client")
api_logger = structlog.get_logger("vkteams_client.api")
events_logger = structlog.get_logger("vkteams_client.events")
send_message_logger = structlog.get_logger("vkteams_client.send_message")
