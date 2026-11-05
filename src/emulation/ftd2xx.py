

#
#
# +-----------------+
# |     ftd2xx      |
# |    emulator     |
# +-----------------+
#          |
#          |
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

from typing import Optional, List

import src.emulation.fpga

# pylint: disable=invalid-name
# The names are formatted like that for compatibility with the real library.

HEADER_INT : int = 170
FOOTER_INT : int = 85

class Device:

    def __init__ (self, serial : bytes) -> None :
        assert isinstance(serial, bytes)
        self.fpga   = src.emulation.fpga.fpga()
        self.serial = serial
        return

    def getDeviceInfo (self) :
        return

    def setUSBParameters (self, arg1 : int, arg2 : int) :
        assert isinstance(arg1, int)
        assert isinstance(arg2, int)
        return

    def setTimeouts (self, arg1 : int, arg2 : int) :
        assert isinstance(arg1, int)
        assert isinstance(arg2, int)
        return

    def setLatencyTimer (self, arg : int) :
        assert isinstance(arg, int)
        return

    def getEventStatus (self) -> int :
        return 0

    def write (self, pack : bytes) -> int :
        assert isinstance(pack, bytes)
        assert len(pack) > 4
        assert pack[ 0] == HEADER_INT
        assert pack[-1] == FOOTER_INT
        direction_bit : int = pack[2] & 0b10000000
        word : int = pack[2] & 0b01111111
        if direction_bit == 0 :
            # write command
            assert pack[1] + 5 == len(pack)
            self.fpga.write_command(word, pack[3:-1])
            pass
        else :
            # read request
            lsb_part = pack[1]
            msb_part = pack[3] << 8
            size = (msb_part | lsb_part) + 1
            self.fpga.read_request(word, size)
            pass
        return len(pack)

    def read (self, size : int) -> bytes :
        assert isinstance(size, int)
        ret = bytearray()
        read_word : int   = self.fpga.get_read_word()
        read_data : bytes = self.fpga.get_read_data()
        ret.append(0xaa)      # header
        ret.append(0x00)      # msb of size - unused
        ret.append(read_word) # subaddress
        ret.extend(read_data) # data
        ret.append(0x55)      # trailer
        return bytes(ret)

    pass

devices : List[Device] = []
devices.append(Device(b"GARBAGE"))
devices.append(Device(b"RD3_02A"))
devices.append(Device(b"FAKEDEV"))
devices.append(Device(b"RD3_02B"))

def createDeviceInfoList () -> int :
    return len(devices)

def listDevices () -> Optional[List[bytes]] :
    serials = []
    for i in range(0, len(devices)) :
        serials.append(devices[i].serial)
        pass
    return serials

def openEx (id_str : bytes) -> Device :
    for i in range(0, len(devices)) :
        if id_str == devices[i].serial :
            return devices[i]
        pass
    assert False
    return None



