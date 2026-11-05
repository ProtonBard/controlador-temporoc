from src.CONSTANTS import CONSTANTS


class interface:  # merged subaddress 66 and 67 into interface as they are not respecting 66=analog 67=digital
    def __init__(self, i2c):
        self.__i2c = i2c
                
        self.en = self.__enable(self.__i2c)
        self.dis = self.__disable(self.__i2c)
        self.set = self.__set(self.__i2c)
        self.get = self.__get(self.__i2c)
        self.select = self.__select(i2c)

    class __select:
        def __init__(self, i2c):
            self.__i2c = i2c
            self.global_trigger = self.__global_trigger(i2c)
            self.dig_modeRO = self.__dig_modeRO(i2c)
            self.miller_cap_LG_pdet_buffer_n = self.__miller_cap(i2c, 2, 6)
            self.miller_cap_LG_pdet_buffer_p = self.__miller_cap(i2c, 2, 4)
            self.miller_cap_HG_pdet_buffer_n = self.__miller_cap(i2c, 2, 2)
            self.miller_cap_HG_pdet_buffer_p = self.__miller_cap(i2c, 2, 0)
            self.miller_cap_probeA = self.__miller_cap(i2c, 3, 0)

        class __global_trigger:
            def __init__(self, i2c):
                self.__i2c = i2c

            def ground(self):
                self.__i2c.set_bits(66, 3, 0, 2, 0)

            def ORTL(self):
                self.__i2c.set_bits(66, 3, 0, 2, 1)

            def ORTH(self):
                self.__i2c.set_bits(66, 3, 0, 2, 2)

            def ORTQ(self):
                self.__i2c.set_bits(66, 3, 0, 2, 3)

        class __dig_modeRO:
            def __init__(self, i2c):
                self.__i2c = i2c
                # if (not simu) & (self.__i2c.connect_status == 1):
                #     self.tempo.deserialiser_reset()
                # Temporoc3 default value
                self.RO_code = 0b01111
                self.RO_str = "full_adc_tdc"
                self.RObit_count = 1154
     
            def __call__(self, mode: str|int):
                if isinstance(mode, str):
                    self.__set_RO_mode_as_str(mode)
                elif isinstance(mode, int):
                    self.__set_RO_mode_as_int(mode)
                else:
                    print("Unknown TEMPOROC digital readout mode %s" % mode)
                # getattr(self, mode)()

            def __str__(self):
                return self.RO_str

            def __set_RO_mode_as_str(self, ROmode_str: str):
                assert ROmode_str in CONSTANTS.FRAME_LENGTH_RO_MODE_STR.keys(), "Unknown TEMPOROC digital readout mode %s" % ROmode_str
                tmp = CONSTANTS.FRAME_LENGTH_RO_MODE_STR[ROmode_str]
                self.RO_code = tmp[1]
                self.RO_str = ROmode_str
                self.RObit_count = tmp[0]
                self.__i2c.set_bits(66, 4, 0, 5, self.RO_code)

            def __set_RO_mode_as_int(self, RO_mode_int:int):
                assert RO_mode_int<32
                assert RO_mode_int>=0
                self.RO_code = RO_mode_int
                self.RO_str = ''
                self.RObit_count = CONSTANTS.FRAME_LENGTH_RO_MODE_INT[RO_mode_int]
                self.__i2c.set_bits(66, 4, 0, 5, self.RO_code)

            def full_adc_tdc(self):
                self.RO_str = "full_adc_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def hg_adc_high_tdc(self):
                self.RO_str = "hg_adc_high_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def lg_adc_low_tdc(self):
                self.RO_str = "lg_adc_low_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def hg_lg_adc(self):
                self.RO_str = "hg_lg_adc"
                self.__set_RO_mode_as_str(self.RO_str)

            def hg_adc(self):
                self.RO_str = "hg_adc"
                self.__set_RO_mode_as_str(self.RO_str)

            def lg_adc(self):
                self.RO_str = "lg_adc"
                self.__set_RO_mode_as_str(self.RO_str)

            def low_high_tdc(self):
                self.RO_str = "low_high_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def high_tdc(self):
                self.RO_str = "high_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def low_tdc(self):
                self.RO_str = "low_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def hg_adc_low_tdc(self):
                self.RO_str = "hg_adc_low_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def lg_adc_high_tdc(self):
                self.RO_str = "lg_adc_high_tdc"
                self.__set_RO_mode_as_str(self.RO_str)

            def hit(self):
                self.RO_str = "hit"
                self.__set_RO_mode_as_str(self.RO_str)

            def fuller(self):
                self.RO_str = "fuller"
                self.__set_RO_mode_as_str(self.RO_str)


        class __miller_cap:
            def __init__(self, i2c, subaddr, bit_offset_lsb):
                self.__bit_offset_lsb = bit_offset_lsb
                self.__subaddr = subaddr
                self.__i2c = i2c

            def _100fF(self):
                self.__i2c.set_bits(67, self.__subaddr, self.__bit_offset_lsb, 2, 0)

            def _300fF(self):
                self.__i2c.set_bits(67, self.__subaddr, self.__bit_offset_lsb, 2, 1)

            def _500fF(self):
                self.__i2c.set_bits(67, self.__subaddr, self.__bit_offset_lsb, 2, 2)

            def _700fF(self):
                self.__i2c.set_bits(67, self.__subaddr, self.__bit_offset_lsb, 2, 3)

    class __set:
        def __init__(self, i2c):
            self.__i2c = i2c

        def TX_strength(self, value_4b):
            self.__i2c.set_bits(66, 0, 4, 4, value_4b)

        def TX_preEmphasis(self, value_4b):
            self.__i2c.set_bits(66, 0, 0, 4, value_4b)

        def Delay_TX_preEmphasis(self, value_2b):
            self.__i2c.set_bits(66, 1, 0, 2, value_2b)

        def nb_trigger(self, value5b):
            assert value5b < 32
            assert value5b >= 0
            self.__i2c.set_bits(66, 5, 0, 5, value5b)

        def Ibi_buffer(self, value4b):
            self.__i2c.set_bits(67, 0, 0, 4, value4b)

        def ibFCP_buffer(self, value4b):
            self.__i2c.set_bits(67, 1, 4, 4, value4b)

        def ibFCN_buffer(self, value4b):
            self.__i2c.set_bits(67, 1, 0, 4, value4b)

    class __get:
        def __init__(self, i2c):
            self.__i2c = i2c

        def TX_strength(self):
            return self.__i2c.get_bits(66, 0, 4, 4)

        def TX_preEmphasis(self):
            return self.__i2c.get_bits(66, 0, 0, 4)

        def Delay_TX_preEmphasis(self):
            return self.__i2c.get_bits(66, 1, 0, 2)

        def nb_trigger(self):
            return self.__i2c.get_bits(66, 5, 0, 5)

        def Ibi_buffer(self):
            return self.__i2c.get_bits(67, 0, 0, 4)

        def ibFCP_buffer(self):
            return self.__i2c.get_bits(67, 1, 4, 4)

        def ibFCN_buffer(self):
            return self.__i2c.get_bits(67, 1, 0, 4)

    class __enable:
        def __init__(self, i2c):
            self.__i2c = i2c

        def RX(self):
            self.__i2c.set_bit(66, 2, 7, 1)

        def PowerPulsing_RX(self):
            self.__i2c.set_bit(66, 2, 6, 1)

        def Forced_ValEvt(self):
            self.__i2c.set_bit(66, 2, 5, 1)

        def ck320(self):
            self.__i2c.set_bit(66, 3, 7, 1)

        def digital_probe(self):
            self.__i2c.set_bit(66, 3, 6, 1)

        def Nor_TrigT_L_RS(self):
            self.__i2c.set_bit(66, 3, 5, 1)

        def Nor_TrigQ(self):
            self.__i2c.set_bit(66, 3, 4, 1)

        def Nor_TrigT_H_RS(self):
            self.__i2c.set_bit(66, 3, 3, 1)

        def Nor_TrigQ_RS(self):
            self.__i2c.set_bit(66, 3, 2, 1)

        def trigT_L_RS_mux(self):
            self.__i2c.set_bit(66, 4, 7, 1)

        def trigT_H_RS_mux(self):
            self.__i2c.set_bit(66, 4, 6, 1)

        def trigQ_RS_mux(self):
            self.__i2c.set_bit(66, 4, 5, 1)

        def slow_adc_mux(self):
            self.__i2c.set_bit(66, 5, 7, 1)

        def sel_trigger_high(self):
            self.__i2c.set_bit(66, 5, 6, 1)

        def sync_cluster(self):
            self.__i2c.set_bit(66, 5, 5, 1)

        def TDC_passthrough(self):
            self.__i2c.set_bit(66, 6, 7, 1)

        def trigger_charge_inh(self):
            self.__i2c.set_bit(66, 6, 6, 1)

        def tdc_ck(self):
            self.__i2c.set_bit(66, 6, 5, 1)

        def tdc_trigger(self):
            self.__i2c.set_bit(66, 6, 4, 1)

        def ClkDataRO_cluster_for_channel(self, channel):
            self.ClkDataRO_cluster(channel // 16)

        def ClkDataRO_cluster(self, cluster_list):
            if isinstance(cluster_list, list):
                for cluster in cluster_list:
                    self.__ClkDataRO_cluster(cluster)
            else:
                self.__ClkDataRO_cluster(cluster_list)

        def __ClkDataRO_cluster(self, cluster):
            assert isinstance(cluster, int)
            assert cluster >= 0
            assert cluster < 4
            self.__i2c.set_bit(66, 6, cluster, 1)

        def bias_buffer(self):
            self.__i2c.set_bit(67, 0, 4, 1)

        def analog_probe(self):
            self.__i2c.set_bit(67, 3, 4, 1)

        def LG_pdet_MUX_output(self):
            self.__i2c.set_bit(67, 3, 3, 1)

        def HG_pdet_MUX_output(self):
            self.__i2c.set_bit(67, 3, 2, 1)

    class __disable:
        def __init__(self, i2c):
            self.__i2c = i2c

        def RX(self):
            self.__i2c.set_bit(66, 2, 7, 0)

        def PowerPulsing_RX(self):
            self.__i2c.set_bit(66, 2, 6, 0)

        def Forced_ValEvt(self):
            self.__i2c.set_bit(66, 2, 5, 0)

        def ck320(self):
            self.__i2c.set_bit(66, 3, 1, 0)

        def digital_probe(self):
            self.__i2c.set_bit(66, 3, 6, 0)

        def Nor_TrigT_L_RS(self):
            self.__i2c.set_bit(66, 3, 5, 0)

        def Nor_TrigT_Q(self):
            self.__i2c.set_bit(66, 3, 4, 0)

        def Nor_TrigT_H_RS(self):
            self.__i2c.set_bit(66, 3, 3, 0)

        def Nor_TrigQ_RS(self):
            self.__i2c.set_bit(66, 3, 2, 0)

        def trigT_L_RS_mux(self):
            self.__i2c.set_bit(66, 4, 7, 0)

        def trigT_H_RS_mux(self):
            self.__i2c.set_bit(66, 4, 6, 0)

        def trigQ_RS_mux(self):
            self.__i2c.set_bit(66, 4, 5, 0)

        def slow_adc_mux(self):
            self.__i2c.set_bit(66, 5, 7, 0)

        def sel_trigger_high(self):
            self.__i2c.set_bit(66, 5, 6, 0)

        def sync_cluster(self):
            self.__i2c.set_bit(66, 5, 5, 0)

        def TDC_passthrough(self):
            self.__i2c.set_bit(66, 6, 7, 0)

        def trigger_charge_inh(self):
            self.__i2c.set_bit(66, 6, 6, 0)

        def tdc_ck(self):
            self.__i2c.set_bit(66, 6, 5, 0)

        def tdc_trigger(self):
            self.__i2c.set_bit(66, 6, 4, 0)

        def ClkDataRO_other_clusters_for_channel(self, channel):
            self.ClkDataRO_cluster([i for i in range(4) if i != (channel // 16)])

        def ClkDataRO_clusters_except(self, cluster_list):
            if isinstance(cluster_list, list):
                pass
            elif isinstance(cluster_list, int):
                cluster_list = [cluster_list]
            else:
                print("Input type not accepted")
            cluster_list = list(set(cluster_list) ^ {0, 1, 2, 3})  # complentary list
            for cluster in cluster_list:
                self.__ClkDataRO_cluster(cluster)

        def ClkDataRO_cluster(self, cluster_list):
            if isinstance(cluster_list, list):
                for cluster in cluster_list:
                    self.__ClkDataRO_cluster(cluster)
            else:
                self.__ClkDataRO_cluster(cluster_list)

        def __ClkDataRO_cluster(self, cluster):
            assert isinstance(cluster, int)
            assert cluster >= 0
            assert cluster < 4
            self.__i2c.set_bit(66, 6, cluster, 0)

        def bias_buffer(self):
            self.__i2c.set_bit(67, 0, 4, 0)

        def analog_probe(self):
            self.__i2c.set_bit(67, 3, 4, 0)

        def LG_pdet_MUX_output(self):
            self.__i2c.set_bit(67, 3, 3, 0)

        def HG_pdet_MUX_output(self):
            self.__i2c.set_bit(67, 3, 2, 0)
