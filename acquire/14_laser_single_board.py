import time

import ftd2xx
import pandas as pd
import matplotlib.pyplot as plt
import math
import os
import numpy as np

from src.utils import *
import uiroc.device as device
from src.common_setup import *
from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *


from datetime import datetime

def setup_laser_single_board(Nevents=100000.0):
    Nevents = int(Nevents)

    config = {'save_folder': [], 'tempo_dig_ck': 80, 'readout_mode': [],
              'step': 0, 'restart_from_last_step': False, 'board': [1],
              'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
              'current_time': [], 'log': [], 'start_time': 0, 'coincidence_rate': 0, 'debug': []}

    config['config_B1'] = {'mode': 'master', 'board': 1, 'SiPM_model': 'Hamamatsu_S13361_6597',
                           'SiPM_breakdown': 52.5,
                           'CAEN_serial_number': 'AL04WEE3A', 'light_source': 'pilas_laser',
                           'patgain': 4, 'dacTH': 1023, 'dacTL': 1023, 'dacTQ': 600, 'charge_filter': False,
                           'palgGain': 1, 'tauLG': 15, 'target_hv': 56, 'tdc_injected': [['low', 'high']],
                           'deserialiser_time': 2200, 'enabled_TH_fb': False,
                           'enable_TL_ASIC_ch': [42],
                           'calib_time_discri': False, 'calib_inDAC': False, 'VDDD': 1.34}

    local_output_dir = "../output/Hamamatsu/laser/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    master = temporoc3(config)
    master.hv.connect()
    master.hv.turn_on()

    # hv.set_voltage_modulating_ramp(hv_voltage, config['SiPM_breakdown'][config['SiPM_model']])

    # time.sleep(3)
    # for i in range(3):
    #     time.sleep(2)
    #     print(slave.hv.measure_SiPM_HV(), end='\t\t\t\t')
    #     print(master.hv.measure_SiPM_HV(), end='\n')

    # time.sleep(2)
    # print(master.hv.save_periodically_SiPM_HV(), end='\n')

    master.hv.wait_setpoint_reached()

    setup_temporoc([master], config, laser=True)

    acquire_data_multi_boards_safe(Nevents, config, [master])

    master.close()


if __name__ == "__main__":
    setup_laser_single_board(Nevents=100000)