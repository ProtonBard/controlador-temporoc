import datetime
import time

import numpy as np

import src.CONSTANTS
from src.pulser import pulser


# FPGA class factory
# # TODO: Customize the FPGA class to your needs
# def construct_FPGA(type=None):
#     if type == 'single':
#         class FPGA(FPGA_base, FPGA_PLL):
#             def __init__(self, dev, asic_list, FPGA_PLL):
#                 super().__init__(dev, asic_list, FPGA_PLL)
#         return FPGA
#     elif type == 'dual':
#         class FPGA(FPGA_base):
#             def __init__(self, dev, asic_list, FPGA_PLL):
#                 super().__init__(dev, asic_list, FPGA_PLL)
#         return FPGA
#     else:
#         raise ValueError("Unknown FPGA type. Only single-asic and dual-asic are supported.")


class FPGA_base:
    def __init__(self, dev, asic_list, FPGA_PLL):
        self.dev = dev
        self.OUT1 = self.__1(dev)
        self.OUT2_select = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_control_io_2,
                                                   src.CONSTANTS.REGISTERS.addr_sma_control, 2, asic_list)
        self.OUT3_select = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_control_io_3,
                                                   src.CONSTANTS.REGISTERS.addr_sma_control, 3, asic_list)
        self.OUT4_select = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_control_io_4,
                                                   src.CONSTANTS.REGISTERS.addr_sma_control, 4, asic_list)
        self.OUT5 = self.__5(dev)
        self.OUT6_select = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_control_io_6,
                                                   src.CONSTANTS.REGISTERS.addr_sma_control, 6, asic_list)
        self.OUT7_select = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_control_io_7,
                                                   src.CONSTANTS.REGISTERS.addr_sma_control, 7, asic_list)

        self.select = self.__select(dev, FPGA_PLL)
        self.pulser = pulser(dev)

        # ASIC signals controlled by FPGA ! 
        self.get = self.__get(dev)
        self.set = self.__set(dev)
        self.reset = self.__reset(dev, self.set, asic_list)


    def disable_foreign_reset_enable(self):
        word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word & ~(1 << 5))

    def enable_foreign_reset_enable(self):
        word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word | (1 << 5))

    def test_read_write_FPGA_reg(self):
        # all bits should be set to 1 then 0 and checked
        register_tested = src.CONSTANTS.REGISTERS.addr_read_reg_iter
        for val in [255, 0]:
            self.dev.write_word(register_tested, val)
            read_val = self.dev.read_word(register_tested)
            if read_val!=val:
                print("USB communication error likely due to firmware generation error")
                print("From register addr_read_reg_iter %d: read_val 0x%x or %s != written 0x%x or %s"%
                      (register_tested, val, bin(val), read_val, bin(read_val)))
                exit(0)

    class __get:
        def __init__(self, dev):
            self.dev = dev

        def chipid(self):
            return self.dev.read_word(src.CONSTANTS.REGISTERS.addr_chip_id)

        def __get_fpga_config_reg(self, config_reg, bit_offset):
            return ((self.dev.read_word(config_reg)) & (1 << bit_offset)) >> bit_offset

        def resetn_digital_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_2,
                                              src.CONSTANTS.REGISTERS.resetn)

        def conv_syst_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_conv_sys)

        def ro_enable_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_ro_enable)

        def val_evt_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_val_evt)

        def resetn_probe_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_rstn_probe)

        def resetn_latch_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_rstn_latch)

        def power_on_ASIC(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_power_on)

        def hold_ext(self):
            return self.__get_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1,
                                              src.CONSTANTS.REGISTERS.tpr_hold_ext)

        def I2C_clock(self):
            return self.dev.read_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                                     src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck)

        def resetn_I2C_(self):
            return self.dev.read_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                                     src.CONSTANTS.REGISTERS.addr_sc_status_bit_resetn_I2C)

        def resetn_SC(self):
            return self.dev.read_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                                     src.CONSTANTS.REGISTERS.addr_sc_status_bit_resetn_SC)

        def hash_fw_version(self):
            fw_hash = ''
            fw_hash_chr = ''

            for i in range(70):
                a = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_version_string)
                fw_hash += str(a)
                fw_hash_chr += chr(a)

            # print(fw_hash_chr)
            return fw_hash

        def read_timestamp(self):
            # Reading hard-coded synthesis timestamp from a firmware IP (USR_ACCESSE2)
            # https://docs.amd.com/r/en-US/ug570-ultrascale-configuration/USR_ACCESSE2
            timestamp = 0
            for i in range(4):
                val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_timestamp_0+i)
                timestamp += val << (8*i)
            second = timestamp & 0b111111
            minute = (timestamp & (0b111111<<6))>>6
            hour = (timestamp & (0b11111<<12))>>12
            year = ((timestamp & (0b111111<<17))>>17)+2000
            month = (timestamp & (0b1111<<23))>>23
            day = (timestamp & (0b11111<<27))>>27

            timestamp_str = "%d_%d_%d_%d_%d_%d"%(year, month, day, hour, minute, second)
            print("FW = "+timestamp_str)
            return timestamp_str

        def hit_register(self, iteration=1) -> np.array:
            # read the state of latch trigger (L/H/Q) for all channels
            # sensitive on LEVEL thus can not see both sides of the pedestal
            # whereas if was sensitive on EDGES, it could.

            # reset the 3 summation counters
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan, 0)

            # scan all channels a number of times
            for i in range(iteration):
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_channel, 64)

            time.sleep(0.001)
            hit_reg = []
            # read sums
            for i in range(64):
                hit_reg_per_channel = []
                for gain in range(3):
                    hit_reg_per_channel.append(self.dev.read_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan))
                    time.sleep(0.001)
                hit_reg.append(hit_reg_per_channel)
            # print(hit_reg)
            return np.array(hit_reg) / iteration


        def hit_register_faster(self, iteration=200):
            # all channels are read (from 0 up to channel 63 included)
            return self._hit_register(iteration)

        def hit_register_for_one_discri(self, channel, discri, iteration=200):
            hit_reg = self._hit_register(iteration)
            return hit_reg[-channel-1][discri]

        def hit_register_for_group_size_discri(self, channel, discri, group_size, iteration=200):
            hit_reg = self._hit_register(iteration)
            print("check order")
            return hit_reg[-channel-1::-group_size].T[discri] # check order !!

        def _hit_register(self, iteration):
            # read the state of latch trigger (L/H/Q) for all channels
            # sensitive on LEVEL thus can not see both sides of the pedestal
            # whereas if was sensitive on EDGES, it could.
            assert iteration < 256, 'Above 8-bit counter range allocated in FPGA for hit register stats'
            assert iteration >= 0
            channel = 63

            # start = time.time()

            # channel number is fixed to maximum because
            # hit register inside the FPGA is WRITTEN from 0 to 63 but is READ from 63 to 0...
            # need to scan all channel values anyway, partial read forbidden (to improve)
            # first index correspond to lower channel (0) if all channels read

            # reset the 3 summation counters
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan, 0)

            # set number of time to scan channels
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_iter, iteration)
            a = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_read_reg_iter)

            # launch scan while setting the highest channel read before reset to next iteration
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_channel, channel+1)

            one_channel_read_time = 20e-9*20 # 15 irl clock cycles at 50 MHz
            time.sleep(one_channel_read_time*(channel+1)*iteration)

            # read sums
            hit_reg = self.dev.read_words(src.CONSTANTS.REGISTERS.addr_read_reg_scan, 3 * (channel + 1))
            # stop = time.time()
            # print("read sum elapsed time: %.4e s" % (stop - start))
            hit_reg = np.array(np.frombuffer(hit_reg, dtype=np.uint8), dtype=np.int64).reshape(channel + 1, 3) / iteration

            # print(hit_reg)

            # if discri_studied == 'T1':
            #     hit_reg_index = 1
            # elif discri_studied == 'T2':
            #     hit_reg_index = 2
            # elif discri_studied == 'TQ':
            #     hit_reg_index = 3

            # # if any(hit_reg.T[hit_reg_index] != 1):
            # if any(hit_reg.T[1] != 1) or any(hit_reg.T[2] != 1):
            #     # if all channels are "clearly" over the pedestal (because equal to 10 = iteration1)
            #     # no need to iterate more (fasten the s-curve)
            #     # otherwise, if at least one channel starts to see pedestal,
            #     # run following complementary iteration2 for better statistics
            #     iteration2 = 90
            #     hit_reg += self.hit_register2(iteration2)
            #     hit_reg /= 2  # average

            return hit_reg[::-1]  # order reverted due to


        def hit_register_channel(self, channel) -> int:
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_channel,
                                63)  # write last channel number to examin (starts at 0)
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan,
                                0)  # write anything to launch reading read register
            for channel in range(63, channel, -1):  # dump unwanted channel results
                hit_reg = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan)
                # print(channel, hit_reg)
            return self.dev.read_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan)

        def hit_map(self):
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_channel,
                                63)  # write last channel number to examin (starts at 0)
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan,
                                0)  # write anything to launch reading read register
            hit_reg = []
            # for channel in range(63, -1, -1):  # order error
            for channel in range(64):
                # self.common.probeDig.channel(channel).TrigT_L_RS()
                # self.common.probeDig.channel(channel).TrigT_H_RS()
                hit_reg.append(self.dev.read_word(src.CONSTANTS.REGISTERS.addr_read_reg_scan))
                # hit_reg_low = np.bitwise_and(hit_reg, 0b100)
                # hit_reg_high = np.bitwise_and(hit_reg, 0b010)

                pass
            # return np.array(hit_reg[::-1]) # because fill downwards from 63 to 0
            return np.array(hit_reg)

        def hit_map_low(self):
            return np.bitwise_and(self.hit_map(), 0b100)

        def hit_map_high(self):
            return np.bitwise_and(self.hit_map(), 0b010)

    class __set:
        def __init__(self, dev):
            self.dev = dev

        def chipid(self, chip_id_4b):
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_chip_id, chip_id_4b)

        def delay_ext_trigger(self, delay_10b):
            # Write FPGA register with 10 bits value (11th is reserved for chaining several delay boxes)
            # 10 ps step => 10.24 ns range
            delay_10b = int(delay_10b)
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_delayer_low, delay_10b & 0xff)  # lsb
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_delayer_high, (delay_10b & 0b11_0000_0000) >> 8)  # msb

            read_value = ((self.dev.read_word(src.CONSTANTS.REGISTERS.addr_delayer_high) << 8) + self.dev.read_word(
                src.CONSTANTS.REGISTERS.addr_delayer_low))
            if read_value == delay_10b:
                return True
            else:
                print("Read delay from external delaybox does not match written. %d %d" % (delay_10b, read_value))
                return False

        def hit_register_channel(self, channel: int) -> None:
            assert isinstance(channel, int)
            assert channel >= 0
            assert channel <= 63
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_channel, channel + 1)
            return

        def val_event_width_ns(self, width_ns):
            """ by step of 20 ns"""
            # multiple of 50 MHz period
            assert width_ns >= 20  # ns
            assert width_ns < 2 ** 8 * 20
            value_8b = int(width_ns // 20) - 1
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_val_evt, value_8b)
            return value_8b

        def iteration(self, iter_8b):
            assert iter_8b >= 0
            assert iter_8b < 2 ** 8
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_iter, iter_8b)

        def resetn_digital_ASIC(self, value_1b):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_2, value_1b,
                                       src.CONSTANTS.REGISTERS.resetn)

        def PLL_as_clock_source(self):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, 1,
                                       src.CONSTANTS.REGISTERS.tpr_clk_mux_sel)

        def FPGA_as_clock_source(self):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, 0,
                                       src.CONSTANTS.REGISTERS.tpr_clk_mux_sel)

        def __set_fpga_config_reg(self, config_reg, bit_value, bit_offset):
            read_val = self.dev.read_word(config_reg)
            if bit_value == 1:
                new_value = read_val | (1 << bit_offset)
            elif bit_value == 0:
                new_value = read_val & ~(1 << bit_offset)
            else:
                print("Wrong value")
                return
            self.dev.write_word(config_reg, new_value)
            read_val = self.dev.read_word(config_reg)
            if new_value != read_val:
                print(hex(new_value), hex(read_val))
                assert new_value == read_val

        def conv_syst_ASIC(self, value_1b):  # 1 force the digital to convert without internal logic
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_conv_sys)

        def ro_enable_ASIC(self, value_1b):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_ro_enable)

        def val_evt_ASIC(self, value_1b):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_val_evt)

        def resetn_probe_ASIC(self, value_1b):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_rstn_probe)

        def power_on_ASIC(self, value_1b):
            """
            :param value_1b: allows ASIC to receive clock
            :return:
            """
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_power_on)

        def hold_ext_ASIC(self, value_1b):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_hold_ext)

        def resetn_latch_ASIC(self, value_1b):
            self.__set_fpga_config_reg(src.CONSTANTS.REGISTERS.addr_tpr_status_1, value_1b,
                                       src.CONSTANTS.REGISTERS.tpr_rstn_latch)

        def I2C_clock_ASIC(self, value_1b):
            self.dev.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                               src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, value_1b)

        def resetn_I2C_ASIC(self, value_1b):
            self.dev.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                               src.CONSTANTS.REGISTERS.addr_sc_status_bit_resetn_I2C, value_1b)

        def resetn_SC_ASIC(self, value_1b):
            self.dev.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                               src.CONSTANTS.REGISTERS.addr_sc_status_bit_resetn_SC, value_1b)

    class __reset:
        def __init__(self, dev, setter, asic_list):
            self.dev = dev
            self.set = setter
            self.asic_list = asic_list

        def all_temporoc(self):
            self.tpr_SC()
            self.tpr_i2c_sm()
            self.tpr_digital()
            # self.resetn_read() # now controlled by FPGA only not from soft
            self.tpr_probe()
            self.tpr_latch()

        def tpr_SC(self):
            # temporoc slow control configuration
            self.set.resetn_SC_ASIC(0)
            self.set.resetn_SC_ASIC(1)

        def tpr_i2c_sm(self):
            # temporoc i2c state machine
            self.set.resetn_I2C_ASIC(0)
            self.set.resetn_I2C_ASIC(1)

        def tpr_digital(self):
            self.set.resetn_digital_ASIC(0)
            self.set.resetn_digital_ASIC(1)

        def tpr_probe(self):
            self.set.resetn_probe_ASIC(0)
            self.set.resetn_probe_ASIC(1)

        def tpr_latch(self):
            self.set.resetn_latch_ASIC(0)
            self.set.resetn_latch_ASIC(1)

        def latch_force(self, asic=None):
            if asic is None:
                for asic in self.asic_list:
                    asic.common.en.bypassResetMgmt()
            else:
                asic.common.dis.bypassResetMgmt()

            self.tpr_latch()

            if asic is None:
                for asic in self.asic_list:
                    asic.common.en.bypassResetMgmt()
            else:
                asic.common.dis.bypassResetMgmt()

    class __select:
        def __init__(self, dev, FPGA_PLL):
            self.dev = dev
            self.foreign_eof = shared_IO_FPGA_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_eof_foreign,
                                                       None, None)
            self.trigger_mon = self.__probe_mon_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_trigger_mon)
            self.trigger_ext = self.__ext_trigger_selector(dev, src.CONSTANTS.REGISTERS.addr_sma_trigger_ext)
            self.ck_from_FPGA_to_PLL = self.__fpga_to_epll_clk_ref_sel(dev, FPGA_PLL)
            self.ck_from_FPGA_to_ASIC = self.__fpga_to_asic_clk_sel(dev, FPGA_PLL)


        class __ext_trigger_selector:
            def __init__(self, dev, addr_sma):
                self.dev = dev
                self.addr_sma = addr_sma

            def off(self):
                self.dev.write_word(self.addr_sma, 0)

            def or_trig_l_rs(self):
                self.dev.write_word(self.addr_sma, 4)

            def or_trig_h_rs(self):
                self.dev.write_word(self.addr_sma, 5)

            def or_trig_q(self):
                self.dev.write_word(self.addr_sma, 6)

            def or_trig_q_rs(self):
                self.dev.write_word(self.addr_sma, 7)

        class __probe_mon_selector:
            def __init__(self, dev, addr_sma):
                self.dev = dev
                self.addr_sma = addr_sma

            def digit_probe(self):
                self.dev.write_word(self.addr_sma, 0)

            def or_trig_l_rs(self):
                self.dev.write_word(self.addr_sma, 4)

            def or_trig_h_rs(self):
                self.dev.write_word(self.addr_sma, 5)

            def or_trig_q(self):
                self.dev.write_word(self.addr_sma, 6)

            def or_trig_q_rs(self):
                self.dev.write_word(self.addr_sma, 7)


        class __fpga_to_epll_clk_ref_sel:
            def __init__(self, dev, FPGA_PLL):
                self.dev = dev
                self.FPGA_register = src.CONSTANTS.REGISTERS.addr_tpr_epll_clk_sel
                self.offset = 0
                self.length = 3

            def __write_in_place(self, new_val):
                # read back
                old_val = self.dev.read_word(self.FPGA_register)
                # write new bit(s) : keep old bits, add new bits
                mask = (~(((2 ** self.length) - 1) << self.offset) & 0xff)
                new_val = new_val & (2**self.length-1)
                new_val = (old_val & mask) | (new_val << self.offset)
                self.dev.write_word(self.FPGA_register, new_val)

            def off(self):
                self.__write_in_place(0b000)

            def cristal_100MHz(self):
                self.__write_in_place(0b001)

            def input_clk1(self):
                self.__write_in_place(0b010)

            def input_clk2(self):
                self.__write_in_place(0b011)

            def clk_320(self):
                self.__write_in_place(0b100)

            def readback_config(self):
                val = (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tpr_status_2) & (
                        0b11 << self.offset)) >> self.offset
                print(bin(val))
                return val

        class __fpga_to_asic_clk_sel:
            def __init__(self, dev, FPGA_PLL):
                self.dev = dev
                self.FPGA_register = src.CONSTANTS.REGISTERS.addr_tpr_fpga_to_asic_clk_sel
                self.offset = 0
                self.length = 3

            def __write_in_place(self, new_val):
                # read back
                old_val = self.dev.read_word(self.FPGA_register)
                # write new bit(s) : keep old bits, add new bits
                mask = (~(((2 ** self.length) - 1) << self.offset) & 0xff)
                new_val = new_val & (2**self.length-1)
                new_val = (old_val & mask) | (new_val << self.offset)
                self.dev.write_word(self.FPGA_register, new_val)

            def off(self):
                self.__write_in_place(0b000)

            def PLL_OUT3(self): # epll_to_fpga_clk
                self.__write_in_place(0b001)

            def input_clk1(self):
                self.__write_in_place(0b010)

            def input_clk2(self):
                self.__write_in_place(0b011)

            def clk_320(self):
                self.__write_in_place(0b100)

            def readback_config(self):
                val = (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tpr_status_2) & (
                        0b11 << self.shift)) >> self.shift
                print(bin(val))
                return val

    class __1:
        def __init__(self, dev):
            self.dev = dev

        def en_ck320(self):
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_sma_control, 0x11)

        def dis_ck320(self):
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_sma_control, 0x10)

    class __5:
        def __init__(self, dev):
            self.dev = dev

        def en_ck40M(self):  # in phase with hit to delay
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_sma_control, 0x51)

        def dis_ck40M(self):
            self.dev.write_word(src.CONSTANTS.REGISTERS.addr_sma_control, 0x50)


