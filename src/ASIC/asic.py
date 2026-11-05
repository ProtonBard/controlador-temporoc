import src.CONSTANTS
from uiroc.i2c import i2c
from src.ASIC.bias import bias
from src.ASIC.channel import channel
from src.ASIC.common import common
from src.ASIC.interface import interface

import pandas as pd


class asic:

    def __init__(self, dev, SC_config_file, chipID=1):
        self.dev = dev

        df_i2c = pd.read_csv(SC_config_file, index_col=None, dtype={"add": int, "subadd": int, "data": str})
        self.i2c = i2c(dev, df_i2c, chipID)

        self.ch = channel(self.i2c)
        self.bias = bias(self.i2c)
        self.common = common(self.i2c)
        self.interface = interface(self.i2c)

