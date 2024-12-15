import logging

logger = logging.getLogger(__name__)


class DeviceConnectionError(Exception):
    ...


def exception_no_devices(func):
    """Simple function exception decorator"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AttributeError as e:
            logger.error(f"Scanner is not initialized!")

    return wrapper
