import logging


logger = logging.getLogger("groundedagent")


def init_app_insights(connection_string: str | None) -> bool:
    """Enable Azure Monitor/OpenTelemetry export when connection string is present.

    Returns True when configured successfully, otherwise False.
    """
    if not connection_string:
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        logger.info("app_insights_enabled")
        return True
    except Exception as exc:
        logger.warning(f"app_insights_init_failed: {exc}")
        return False
