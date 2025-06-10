class BotException(Exception):
    """Base class for exceptions in this bot."""


class DataAgreementException(BotException):
    """Exception raised when there's an issue with data agreement handling."""


class FeedbackHandlingException(BotException):
    """Exception raised when there's an issue with feedback handling."""


class TokenException(BotException):
    """Exception raised when there's an issue with token handling."""


class DefaultInteractionException(BotException):
    """Exception raised for issues in default interaction handling."""


class InvalidVectorIndex(BotException):
    """Exception raised for issues in invalid vector index handling."""


class InvalidIncomingData(BotException):
    """Exception raised for issues in invalid incoming data handling."""


class PostgresException(BotException):
    """Exception raised for Postgres connection related"""


class StreamingResponseException(BotException):
    """Exception when streaming failed"""


class UserIndexError(BotException):
    """Exception when user access to index failed"""
