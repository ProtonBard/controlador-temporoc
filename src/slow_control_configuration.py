
#
#
# +---------------+
# | Slow  control |
# | configuration |
# +---------------+
#         |
#         |
# +---------------+
# | Slow  control |
# |   interface   |
# +---------------+
#         |
#         |
# +-----------------------------------+
# |           Ftdi interface          |
# +-----------------------------------+
#                   |
#                  emu?
#                  y  n
#                 /    \
#                /      \
#               /        \
#              /          \
#             /            \
#            /              \
#           /                \
# +-----------------+ +---------------+
# |     ftd2xx      | |     ftd2xx    |
# |    emulator     | |               |
# +-----------------+ +---------------+
#          |                  |
#          |                  |
# +-----------------+ +---------------+
# |  FPGA emulator  | |               |
# +-----------------+ |               |
#          |          |               |
#          |          |     FPGA      |
# +-----------------+ |               |
# | Slow    control | |               |
# | master emulator | |               |
# +-----------------+ +---------------+
#          |                  |
#          |                  |
# +-----------------+ +---------------+
# | Slow    control | |     ASIC      |
# | slave  emulator | |               |
# +-----------------+ +---------------+
#
#

import slow_control_interface
import uiroc
from slow_control_registers import SlowControlRegisters

class BitManipulationError (Exception) :
    pass

class TransmissionError (Exception) :
    pass

class RegisterLocation () :

    def __init__ (self, address : int, subaddress : int, width : int, index : int) -> None :
        assert isinstance(address,    int)
        assert isinstance(subaddress, int)
        assert isinstance(width,      int)
        assert isinstance(index,      int)
        assert address    >=   0
        assert address    <  256
        assert subaddress >=   0
        assert subaddress <  256
        assert width      >=   1
        assert width      <=   8
        assert index      >=   0
        assert index      <    8
        assert (index + width) <= 8
        self.address    = address
        self.subaddress = subaddress
        self.width      = width
        self.index      = index
        return

    def assert_valid (self) -> None :
        assert isinstance(self.address,    int)
        assert isinstance(self.subaddress, int)
        assert isinstance(self.width,      int)
        assert isinstance(self.index,      int)
        assert self.address    >=   0
        assert self.address    <  256
        assert self.subaddress >=   0
        assert self.subaddress <  256
        assert self.width      >=   1
        assert self.width      <=   8
        assert self.index      >=   0
        assert self.index      <    8
        assert (self.index + self.width) <= 8
        return

    def get_mask (self) -> int :
        self.assert_valid()
        mask : int = 0
        match self.width :
            case 0 : raise BitManipulationError("Zero size integer are not valid.")
            case 1 : mask = 0x01
            case 2 : mask = 0x03
            case 3 : mask = 0x07
            case 4 : mask = 0x0F
            case 5 : mask = 0x1F
            case 6 : mask = 0x3F
            case 7 : mask = 0x7F
            case 8 : mask = 0xFF
            case _ : raise BitManipulationError("Fied may not be larger than an octet.")
        smask : int = mask << self.index
        return smask

    pass

class RegisterData () :

    def __init__ (self, address : int, subaddress : int, width : int, index : int, data : int) -> None :
        assert isinstance(data, int)
        assert data >=   0
        assert data <  256
        self.loc  = RegisterLocation(address, subaddress, width, index)
        self.data = data
        return

    def assert_valid (self) -> None :
        assert isinstance(self.data, int)
        self.loc.assert_valid()
        assert self.data >=   0
        assert self.data <  256
        return

    pass

class SlowControlConfiguration () :

    def __init__ (self, ftdi : uiroc.device.FtdInterface) -> None :
        self.ftdi = ftdi
        self.registers = SlowControlRegisters()
        return

    def comm_tx (self, rd : RegisterData) -> None :
        assert isinstance(rd, RegisterData)
        rd.assert_valid()
        data_expected : int = self.internal_shift_in(rd)
        slow_control_interface.write_register(self.ftdi, rd.loc.address, rd.loc.subaddress, data_expected)
        data_received : int = slow_control_interface.read_register(self.ftdi, rd.loc.address, rd.loc.subaddress)
        if data_received == data_expected :
            self.registers.set(rd.loc.address, rd.loc.subaddress, data_expected)
            return
        raise TransmissionError(f"Wrote {hex(data_expected)}, but read {hex(data_received)}.")

    def comm_rx (self, rl : RegisterLocation) -> int :
        assert isinstance(rl, RegisterLocation)
        rl.assert_valid()
        data_received : int = slow_control_interface.read_register(self.ftdi, rl.address, rl.subaddress)
        self.registers.set(rl.address, rl.subaddress, data_received)
        return self.internal_shift_out(rl)

    def internal_shift_out (self, rl : RegisterLocation) -> int :
        assert isinstance(rl, RegisterLocation)
        rl.assert_valid()
        data_raw     : int = self.registers.get(rl.address, rl.subaddress)
        data_masked  : int = data_raw & rl.get_mask()
        data_shifted : int = data_masked >> rl.index
        return data_shifted

    def internal_shift_in (self, rd : RegisterData) -> int :
        assert isinstance(rd, RegisterData)
        rd.assert_valid()
        mask_positive : int = rd.loc.get_mask()
        mask_negative : int = mask_positive ^ 0xff
        data_shifted  : int = rd.data << rd.loc.index
        data_partial  : int = self.registers.get(rd.loc.address, rd.loc.subaddress) & mask_negative
        data_full     : int = data_partial | data_shifted
        return data_full

    pass

