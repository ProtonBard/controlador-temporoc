

#
#
# +-----------------+
# |  FPGA emulator  |
# +-----------------+
#          |
#          |
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

from src.emulation.slow_control_master_emulator import SlowControlMasterEmulator
from src.emulation.emulator_exceptions import WordNotEmulatedError
from src.emulation.emulator_exceptions import WordNotWritableError
from src.emulation.emulator_exceptions import WordNotDefinedError

DUMMY_FIRMWARE_VERSION : int = 0x01

class FPGA () :

    def __init__ (self) -> None :
        self.slow_control = SlowControlMasterEmulator()
        self.request_word : int       = 0
        self.request_data : bytearray = bytearray()
        self.word_0  : int   = 0
        self.word_1  : int   = 0
        self.word_2  : int   = 0
        return

    def write_command (self, word : int, data : bytes) -> None :
        assert isinstance(word, int)
        assert isinstance(data, bytes)
        match word :
            case   0 : assert len(data) == 1; self.word_0 = data[0]; self.slow_control.set_word_0(self.word_0); return
            case   1 : assert len(data) == 1; self.word_1 = data[0]; return
            case   2 : assert len(data) == 1; self.word_2 = data[0]; return
            case   4 : raise WordNotWritableError()
            case   6 : raise WordNotEmulatedError()
            case   7 : raise WordNotEmulatedError()
            case   8 : raise WordNotWritableError()
            case   9 : raise WordNotWritableError()
            case  18 : raise WordNotWritableError()
            case  19 : raise WordNotWritableError()
            case  20 : raise WordNotEmulatedError()
            case  21 : raise WordNotEmulatedError()
            case  22 : raise WordNotWritableError()
            case  24 : raise WordNotEmulatedError()
            case  25 : raise WordNotWritableError()
            case  26 : raise WordNotWritableError()
            case  27 : raise WordNotWritableError()
            case  28 : raise WordNotWritableError()
            case  30 : raise WordNotEmulatedError()
            case  31 : raise WordNotEmulatedError()
            case  32 : raise WordNotEmulatedError()
            case  33 : raise WordNotEmulatedError()
            case  34 : raise WordNotWritableError()
            case  35 : raise WordNotWritableError()
            case  36 : raise WordNotWritableError()
            case  37 : raise WordNotWritableError()
            case  38 : raise WordNotEmulatedError()
            case  39 : raise WordNotWritableError()
            case  40 : raise WordNotWritableError()
            case  41 : raise WordNotWritableError()
            case  42 : raise WordNotWritableError()
            case  43 : raise WordNotWritableError()
            case  44 : raise WordNotWritableError()
            case  45 : raise WordNotWritableError()
            case  46 : raise WordNotWritableError()
            case  55 : raise WordNotWritableError()
            case  56 : self.slow_control.set_word_56(data); return
            case  57 : raise WordNotEmulatedError()
            case  58 : raise WordNotEmulatedError()
            case  59 : raise WordNotEmulatedError()
            case  60 : assert len(data) == 1; self.slow_control.set_word_60(data[0]); return
            case  61 : raise WordNotEmulatedError()
            case  69 : raise WordNotEmulatedError()
            case  70 : raise WordNotWritableError()
            case  71 : raise WordNotWritableError()
            case  72 : raise WordNotWritableError()
            case  73 : raise WordNotEmulatedError()
            case 100 : raise WordNotWritableError()
            case   _ : raise WordNotDefinedError()
        return

    def read_request (self, word : int, size : int) -> None :
        assert isinstance(word, int)
        assert isinstance(size, int)
        self.request_word = word
        match word :
            case   0 : self.request_data = bytearray([self.word_0])
            case   1 : self.request_data = bytearray([self.word_1])
            case   2 : self.request_data = bytearray([self.word_2])
            case   4 : self.request_data = bytearray([self.slow_control.get_word_4()])
            case   6 : raise WordNotEmulatedError()
            case   7 : raise WordNotEmulatedError()
            case   8 : raise WordNotEmulatedError()
            case   9 : raise WordNotEmulatedError()
            case  18 : raise WordNotEmulatedError()
            case  19 : raise WordNotEmulatedError()
            case  20 : raise WordNotEmulatedError()
            case  21 : raise WordNotEmulatedError()
            case  22 : raise WordNotEmulatedError()
            case  24 : raise WordNotEmulatedError()
            case  25 : raise WordNotEmulatedError()
            case  26 : raise WordNotEmulatedError()
            case  27 : raise WordNotEmulatedError()
            case  28 : raise WordNotEmulatedError()
            case  30 : raise WordNotEmulatedError()
            case  31 : raise WordNotEmulatedError()
            case  32 : raise WordNotEmulatedError()
            case  33 : raise WordNotEmulatedError()
            case  34 : raise WordNotEmulatedError()
            case  35 : raise WordNotEmulatedError()
            case  36 : raise WordNotEmulatedError()
            case  37 : raise WordNotEmulatedError()
            case  38 : raise WordNotEmulatedError()
            case  39 : raise WordNotEmulatedError()
            case  40 : raise WordNotEmulatedError()
            case  41 : raise WordNotEmulatedError()
            case  42 : raise WordNotEmulatedError()
            case  43 : raise WordNotEmulatedError()
            case  44 : raise WordNotEmulatedError()
            case  45 : raise WordNotEmulatedError()
            case  46 : raise WordNotEmulatedError()
            case  55 : self.request_data = bytearray(self.slow_control.get_word_55(size))
            case  56 : raise WordNotEmulatedError()
            case  57 : raise WordNotEmulatedError()
            case  58 : raise WordNotEmulatedError()
            case  59 : raise WordNotEmulatedError()
            case  60 : self.request_data = bytearray([self.slow_control.get_word_60()])
            case  61 : raise WordNotEmulatedError()
            case  69 : raise WordNotEmulatedError()
            case  70 : raise WordNotEmulatedError()
            case  71 : raise WordNotEmulatedError()
            case  72 : raise WordNotEmulatedError()
            case  73 : raise WordNotEmulatedError()
            case 100 : self.request_data = bytearray([DUMMY_FIRMWARE_VERSION])
            case   _ : raise WordNotDefinedError()
        return

    def get_read_word (self) -> int :
        return self.request_word

    def get_read_data (self) -> bytearray :
        return self.request_data

    pass