class shared_IO_FPGA_selector:
    def __init__(self, dev, addr_sma, addr_sma_common, ena_io_fpga_addr, asic_list=None):
        self.dev = dev
        self.addr_sma = addr_sma
        self.addr_sma_common = addr_sma_common
        self.ena_io_fpga_addr = ena_io_fpga_addr
        self.offset = 44
        self.enabled = 0
        self.asic_list = asic_list

    def __enable_probe(self, index):
        self.dev.write_word(self.addr_sma, index)
        if self.addr_sma_common:
            if not self.enabled:
                self.dev.write_word(self.addr_sma_common, (self.ena_io_fpga_addr << 4) + 1)
                self.enabled = 1

    def __disable(self):
        self.dev.write_word(self.addr_sma_common, (self.ena_io_fpga_addr << 4) + 0)

    def off(self):
        if self.addr_sma_common:
            self.__disable()
        self.dev.write_word(self.addr_sma, 0)

    def tpr_rstn_local(self):
        self.__enable_probe(1)

    def tpr_rstn_foreign(self):
        self.__enable_probe(2)

    def tpr_rstn_to_asic(self):
        self.__enable_probe(3)

    def ser_clk(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(4 + cluster)

    def ser_time_cpt_sampled(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(67 + cluster)

    def ser_data(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(8 + cluster)

    def ser_ovf(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(12 + cluster)

    def local_eof(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(16 + cluster)

    def frame_received_by_charge_filter(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(20 + cluster)

    def frame_rejected_by_charge_filter(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(24 + cluster)

    def frame_received_by_retriggering_filter(self, cluster):
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(28 + cluster)

    def frame_rejected_by_retriggering_filter(self, cluster):
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(32 + cluster)

    def frame_received_by_eof_coincidence_inter_cluster_filter(self, cluster):
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(36 + cluster)

    def frame_rejected_by_eof_coincidence_inter_cluster_filter(self, cluster):
        assert cluster >= 0
        assert cluster < 4
        self.__enable_probe(40 + cluster)

    def or_trig_l_rs(self):
        for asic in self.asic_list:
            asic.interface.en.Nor_TrigT_L_RS()
        self.__enable_probe(self.offset + 0)

    def or_trig_h_rs(self):
        for asic in self.asic_list:
            asic.interface.en.Nor_TrigT_H_RS()
        self.__enable_probe(self.offset + 1)

    def or_trig_q(self):
        for asic in self.asic_list:
            asic.interface.en.Nor_TrigQ()
        self.__enable_probe(self.offset + 2)

    def or_trig_q_rs(self):
        for asic in self.asic_list:
            asic.interface.en.Nor_TrigQ_RS()
        self.__enable_probe(self.offset + 3)

    def trig_q_mux(self):
        for asic in self.asic_list:
            asic.interface.en.trigQ_RS_mux()
        self.__enable_probe(self.offset + 4)

    def trig_t_l_rs_mux(self):
        for asic in self.asic_list:
            asic.interface.en.trigT_L_RS_mux()
        self.__enable_probe(self.offset + 5)

    def trig_t_h_rs_mux(self):
        for asic in self.asic_list:
            asic.interface.en.trigT_H_RS_mux()
        self.__enable_probe(self.offset + 6)

    def tdc_dat_val(self):
        self.__enable_probe(self.offset + 7)

    def adc_cnv_done(self):  # external ADC
        self.__enable_probe(self.offset + 8)

    def digit_probe(self):
        self.__enable_probe(self.offset + 9)

    def pulse_tdc(self):
        self.__enable_probe(self.offset + 10)

    def input_clk1(self):
        self.__enable_probe(self.offset + 11)

    def input_clk2(self):
        self.__enable_probe(self.offset + 12)

    def val_evnt(self):
        self.__enable_probe(self.offset + 13)

    def eof_local(self):
        self.__enable_probe(self.offset + 14)

    def coincidence(self):
        self.__enable_probe(self.offset + 15)

    # 1 free address space

    def ck_towards_PLL(self):
        self.__enable_probe(62)

    def ck_from_PLL_OUT3(self):
        self.__enable_probe(63)

    def tpr_read_rstn(self):
        self.__enable_probe(64)

    def tpr_read_clk(self):
        self.__enable_probe(65)

    def tpr_read_clkn(self):
        self.__enable_probe(66)

    def SPI_PLL_SCLK(self):
        self.__enable_probe(71)

    def SPI_PLL_CSb(self):
        self.__enable_probe(72)

    def SPI_PLL_MOSI(self):
        self.__enable_probe(73)

    def SPI_PLL_MISO(self):
        self.__enable_probe(74)

    # free address space up to 127
