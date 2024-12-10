from api.commands import Commands
from api.vna import VNABlock


class State:
    measure_running = False
    monitor_running = False
    d3: Commands = None
    vna: VNABlock = None

    @classmethod
    def init_d3(cls):
        cls.d3 = Commands()
        cls.d3.connect_devices()
        cls.d3.set_units()

    @classmethod
    def init_vna(cls):
        cls.vna = VNABlock()

    @classmethod
    def del_d3(cls):
        cls.d3.disconnect_devices()
        del cls.d3

    @classmethod
    def del_vna(cls):
        del cls.vna

