
#
# Interface to read or write to slow control registers.
# Wraps communication with the ftdi interface in matters regarding
# slow control configuration.
#
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

import uiroc

class CommunicationTimeoutError (Exception) :
    pass

TIMEOUT : int = 1000

def wait_until_done_or_timeout (ftdi : uiroc.device.FtdInterface) -> bool :
    for _ in range(0, TIMEOUT) :
        add4 = ftdi.read_word(4)
        flag = add4 & 0x01
        if flag != 0 :
            return True
        pass
    return False

def write_register (ftdi : uiroc.device.FtdInterface, add : int, subadd : int, data : int) -> None :
    assert isinstance(ftdi,   uiroc.device.FtdInterface)
    assert isinstance(add,    int)
    assert isinstance(subadd, int)
    assert isinstance(data,   int)
    #initialize w60
    ftdi.write_word(60, 0x00)
    #enable I2C clock
    add0 = ftdi.read_word(0)
    add0 = add0 | 0b01000000
    ftdi.write_word(0, add0)
    #
    i2c_data = b'\x01' +\
               add.to_bytes(1, byteorder='little') +\
               subadd.to_bytes(1, byteorder='little') +\
               data.to_bytes(1, byteorder='little')
    ftdi.write_words(56, i2c_data, len(i2c_data))
    ftdi.write_word(60, 0b00000010)
    #
    done = wait_until_done_or_timeout(ftdi)
    #disable i2c clock
    add0 = add0 & 0b10111111
    ftdi.write_word(0, add0)
    if not done :
        raise CommunicationTimeoutError()
    return


def read_register (ftdi : uiroc.device.FtdInterface, add : int, subadd : int) -> int :
    # initialize w60
    ftdi.write_word(60, 0x00)
    # enable I2C clock
    add0 = ftdi.read_word(0)
    add0 = add0 | 0b01000000
    ftdi.write_word(0, add0)
    #
    i2c_data = b'\x81' +\
               add.to_bytes(1, byteorder='little') +\
               subadd.to_bytes(1, byteorder='little') +\
               b'\x00'
    ftdi.write_words(56, i2c_data, len(i2c_data))
    ftdi.write_word(60, 0b00000010)
    #
    done = wait_until_done_or_timeout(ftdi)
    #
    if done :
        result = ftdi.read_word(55)
        pass
    #data software OK
    ftdi.write_word(60, 0b00000100)
    #disable i2c clock
    add0 = add0 & 0b10111111
    ftdi.write_word(0, add0)
    if not done :
        raise CommunicationTimeoutError()
    return result



