import src.CONSTANTS


class external_DAC:
    def __init__(self, dev):
        self.dev = dev

    def set_dac_VinP(self, dac_value_12b):
        # DAC 1 = DAC A = VinP
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_enable, 0)  # write configuration

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_d1_high, (dac_value_12b & 0xf00)>>8)  # msb
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_d1_low, dac_value_12b & 0xff)  # lsb

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_enable, 1)  # write configuration
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_enable, 0)

    def set_dac_VinN(self, dac_value_12b):
        # DAC 2 = DAC B = VinN
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_enable, 0)  # write configuration

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_d2_high, (dac_value_12b & 0xf00)>>8)  # msb
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_d2_low, dac_value_12b & 0xff)  # lsb

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_enable, 1)  # write configuration
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_dac_enable, 0)
