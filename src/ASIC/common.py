import time
import warnings


class common:
    def __init__(self, i2c):
        self.set = self.__set(i2c)
        self.get = self.__get(i2c)
        self.en = self.__enable(i2c)
        self.dis = self.__disable(i2c)
        self.select = self.__select(i2c)
        self.probeDig = self.__probeDig(i2c)

    class __probeDig:
        def __init__(self, i2c):
            self.digital_probe = None
            self.channel = self.__channel(i2c, self)
            self.cluster = self.__cluster(i2c, self)

        class __channel:
            def __init__(self, i2c, _probeDig):
                self.__i2c = i2c
                self._probeDig = _probeDig

            def __call__(self, ch):
                assert isinstance(ch, int)
                assert ch >= 0
                assert ch < 64

                # tempo.asic.interface.en.digital_probe()
                self.__i2c.set_bit(66, 3, 6, 1)

                if self._probeDig.digital_probe is not None:
                    address = self._probeDig.digital_probe[0]
                    sub_address = self._probeDig.digital_probe[1]
                    if ch != address:
                        # print(f'reset probe {address} {sub_address}')
                        self.__i2c.write_register(address, sub_address, 0)
                        if address == 65:
                            # print(f'reset probe {address} {sub_address+1}')
                            self.__i2c.write_register(address, sub_address + 1, 0)

                self._probeDig.digital_probe = [ch, 66]  # Save probe enabled to avoid collisions
                self.off = self.__off(self.__i2c, ch)
                self.rstn_TDC = self.__rstn_TDC(self.__i2c, ch)
                self.TrigT_H = self.__TrigT_H(self.__i2c, ch)
                self.TrigT_H_RS = self.__TrigT_H_RS(self.__i2c, ch)
                self.TH = self.__TH(self.__i2c, ch)
                self.TrigT_L = self.__TrigT_L(self.__i2c, ch)
                self.TrigT_L_RS = self.__TrigT_L_RS(self.__i2c, ch)
                self.TL = self.__TL(self.__i2c, ch)
                return self

            class __off:
                def __init__(self, i2c, ch):
                    self.__i2c = i2c
                    self.__ch = ch

                def __call__(self):
                    self._probeDig.digital_probe = None
                    self.__i2c.write_register(self.__ch, 66, 0)

            class __rstn_TDC:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b1000_0000)

            class __TrigT_H:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b0100_0000)

            class __TrigT_H_RS:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b0010_0000)

            class __TH:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b0001_0000)

            class __TrigT_L:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b0000_1000)

            class __TrigT_L_RS:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b0000_0100)

            class __TL:
                def __init__(self, i2c, ch):
                    self.__ch = ch
                    self.__i2c = i2c

                def __call__(self):
                    self.__i2c.write_register(self.__ch, 66, 0b0000_0010)

        class __cluster:
            def __init__(self, i2c, _probeDig):
                self.__i2c = i2c
                self.__probeDig = _probeDig
                self.__i2c = i2c
                self.__subaddr = None

            def __call__(self, cluster_index):
                assert isinstance(cluster_index, int)
                assert cluster_index >= 0
                assert cluster_index < 4
                self.__subaddr = 12 + 2 * cluster_index
                # print('cluster')

                # tempo.asic.interface.en.digital_probe()
                self.__i2c.set_bit(66, 3, 6, 1)

                if self.__probeDig.digital_probe is not None:
                    address = self.__probeDig.digital_probe[0]
                    sub_address = self.__probeDig.digital_probe[1]
                    # print(f'reset probe {address} {sub_address}')
                    self.__i2c.write_register(address, sub_address, 0)

                    if address == 65:
                        # print(f'reset probe {address} {sub_address+1}')
                        self.__i2c.write_register(address, sub_address + 1, 0)

                return self

            def off(self):
                self.__probeDig.digital_probe = None
                self.__i2c.write_register(65, self.__subaddr, 0)
                self.__i2c.write_register(65, self.__subaddr + 1, 0)

            def selectADCHG(self):
                self.__probeDig.digital_probe = [65, self.__subaddr]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr, 0b1000_0000)

            def selectADCLG(self):
                self.__probeDig.digital_probe = [65, self.__subaddr]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr, 0b0100_0000)

            def hold(self):
                self.__probeDig.digital_probe = [65, self.__subaddr]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr, 0b0001_0000)

            def event_window_end(self):
                self.__probeDig.digital_probe = [65, self.__subaddr]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr, 0b0000_1000)

            def convDoneADCHG(self):
                self.__probeDig.digital_probe = [65, self.__subaddr]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr, 0b0000_0010)

            def convDoneADCLG(self):
                self.__probeDig.digital_probe = [65, self.__subaddr]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr, 0b0000_0001)

            def rstn_sync(self):
                self.__probeDig.digital_probe = [65, self.__subaddr + 1]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr + 1, 0b0000_0010)

            def rstn_latch_int(self):
                self.__probeDig.digital_probe = [65, self.__subaddr + 1]  # Save probe enabled to avoid collisions
                self.__i2c.write_register(65, self.__subaddr + 1, 0b0000_0001)


    class __select:
        def __init__(self, i2c):
            self.trigger = self.__trigger(i2c)
            self.hold = self.__hold(i2c)

        class __trigger:
            def __init__(self, i2c):
                self.__i2c = i2c

            def global_ASIC(self):
                self.__i2c.set_bits(65, 11, 0, 2, 0)

            def local_time_low(self):
                self.__i2c.set_bits(65, 11, 0, 2, 1)

            def local_time_high(self):
                self.__i2c.set_bits(65, 11, 0, 2, 2)

            def local_charge_high(self):
                self.__i2c.set_bits(65, 11, 0, 2, 3)

        class __hold:
            def __init__(self, i2c):
                self.__i2c = i2c

            def internal(self):
                self.__i2c.set_bit(65, 11, 4, 0)

            def external(self):
                self.__i2c.set_bit(65, 11, 4, 1)

    class __enable:
        def __init__(self, i2c):
            self.__i2c = i2c

        def TL(self):
            self.__i2c.set_bit(65, 7, 3, 1)

        def T2(self):
            self.__i2c.set_bit(65, 7, 2, 1)

        def TQ(self):
            self.__i2c.set_bit(65, 7, 1, 1)

        def bg(self):
            self.__i2c.set_bit(65, 7, 0, 1)

        def hyst_TL(self):
            self.__i2c.set_bit(65, 11, 7, 1)

        def hyst_TH(self):
            self.__i2c.set_bit(65, 11, 6, 1)

        def bypassResetMgmt(self):
            """ If enabled, reset from analog. Otherwise, disabled (default state) means reset from digital """
            self.__i2c.set_bit(65, 11, 5, 1)

        def latch(self):
            self.__i2c.set_bit(65, 11, 2, 1)

        def FallingEdgeDetectorH(self):
            self.__i2c.set_bit(65, 8, 3, 1)

        def FallingEdgeDetectorL(self):
            self.__i2c.set_bit(65, 8, 2, 1)

        def TH_polarity(self):
            self.__i2c.set_bit(65, 8, 1, 1)

        def TL_polarity(self):
            self.__i2c.set_bit(65, 8, 0, 1)

        def sel_tdc_rising_edge(self):
            self.__i2c.set_bit(65, 9, 7, 1)


    class __disable:
        def __init__(self, i2c):
            self.__i2c = i2c

        def TL(self):
            self.__i2c.set_bit(65, 7, 3, 0)

        def TH(self):
            self.__i2c.set_bit(65, 7, 2, 0)

        def TQ(self):
            self.__i2c.set_bit(65, 7, 1, 0)

        def bg(self):
            self.__i2c.set_bit(65, 7, 0, 0)

        def hyst_TL(self):
            self.__i2c.set_bit(65, 11, 7, 0)

        def hyst_TH(self):
            self.__i2c.set_bit(65, 11, 6, 0)

        def bypassResetMgmt(self):
            self.__i2c.set_bit(65, 11, 5, 0)

        def latch(self):
            self.__i2c.set_bit(65, 11, 2, 0)

        def FallingEdgeDetectorH(self):
            self.__i2c.set_bit(65, 8, 3, 0)

        def FallingEdgeDetectorL(self):
            self.__i2c.set_bit(65, 8, 2, 0)

        def TH_polarity(self):
            self.__i2c.set_bit(65, 8, 1, 0)

        def TL_polarity(self):
            self.__i2c.set_bit(65, 8, 0, 0)

        def sel_tdc_rising_edge(self):
            self.__i2c.set_bit(65, 9, 7, 0)


    class __set:
        def __init__(self, i2c):
            self.__i2c = i2c

        def bias_1V(self, value_4b):
            assert value_4b >= 0
            assert value_4b < 2**4
            self.__i2c.set_bits(65, 0, 4, 4, value_4b)

        def BG(self, value_4b):
            assert value_4b >= 0
            assert value_4b < 2**4
            self.__i2c.set_bits(65, 0, 0, 4, value_4b)

        def dacTx_wait_stable(self, value_10b, discri):
            if (discri == 1) | (discri == 'TL'):
                self.dacTL_wait_stable(value_10b)
            elif (discri == 2) | (discri == 'TH'):
                self.dacTH_wait_stable(value_10b)
            elif discri == "TQ":
                self.dacQ_wait_stable(value_10b)
            else:
                print('Unknown discriminator')
                exit(0)

        def dacTL(self, value_10b):
            assert value_10b >= 0
            assert value_10b < 2**10
            self.__i2c.set_bits(65, 1, 0, 8, value_10b & 0xff)
            self.__i2c.set_bits(65, 2, 0, 2, (value_10b & 0x300) >> 8)

        def dacTL_wait_stable(self, value_10b):
            assert value_10b >= 0
            assert value_10b < 2**10
            prev_value_10b = (self.__i2c.get_bits(65, 2, 0, 2) << 8) + self.__i2c.get_bits(65, 1, 0, 8)
            self.__i2c.set_bits(65, 1, 0, 8, value_10b & 0xff)
            self.__i2c.set_bits(65, 2, 0, 2, (value_10b & 0x300) >> 8)

            # Measure voltage span to vary to compute minimum delay
            # delay = abs(prev_value_10b-value_10b)*0.0005
            delay = abs(prev_value_10b-value_10b)*0.001
            time.sleep(delay)

        def dacTH(self, value_10b):
            assert value_10b >= 0
            assert value_10b < 2**10
            self.__i2c.set_bits(65, 2, 2, 6, value_10b & 0b11_1111)
            self.__i2c.set_bits(65, 3, 0, 4, (value_10b >> 6) & 0b1111)

        def dacTH_wait_stable(self, value_10b):
            assert value_10b >= 0
            assert value_10b < 2**10
            prev_value_10b = (self.__i2c.get_bits(65, 3, 0, 4) << 6) + self.__i2c.get_bits(65, 2, 2, 6)
            self.__i2c.set_bits(65, 2, 2, 6, value_10b & 0b11_1111)
            self.__i2c.set_bits(65, 3, 0, 4, (value_10b >> 6) & 0b1111)

            # Measure voltage span to vary to compute minimum delay
            delay = abs(prev_value_10b-value_10b)*0.0005
            time.sleep(delay)

        def dacT12_wait_stable(self, T1_value_10b, T2_value_10b):
            assert T1_value_10b >= 0
            assert T1_value_10b < 2**10

            assert T2_value_10b >= 0
            assert T2_value_10b < 2**10

            prev_T1_value_10b = (self.__i2c.get_bits(65, 2, 0, 2) << 8) + self.__i2c.get_bits(65, 1, 0, 8)
            self.__i2c.set_bits(65, 1, 0, 8, T1_value_10b & 0xff)
            self.__i2c.set_bits(65, 2, 0, 2, (T1_value_10b & 0x300) >> 8)

            prev_T2_value_10b = (self.__i2c.get_bits(65, 3, 0, 4) << 6) + self.__i2c.get_bits(65, 2, 2, 6)
            self.__i2c.set_bits(65, 2, 2, 6, T2_value_10b & 0b11_1111)
            self.__i2c.set_bits(65, 3, 0, 4, (T2_value_10b >> 6) & 0b1111)

            # Measure voltage span to vary to compute minimum delay
            delay = max(abs(prev_T1_value_10b-T1_value_10b), abs(prev_T2_value_10b-T2_value_10b))*0.0005
            time.sleep(delay)

        def dacQ(self, value_10b):
            assert value_10b >= 0
            assert value_10b < 2**10
            self.__i2c.set_bits(65, 3, 4, 4, value_10b & 0b1111)
            self.__i2c.set_bits(65, 4, 0, 6, (value_10b >> 4) & 0b11_1111)

        def dacQ_wait_stable(self, value_10b):
            assert value_10b >= 0
            assert value_10b < 2**10
            prev_value_10b = self.__i2c.get_bits(65, 4, 0, 6) << 4 + self.__i2c.get_bits(65, 3, 4, 4)

            self.__i2c.set_bits(65, 3, 4, 4, value_10b & 0b1111)
            self.__i2c.set_bits(65, 4, 0, 6, (value_10b >> 4) & 0b11_1111)
            # Measure dac span to vary to compute minimum delay
            delay = abs(prev_value_10b-value_10b)*0.0005
            time.sleep(delay)

        def Ibi_threshold_dac(self, value_4b):
            assert value_4b >= 0
            assert value_4b < 2**4
            self.__i2c.set_bits(65, 5, 4, 4, value_4b)

        def Ibo_threshold_dac(self, value_4b):
            self.__i2c.set_bits(65, 5, 0, 4, value_4b)

        def Ibi_threshold_dacQ(self, value_4b):
            self.__i2c.set_bits(65, 6, 4, 4, value_4b)

        def Ibo_threshold_dacQ(self, value_4b):
            self.__i2c.set_bits(65, 6, 0, 4, value_4b)

        def shaper_delay_length(self, value_5b):
            self.__i2c.set_bits(65, 9, 0, 5, value_5b)

        def event_window_length(self, value_6b):
            self.__i2c.set_bits(65, 10, 0, 6, value_6b)

    class __get:
        def __init__(self, i2c):
            self.__i2c = i2c

        def BG(self):
            return self.__i2c.get_bits(65, 0, 0, 6)

        def dacTL(self):
            return (self.__i2c.get_bits(65, 2, 0, 2) << 8) + self.__i2c.get_bits(65, 1, 0, 8)

        def dacTH(self):
            return (self.__i2c.get_bits(65, 3, 0, 4) << 6) + self.__i2c.get_bits(65, 2, 2, 6)

        def dacQ(self):
            return (self.__i2c.get_bits(65, 4, 0, 6) << 4) + self.__i2c.get_bits(65, 3, 4, 4)


        def Ibi_threshold_dac(self):
            return self.__i2c.get_bits(65, 5, 4, 4)

        def Ibo_threshold_dac(self):
            return self.__i2c.get_bits(65, 5, 0, 4)

        def Ibi_threshold_dacQ(self):
            return self.__i2c.get_bits(65, 6, 4, 4)

        def Ibo_threshold_dacQ(self):
            return self.__i2c.get_bits(65, 6, 0, 4)

        def shaper_delay_length(self):
            return self.__i2c.get_bits(65, 9, 0, 5)

        def event_window_length(self):
            return self.__i2c.get_bits(65, 10, 0, 6)
