class channel:
    def __init__(self, i2c):
        self.__channel_list = [0]
        self.__i2c = i2c
        
        self.enable = self.__enable(i2c, self.__channel_list)
        self.disable = self.__disable(i2c, self.__channel_list)
        self.set = self.__set(i2c, self.__channel_list)
        self.get = self.__get(i2c, self.__channel_list)
        self.select = self.__select(i2c, self.__channel_list)

    def __call__(self, ch):
        self.__channel_list = [int(ch)]
        self.enable = self.__enable(self.__i2c, self.__channel_list)
        self.disable = self.__disable(self.__i2c, self.__channel_list)
        self.set = self.__set(self.__i2c, self.__channel_list)
        self.get = self.__get(self.__i2c, self.__channel_list)
        self.select = self.__select(self.__i2c, self.__channel_list)
        return self

        # dynamic variable instanciation does not allow for autocompletion in pycharm IDE...
        # for ch in range(64):
        #     setattr(self, "ch%d"%ch, self.__channel(ch))

    def all(self):
        self.__channel_list = list(range(64))

        self.enable = self.__enable(self.__i2c, self.__channel_list)
        self.disable = self.__disable(self.__i2c, self.__channel_list)
        self.set = self.__set(self.__i2c, self.__channel_list)
        self.get = self.__get(self.__i2c, self.__channel_list)
        self.select = self.__select(self.__i2c, self.__channel_list)

        return self

    def all_except(self, ch):
        channel_list = []
        if isinstance(ch, list):
            if not ch:
                channel_list = list(range(64))
                # print("empty list of channels in all_except()")
                # return self
            else:
                channel_list = list(range(64))
                for chi in ch:
                    channel_list.remove(chi)
        elif isinstance(ch, int):
            channel_list = list(range(64))
            channel_list.remove(ch)
        else:
            print("Unauthorized type for channel in method all_except()")
        self.__channel_list = channel_list
        # print(channel_list)
        self.enable = self.__enable(self.__i2c, self.__channel_list)
        self.disable = self.__disable(self.__i2c, self.__channel_list)
        self.set = self.__set(self.__i2c, self.__channel_list)
        self.get = self.__get(self.__i2c, self.__channel_list)
        self.select = self.__select(self.__i2c, self.__channel_list)

        return self

    def cluster(self, index):
        assert isinstance(index, int)
        assert index >= 0
        assert index < 5
        self.__channel_list = list(range(16 * index, 16 * (index + 1)))

        self.enable = self.__enable(self.__i2c, self.__channel_list)
        self.disable = self.__disable(self.__i2c, self.__channel_list)
        self.set = self.__set(self.__i2c, self.__channel_list)
        self.get = self.__get(self.__i2c, self.__channel_list)
        self.select = self.__select(self.__i2c, self.__channel_list)

        return self

    def group(self, channel_list):
        self.__channel_list = channel_list
        self.enable = self.__enable(self.__i2c, self.__channel_list)
        self.disable = self.__disable(self.__i2c, self.__channel_list)
        self.set = self.__set(self.__i2c, self.__channel_list)
        self.get = self.__get(self.__i2c, self.__channel_list)
        self.select = self.__select(self.__i2c, self.__channel_list)

        return self

    class __select:
        def __init__(self, i2c, ch):
            self.trigQ = self.__trigger_selector(i2c, ch, 6)
            self.trigTH = self.__trigger_selector(i2c, ch, 5)
            self.trigTL = self.__trigger_selector(i2c, ch, 4)
            self.Zin = self.__Zin(i2c, ch)
            self.analogProbe = self.__analogProbe(i2c, ch)

        class __Zin:
            def __init__(self, i2c, ch):
                self.__i2c = i2c
                self.__ch = ch

            def high(self):
                self.__i2c.set_bit_list(self.__ch, 0, 1, 1)

            def low(self):
                self.__i2c.set_bit_list(self.__ch, 0, 1, 0)

        class __analogProbe:
            # exclusive selection of 1 probe out of 4
            def __init__(self, i2c, ch):
                #  "Analog probe can only be enabled for one given channel (not a group/cluster/all channels)"
                if len(ch) == 1:
                    self.__ch = ch
                else:
                    self.__ch = None
                self.__i2c = i2c
                self.__analogProbe = None
                
            def __turn_off_previous_probe_enabled(self):
                if self.__analogProbe is not None:
                    address = self.__analogProbe
                    self.__i2c.write_register(address, 65, 0)

            def __call__(self, probe: str):
                assert probe in ['off', 'shH', 'shL', 'paLG', 'paHG']
                getattr(self, probe)()

            def off(self):
                if self.__ch is not None:
                    self.__i2c.set_bits_list(self.__ch, 65, 0, 8, 0)

            def shH(self):
                if self.__ch is not None:
                    self.__turn_off_previous_probe_enabled()
                    self.__i2c.set_bits_list(self.__ch, 65, 0, 8, 0b1000)
                    self.__analogProbe = self.__ch[0]

            def shL(self):
                if self.__ch is not None:
                    self.__turn_off_previous_probe_enabled()
                    self.__i2c.set_bits_list(self.__ch, 65, 0, 8, 0b0100)
                    self.__analogProbe = self.__ch[0]

            def paHG(self):
                if self.__ch is not None:
                    self.__turn_off_previous_probe_enabled()
                    self.__i2c.set_bits_list(self.__ch, 65, 0, 8, 0b0010)
                    self.__analogProbe = self.__ch[0]

            def paLG(self):
                if self.__ch is not None:
                    self.__turn_off_previous_probe_enabled()
                    self.__i2c.set_bits_list(self.__ch, 65, 0, 8, 0b0001)
                    self.__analogProbe = self.__ch[0]

        class __trigger_selector:
            def __init__(self, i2c, ch, bit):
                self.__i2c = i2c
                self.__ch = ch
                self.__bit = bit

            def internal(self):
                self.__i2c.set_bit_list(self.__ch, 8, self.__bit, 0)

            def external(self):
                self.__i2c.set_bit_list(self.__ch, 8, self.__bit, 1)

    class __enable:
        def __init__(self, i2c, ch):
            self.__i2c = i2c
            self.__ch = ch
            
        def front_end_except_pdet(self):
            # charge / timing / discri

            self.__i2c.set_bits_list(self.__ch, 7, 0, 8, 0b11111111)
            self.__i2c.set_bits_list(self.__ch, 8, 2, 2, 0b11)
            self.inDac()

        def front_end(self):
            # charge / timing / discri
            self.__i2c.set_bits_list(self.__ch, 7, 0, 8, 0b11111111)
            self.__i2c.set_bits_list(self.__ch, 8, 0, 4, 0b1111)
            self.inDac()

        def charge(self):
            self.__i2c.set_bits_list(self.__ch, 7, 0, 2, 0b11)
            # self.paLG()
            # self.paHG()

            self.__i2c.set_bits_list(self.__ch, 8, 0, 4, 0b1111)
            # self.shLG()
            # self.shHG()
            # self.pdetHG()
            # self.pdetLG()

            # self.inDac()

        def timing(self):
            self.paT()
            # self.inDac()

        def all_discri(self):
            # TL / TH / TQ
            self.__i2c.set_bits_list(self.__ch, 7, 2, 3, 0b111)

        def discri(self, gain):
            if gain == 1:   # low
                self.TL()
            elif gain == 2: # high
                self.TH()

        def TQ(self):
            self.__i2c.set_bit_list(self.__ch, 7, 2, 1)

        def TH(self):
            self.__i2c.set_bit_list(self.__ch, 7, 3, 1)

        def TL(self):
            self.__i2c.set_bit_list(self.__ch, 7, 4, 1)

        def tdcL(self):
            self.__i2c.set_bit_list(self.__ch, 7, 7, 1)

        def tdcH(self):
            self.__i2c.set_bit_list(self.__ch, 7, 6, 1)

        def use_ctest(self):
            self.__i2c.set_bit_list(self.__ch, 0, 3, 1)

        def inDac(self):
            self.__i2c.set_bit_list(self.__ch, 0, 2, 1)

        def cmd_test(self):
            self.__i2c.set_bit_list(self.__ch, 0, 0, 1)

        def paT(self):
            self.__i2c.set_bit_list(self.__ch, 7, 5, 1)

        def paLG(self):
            self.__i2c.set_bit_list(self.__ch, 7, 1, 1)

        def paHG(self):
            self.__i2c.set_bit_list(self.__ch, 7, 0, 1)

        def shLG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 3, 1)

        def shHG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 2, 1)

        def pdetLG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 1, 1)

        def pdetHG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 0, 1)

    class __disable:

        def __init__(self, i2c, ch):
            self.__i2c = i2c
            self.__ch = ch
            # add=ch, subaddr=7, msb to lsb: EN_tdc_low,EN_tdc_high,EN_paT,maskTLn,maskTHn,maskTQn,EN_paLG,EN_paHG
            # add=ch, subaddr=8, msb to lsb: NC*2,sel_ext_TrigQ,sel_ext_TrigT_H,sel_ext_TrigT_L,EN_shLG,EN_shHG,EN_pdetLG,EN_pdetHG

        def front_end_except_pdet(self):
            # charge / timing / discri
            self.__i2c.set_bits_list(self.__ch, 7, 0, 8, 0)
            self.__i2c.set_bits_list(self.__ch, 8, 2, 2, 0)
            self.inDac()

        def front_end(self):
            # print(self.__ch)
            # charge / timing / discri
            self.__i2c.set_bits_list(self.__ch, 7, 0, 8, 0)
            self.__i2c.set_bits_list(self.__ch, 8, 0, 4, 0)
            self.inDac()

        def charge(self):
            self.__i2c.set_bits_list(self.__ch, 7, 0, 2, 0)
            # self.paLG()
            # self.paHG()

            self.__i2c.set_bits_list(self.__ch, 8, 0, 4, 0)
            # self.shLG()
            # self.shHG()
            # self.pdetHG()
            # self.pdetLG()

        def timing(self):
            self.paT()

        def all_discri(self):
            # TL / TH / TQ
            self.__i2c.set_bits_list(self.__ch, 7, 2, 3, 0)

            # save i2c instructions rather than :
            # self.TL()
            # self.TH()
            # self.TQ()

        def discri(self, gain):
            if gain == 1:   # low
                self.TL()
            elif gain == 2: # high
                self.TH()

        def TQ(self):
            self.__i2c.set_bit_list(self.__ch, 7, 2, 0)

        def TH(self):
            self.__i2c.set_bit_list(self.__ch, 7, 3, 0)

        def TL(self):
            self.__i2c.set_bit_list(self.__ch, 7, 4, 0)

        def use_ctest(self):
            self.__i2c.set_bit_list(self.__ch, 0, 3, 0)

        def inDac(self):
            self.__i2c.set_bit_list(self.__ch, 0, 2, 0)

        def cmd_test(self):
            self.__i2c.set_bit_list(self.__ch, 0, 0, 0)

        def tdcL(self):
            self.__i2c.set_bit_list(self.__ch, 7, 7, 0)

        def tdcH(self):
            self.__i2c.set_bit_list(self.__ch, 7, 6, 0)

        def paT(self):
            self.__i2c.set_bit_list(self.__ch, 7, 5, 0)

        def paLG(self):
            self.__i2c.set_bit_list(self.__ch, 7, 1, 0)

        def paHG(self):
            self.__i2c.set_bit_list(self.__ch, 7, 0, 0)

        def shLG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 3, 0)

        def shHG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 2, 0)

        def pdetLG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 1, 0)

        def pdetHG(self):
            self.__i2c.set_bit_list(self.__ch, 8, 0, 0)

    class __set:
        def __init__(self, i2c, ch):
            self.__i2c = i2c
            self.__ch = ch

        def inDac(self, value_8b):
            """" value_8b: 8 bits / max 255 """
            # self.__i2c.write_register_list(self.__ch, 1, value_8b)
            self.__i2c.set_bits_list(self.__ch, 1, 0, 8, value_8b)

        def patComp(self, value_2b):
            assert value_2b >= 0
            assert value_2b < 2**2
            self.__i2c.set_bits_list(self.__ch, 2, 6, 2, value_2b)

        def patGain(self, value_6b):
            assert value_6b > 0
            assert value_6b < 2**6
            self.__i2c.set_bits_list(self.__ch, 2, 0, 6, value_6b)

        def palgGain(self, value_4b):
            assert value_4b > 0
            assert value_4b < 16
            self.__i2c.set_bits_list(self.__ch, 3, 4, 4, value_4b)

        def pahgGain(self, value_4b):
            assert value_4b > 0
            assert value_4b < 16
            self.__i2c.set_bits_list(self.__ch, 3, 0, 4, value_4b)

        def tauHG(self, value_4b):
            assert value_4b > 0
            assert value_4b < 16
            self.__i2c.set_bits_list(self.__ch, 4, 0, 4, value_4b)

        def tauLG(self, value_4b):
            assert value_4b > 0
            assert value_4b < 16
            self.__i2c.set_bits_list(self.__ch, 4, 4, 4, value_4b)

        def calibDACT1(self, value_6b):
            self.__i2c.set_bits_list(self.__ch, 5, 0, 6, value_6b)

        def calibDACT2(self, value_6b):
            self.__i2c.set_bits_list(self.__ch, 6, 0, 6, value_6b)

        def calibDACTx(self, discri, value_6b):
            if (discri == 1) or ('1' in discri):
                self.calibDACT1(value_6b)
            elif (discri == 2) or '2' in discri:
                self.calibDACT2(value_6b)
            else:
                print('Unknown discriminator for calibDAC6b')
                exit(0)

    class __get:
        def __init__(self, i2c, ch):
            self.__i2c = i2c
            self.__ch = ch

        def calibDACT2(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get(ch, 6))
            return res

        def calibDACT1(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get(ch, 5))
            return res

        def tauLG(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get_bits(ch, 4, 0, 4))
            return res

        def tauHG(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get_bits(ch, 4, 4, 4))
            return res

        def pahgGain(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get_bits(ch, 3, 0, 4))
            return res

        def palgGain(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get_bits(ch, 3, 4, 4))
            return res

        def patGain(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get_bits(ch, 2, 0, 6))
            return res

        def patComp(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get_bits(ch, 2, 6, 6))
            return res

        def inDac(self):
            res = []
            for ch in self.__ch:
                res.append(self.__i2c.get(ch, 1))
            return res
