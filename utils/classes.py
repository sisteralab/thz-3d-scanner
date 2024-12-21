class InstrumentAdapterInterface:
    """
    This is the base interface for Instrument adapter
    """

    def _send(self, *args, **kwargs):
        raise NotImplementedError

    def _recv(self, *args, **kwargs):
        raise NotImplementedError

    def read(self, *args, **kwargs):
        raise NotImplementedError

    def query(self, *args, **kwargs):
        raise NotImplementedError

    def write(self, *args, **kwargs):
        raise NotImplementedError

    def connect(self, *args, **kwargs):
        raise NotImplementedError

    def close(self, *args, **kwargs):
        raise NotImplementedError


class BaseInstrument:
    def query(self, cmd: str, **kwargs) -> str:
        return self.adapter.query(cmd, **kwargs)

    def write(self, cmd: str) -> None:
        return self.adapter.write(cmd)


class PrologixMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        host = kwargs.get("host", None)
        if not host:
            host = args[0]  # FIXME: improve later
        if host not in cls._instances:
            cls._instances[host] = super(PrologixMeta, cls).__call__(*args, **kwargs)
        return cls._instances[host]
