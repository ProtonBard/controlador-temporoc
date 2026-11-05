import src.CONSTANTS


class pulser:
    def __init__(self, dev):
        self.dev = dev
        self.freq_Hz = 0
        self.delay_ns_until_resetn_latch = 0
        # be carefull : requires the PLL to output to the FPGA a 80 MHz on OUT3 !!!

    def set_divider(self, divider):
        assert divider >= 2
        assert divider <= 0xffff
        divider = divider - 1  # Minimum division is by 1
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_wstep_hi, (divider & 0xff00) >> 8)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_wstep_lo, divider & 0xff)
        self.launch()

    def set_frequency_in_Hz(self, freq_Hz):
        # will be multiple of 12.5 ns (a 80MHz clock period)

        assert freq_Hz <= 40e6
        assert freq_Hz > 80e6 // 0xffff

        ck_periods_at_80MHz_16bits = int(80e6 / freq_Hz)
        self.freq_Hz = int(80e6 / ck_periods_at_80MHz_16bits)
        print("Hit freq: %d Hz = %d x 80MHz ck periods" % (self.freq_Hz, ck_periods_at_80MHz_16bits))

        # correct for hardware offset   todo limit checks
        ck_periods_at_80MHz_16bits = ck_periods_at_80MHz_16bits - 1

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_wstep_hi, (ck_periods_at_80MHz_16bits & 0xff00) >> 8)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_wstep_lo, ck_periods_at_80MHz_16bits & 0xff)

        # validate
        self.launch()

    def set_period_in_ns(self, period_ns):
        # will be multiple of 12.5 ns (a 80MHz clock period)
        assert period_ns >= 25
        assert period_ns < 0xffff / 80e6 * 1e9
        ck_periods_at_80MHz_16bits = int(80e6 / 1e9 * period_ns)
        self.freq_Hz = int(80e6 / ck_periods_at_80MHz_16bits)
        print("Hit freq: %d Hz = %d x 80MHz ck periods" % (self.freq_Hz, ck_periods_at_80MHz_16bits))

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_wstep_hi, (ck_periods_at_80MHz_16bits & 0xff00) >> 8)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_wstep_lo, ck_periods_at_80MHz_16bits & 0xff)

    def disable_resetn_latch(self):
        # set delay so the reset is never send because out of time window
        self.set_reset_delay_in_ns(1 / self.freq_Hz * 1e9 + 12.5)

    def set_reset_delay_in_ns(self, delay_ns):
        # will be multiple of 12.5 ns (a 80MHz clock period)
        assert delay_ns >= 0
        assert delay_ns < 0xffff / 80e6 * 1e9
        ck_periods_at_80MHz_16bits = int(80e6 / 1e9 * delay_ns)
        self.delay_ns_until_resetn_latch = int(ck_periods_at_80MHz_16bits / 80e6 * 1e9)
        print("Reset delay %d ns" % self.delay_ns_until_resetn_latch)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_rstep_hi, (ck_periods_at_80MHz_16bits & 0xff00) >> 8)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_rstep_lo, ck_periods_at_80MHz_16bits & 0xff)

    def get_reset_delay_in_ns(self):
        return self.delay_ns_until_resetn_latch

    def get_frequency_in_Hz(self):
        return self.freq_Hz

    def mask_on_IO0(self):
        # FPGA IN DELAY forced to GND (control ext trigger)
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val & 0b1111_0111)

    def unmask_on_IO0(self):
        # FPGA IN DELAY free to transmit FPGA pulser to ext trigger
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val | 0x8)

    def set_async_feedthrough_mode(self):
        # divide by 2 feed through PLL clock (through FPGA)
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val & 0b1111_11110)

    def sync_enable_forever(self):
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val | 0x2)

    def sync_disable_forever(self):
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val & 0b1111_1101)

    def take_control_of_resetn_latch(self):
        # let the pulser control the state of resetn_latch, be aware that tpr_status_1 takes over the pulser on resetn_latch (logical and)
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val | (1 << 4))
        print("don't forget to enable bypass")

    def release_resetn_latch(self):
        # pull up to HIGH state
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val & 0b1110_1111)

    def set_sync_mode(self):
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val | 1)

    def mask_on_ext_trigger(self):
        # FPGA IN DELAY forced to GND (control ext trigger)
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val & 0b1111_1011)

    def unmask_on_ext_trigger(self):
        # FPGA IN DELAY free to transmit FPGA pulser to ext trigger
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val | 0x4)

    def set_nb_impulsions(self, N: int):
        isinstance(N, int)
        assert N < 2 ** 16
        assert N >= 0
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_pulse_lo, N & 0x00ff)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_pulse_hi, N >> 8)

    def get_nb_impulsions(self):
        return (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_pulse_hi) << 8) + self.dev.read_word(
            src.CONSTANTS.REGISTERS.addr_test_tdc_pulse_lo)

    def launch(self):
        self.disable()
        # time.sleep(0.1)
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val | (1 << 5))

    def disable(self):
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_config, val & 0b1101_1111)

