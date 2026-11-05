import src.CONSTANTS
import time

class temperature_sensor:
    def __init__(self, dev):
        self.dev = dev

    def read_temperature(self):
        # Not possible to use the single shot mode
        # because the fw is continuously pulling for the temperature data stored in its own register

        # # write in configuration register
        # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_tmp_write, 1)  # select configuration register with pointer
        #
        # # measurement always running & the lowest precision
        # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_tmp_shift_in, 0b0000_0000)
        # # bit 7: enable single-shot
        # # bit 6/5: R1/R0 precision 0 = lowest precision
        # # bit 4/3: F1/F0
        # # bit 2: polarity of alert
        # # bit 1: comparator (1) or interrupt (0) mode
        # # bit 0: enable shut-down mode

        # read temperature on Temporoc board via I2C (TMP275AID U15)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_tmp_read, 0)  # select temperature register with pointer
        time.sleep(0.01)
        # Assuming 12 bits of data
        integer = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo)
        decimal = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo) >> 4
        # extra byte to pull ??? todo
        self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo)
        self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo)
        self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo)
        self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo)
        self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tmp_read_fifo)

        val = (integer << 4) + decimal

        sign = 1
        if (val & (1 << (12 - 1))) != 0:  # if sign bit is set
            val = 2 ** 12 - val
            sign = -1

        integer = val >> 4
        decimal = sign * (val & 0x00f) * 25 / 4 / 100

        return integer + decimal
