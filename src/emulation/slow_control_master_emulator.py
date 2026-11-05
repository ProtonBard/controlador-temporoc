
#
#
# +-----------------+
# | Slow    control |
# | master emulator |
# +-----------------+
#          |
#          |
# +-----------------+
# | Slow    control |
# | slave  emulator |
# +-----------------+
#
#

from src.emulation.slow_control_slave_emulator import SlowControlSlaveEmulator
from src.emulation.emulator_exceptions import UnknownSlowControlCommandError
from src.emulation.emulator_exceptions import ReadFifoUnderflowError
from src.emulation.emulator_exceptions import ReadCommandError

class SlowControlMasterEmulator () :

    def __init__ (self) -> None :
        self.slave = SlowControlSlaveEmulator()
        self.reset   : bool = True
        self.write   : bool = True
        self.ack     : bool = False
        self.end     : bool = True
        self.data_wr : bytes = b""
        self.data_rd : bytearray = bytearray()
        return

    def display (self) -> str :
        ret : str = ""
        ret += "("
        ret += f"(reset {self.reset:d})"
        ret += f"(write {self.write:d})"
        ret += f"(ack {self.ack:d})"
        ret += f"(end {self.end:d})"
        ret += ")"
        return ret

    def set_word_0 (self, data : int) -> None :
        self.reset = (data & 0b00000010) == 0
        self.update()
        return
    def get_word_4 (self) -> int :
        if self.end :
            return 1
        return 0
    def get_word_55 (self, size : int) -> bytes :
        assert isinstance(size, int)
        assert size > 0
        if self.reset or self.write or (len(self.data_rd) == 0) :
            raise ReadCommandError(f"{self.reset:d} {self.write:d} {len(self.data_rd)}")
        # this is a valid read
        if size > len(self.data_rd) :
            raise ReadFifoUnderflowError()
        ret = bytearray()
        for _ in range(0, size) :
            ret.append(self.data_rd[0])
            self.data_rd.pop(0)
            pass
        return bytes(ret)
    def set_word_56 (self, data : bytes) -> None :
        self.data_wr = data
        self.update()
        return
    def get_word_60 (self) -> int :
        word : int = 0b00000000
        if not self.write :
            word = word | 0b00000010
            pass
        if self.ack :
            word = word | 0b00000100
            pass
        return word
    def set_word_60 (self, data : int) -> None :
        self.write = (data & 0b00000010) == 0
        self.ack   = (data & 0b00000100) != 0
        self.update()
        return

    def update (self) -> None :
        if self.reset or (not self.write) or (len(self.data_wr) == 0) :
            # this is not a valid write
            return
        # this is a valid write
        assert (len(self.data_wr) % 4) == 0
        for i in range(0, len(self.data_wr) // 4) :
            if self.data_wr[i] == 0x01 :
                # this is a write
                self.slave.write(1, self.data_wr[i+1])
                self.slave.write(0, self.data_wr[i+2])
                self.slave.write(2, self.data_wr[i+3])
                pass
            elif self.data_wr[i] == 0x81 :
                self.slave.write(1, self.data_wr[i+1])
                self.slave.write(0, self.data_wr[i+2])
                self.data_rd.append(self.slave.read(2))
                pass
            else :
                raise UnknownSlowControlCommandError()
            pass
        self.data_wr = b""
        self.end     = True
        return

    pass




