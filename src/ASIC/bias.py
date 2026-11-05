class I:
    def __init__(self, i2c, addr, subaddr, bit_offset_lsb, bit_size):
        self.__i2c = i2c
        self.__addr = addr
        self.__subaddr = subaddr
        self.__bit_size = bit_size
        self.__bit_offset_lsb = bit_offset_lsb

    def set_4b(self, value_4b):
        assert value_4b>=0
        assert value_4b<2**4
        # print("set_4b ", self.__addr, self.__subaddr, self.__bit_size, self.__bit_offset_lsb, value)
        self.__i2c.set_bits(self.__addr, self.__subaddr, self.__bit_offset_lsb, self.__bit_size, value_4b)

    def get(self):
        value = self.__i2c.get_bits(self.__addr, self.__subaddr, self.__bit_offset_lsb, self.__bit_size)
        # print("get_4b ", self.__addr, self.__subaddr, self.__bit_size, self.__bit_offset_lsb, value)
        return value


class bias:

    def __init__(self, i2c):
        self.__i2c = i2c
        self.input = self.__inputDac(self.__i2c)
        self.calibDac = self.__calibDac(self.__i2c)
        self.pa = self.__preamplifier(self.__i2c)
        self.sh = self.__shaper(self.__i2c)
        self.pdet = self.__pdetector(self.__i2c)
        self.pdbuf = self.__pdbuffer(self.__i2c)
        self.discri = self.__discriminator(self.__i2c)

    def disable_timing(self):
        self.discri.TL.disable()
        self.discri.TH.disable()
        self.pa.T.disable()

    def enable_timing(self):
        self.discri.TL.enable()
        self.discri.TH.enable()
        self.pa.T.enable()

    def disable_charge(self):
        self.pa.HG.disable()
        self.pa.LG.disable()
        self.discri.Q.disable()
        self.sh.HG.disable()
        self.sh.LG.disable()
        self.pdet.disable()
        self.pdbuf.disable()

    def enable_charge(self):
        self.pa.HG.enable()
        self.pa.LG.enable()
        self.discri.Q.enable()
        self.sh.HG.enable()
        self.sh.LG.enable()
        self.pdet.enable()
        self.pdbuf.enable()

    # class __status:
    #     def __init__(self, addr, subaddr, bit_offset_lsb):
    #         self.__addr = addr
    #         self.__subaddr = subaddr
    #         self.__bit_offset_lsb = bit_offset_lsb
    #
    #     def enable(self):
    #         self.__i2c.set_bit(self.__addr, self.__subaddr, self.__bit_offset_lsb, 1)
    #
    #     def disable(self):
    #         self.__i2c.set_bit(self.__addr, self.__subaddr, self.__bit_offset_lsb, 0)

    class __inputDac:

        def __init__(self, i2c):
            self.__i2c = i2c
            self.DAC0 = self.__core(i2c, 0, 7)
            self.DAC1 = self.__core(i2c, 1, 6)

        class __core:
            def __init__(self, i2c, subaddr, bit_enable):
                self.__i2c = i2c
                self.__bit_enable = bit_enable
                self.Ibi = I(i2c, 64, subaddr, 0, 4)
                self.Ibo = I(i2c, 64, subaddr, 4, 4)

            def enable(self):
                self.__i2c.set_bit(64, 13, self.__bit_enable, 1)

            def disable(self):
                self.__i2c.set_bit(64, 13, self.__bit_enable, 0)

    class __calibDac:
        def __init__(self, i2c):
            self.__i2c = i2c
            self.Ib = I(i2c, 64, 2, 4, 4)

        def enable(self):
            self.__i2c.set_bit(64, 14, 4, 1)

        def disable(self):
            self.__i2c.set_bit(64, 14, 4, 0)

    class __preamplifier:
        """ 4 bits """

        def __init__(self, i2c):
            self.__i2c = i2c
            self.T = self.__core(i2c, 2, 4, 0, 5)
            self.HG = self.__core(i2c, 3, 4, 4, 4)
            self.LG = self.__core(i2c, 3, 4, 0, 3)

        class __core:
            def __init__(self, i2c, subaddr, bit_size, bit_offset_lsb, bit_enable):
                self.__i2c = i2c
                self.__bit_enable = bit_enable
                self.Ib = I(i2c, 64, subaddr, bit_offset_lsb, bit_size)

            def enable(self):
                self.__i2c.set_bit(64, 13, self.__bit_enable, 1)

            def disable(self):
                self.__i2c.set_bit(64, 13, self.__bit_enable, 0)

    class __shaper:
        def __init__(self, i2c):
            self.__i2c = i2c
            self.HG = self.__core(i2c, 4, 4, 2)
            self.LG = self.__core(i2c, 5, 4, 1)

        class __core:
            def __init__(self, i2c, subaddr, bit_size, bit_enable):
                self.__i2c = i2c
                self.__bit_enable = bit_enable
                self.Ibi = I(i2c, 64, subaddr, 4, bit_size)
                self.Ibo = I(i2c, 64, subaddr, 0, bit_size)

            def enable(self):
                self.__i2c.set_bit(64, 13, self.__bit_enable, 1)

            def disable(self):
                self.__i2c.set_bit(64, 13, self.__bit_enable, 0)

    class __pdetector:
        def __init__(self, i2c):
            self.__i2c = i2c
            self.Ibi = I(i2c, 64, 6, 4, 4)
            self.Ib_FCP = I(i2c, 64, 7, 4, 4)
            self.Ib_FCN = I(i2c, 64, 7, 0, 4)

        def enable(self):
            self.__i2c.set_bit(64, 13, 0, 1)

        def disable(self):
            self.__i2c.set_bit(64, 13, 0, 0)

    class __pdbuffer:
        def __init__(self, i2c):
            self.__i2c = i2c
            self.Ibi = I(i2c, 64, 6, 0, 4)
            self.Ib_FCP = I(i2c, 64, 8, 4, 4)
            self.Ib_FCN = I(i2c, 64, 8, 0, 4)

        def enable(self):
            self.__i2c.set_bit(64, 14, 2, 1)

        def disable(self):
            self.__i2c.set_bit(64, 14, 2, 0)

    class __discriminator:
        def __init__(self, i2c):
            self.__i2c = i2c
            self.TL = self.__discriT1(i2c)
            self.TH = self.__discriT2(i2c)
            self.Q = self.__discriQ(i2c)

        class __discriT1:
            def __init__(self, i2c):
                self.__i2c = i2c
                self.Ibi = I(i2c, 64, 9, 4, 4)
                self.Ibm1 = I(i2c, 64, 9, 0, 4)
                self.Ibm2 = I(i2c, 64, 10, 4, 4)

            def enable(self):
                self.__i2c.set_bit(64, 14, 1, 1)

            def disable(self):
                self.__i2c.set_bit(64, 14, 1, 0)

        class __discriT2:
            def __init__(self, i2c):
                self.__i2c = i2c
                self.Ibi = I(i2c, 64, 10, 0, 4)
                self.Ibm1 = I(i2c, 64, 11, 4, 4)
                self.Ibm2 = I(i2c, 64, 11, 0, 4)

            def enable(self):
                self.__i2c.set_bit(64, 14, 0, 1)

            def disable(self):
                self.__i2c.set_bit(64, 14, 0, 0)

        class __discriQ:
            def __init__(self, i2c):
                self.__i2c = i2c
                self.Ibi = I(i2c, 64, 12, 4, 4)
                self.Ibo = I(i2c, 64, 12, 0, 4)

            def enable(self):
                self.__i2c.set_bit(64, 14, 3, 1)

            def disable(self):
                self.__i2c.set_bit(64, 14, 3, 0)


