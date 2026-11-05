from src.FPGA import shared_IO_FPGA_selector
import src.CONSTANTS


class external_ADC:
    def __init__(self, dev):
        self.dev = dev
        self.select_trigger = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_trigger_adc, None, None)

    def set_delay_before_trigger(self, delay_8b):
        # multiple of 50 MHz
        assert delay_8b >= 0
        assert delay_8b < 2 ** 8
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_adc_tdelay, delay_8b)

    def launch_n_read(self):
        # 2 acquisitions in a row to get first value : no need in new fw
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_adc_status,
                            1)  # launch acquisition and fetch previous acquisition
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_adc_status, 0)
        # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_adc_status, 1)  # launch acquisition and fetch previous acquisition
        # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_adc_status, 0)
        # self.dev.read_word(src.CONSTANTS.REGISTERS.addr_adc_status)
        HG = (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_adc_d1_high) << 8) + self.dev.read_word(
            src.CONSTANTS.REGISTERS.addr_adc_d1_low)
        LG = (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_adc_d0_high) << 8) + self.dev.read_word(
            src.CONSTANTS.REGISTERS.addr_adc_d0_low)
        return LG, HG

    def read_LG(self):
        return (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_adc_d0_high) << 8) + self.dev.read_word(
            src.CONSTANTS.REGISTERS.addr_adc_d0_low)

    def read_HG(self):
        return (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_adc_d1_high) << 8) + self.dev.read_word(
            src.CONSTANTS.REGISTERS.addr_adc_d1_low)
