import logging
import os
import sys

from opencensus.ext.azure.log_exporter import AzureLogHandler

from .constants import APP_INSIGHTS_KEY, LOG_LEVEL

log_level = os.getenv(LOG_LEVEL, logging.INFO)
insights_key = os.getenv(APP_INSIGHTS_KEY, "93689089-225d-4acb-b2ad-d4bec5599ff1")

# Create the AzureLogHandler and set the custom formatter
azure_handler = AzureLogHandler(
    connection_string=f"InstrumentationKey={insights_key}"
)
azure_handler.setFormatter(
    logging.Formatter(
        "%(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
    )
)

# Set up Azure logger separately for reusability
azure_logger = logging.getLogger("azure_logger")
azure_logger.setLevel(log_level)
azure_logger.addHandler(azure_handler)


def configure_logging(log_level=log_level, name=__name__):
    logger = logging.getLogger(name)

    # Clear any previously added handlers
    logger.handlers.clear()

    # Set the log level for the logger
    logger.setLevel(log_level)

    # Add the handlers to the logger
    system_handler = logging.StreamHandler(sys.stdout)
    system_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"
        )
    )

    logger.addHandler(system_handler)
    logger.addHandler(azure_handler)  # Reuse the previously configured Azure handler

    return logger


def set_logger(log_level=log_level, name=__name__):
    logger = configure_logging(log_level, name)
    return logger