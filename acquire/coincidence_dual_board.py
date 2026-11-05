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

def coincidence_Na22_dual_boards(board_master, board_slave, local_output_dir, Nevents=100000):
    Nevents = int(Nevents)

    config = {'board': [board_master, board_slave],
              'config_B%d' % board_master: {'mode': 'master', 'board': board_master},
              'config_B%d' % board_slave: {'mode': 'slave', 'board': board_slave}}

    extra_config_example1 = {'SiPM_model': 'Hamamatsu_S13361_6597',
              'SiPM_breakdown': 52.5,
              'CAEN_serial_number': 'AL04WEE3A', 'light_source': 'full_segmented_alu_coated_LYSO',
              'patgain': 32, 'dacTH': 1023, 'dacTL': 1023, 'dacTQ': 400, 'charge_filter': True,
              'palgGain': 9, 'tauLG': 2, 'target_hv': 57, 'tdc_injected': [['low', 'high']],
              'deserialiser_time': 3300, 'enabled_TH_fb': True,
              'enable_TL_ASIC_ch': list(range(64)),
              'calib_time_discri': True, 'calib_inDAC': True}

    extra_config_example2 = {'SiPM_model': 'Hamamatsu_S13361_6597',
              'SiPM_breakdown': 52.5,
              'CAEN_serial_number': 'AI05VLCGA', 'light_source': '3x3x5mm_teflon_wrapped_LYSO',
              'patgain': 4, 'dacTH': 1023, 'dacTL': 800, 'dacTQ': 600, 'charge_filter': False,
              'palgGain': 1, 'tauLG': 15, 'target_hv': 57.5, 'tdc_injected': [['low', 'high']],
              'deserialiser_time': 2200, 'enabled_TH_fb': False,
              'enable_TL_ASIC_ch': [43],
              'calib_time_discri': False, 'calib_inDAC': False}

    for board in config['board']:
        config['config_B%d'%board].update(extra_config_example1)

    find_new_folder_index(local_output_dir, config)

    slave = temporoc3(config, mode='slave')
    master = temporoc3(config, mode='master')

    # Turn ON HV CAEN (external module)
    slave.hv.connect()
    # slave.hv.turn_on()
    slave.hv.turn_on_slowly()

    master.hv.connect()
    # master.hv.turn_on()
    master.hv.turn_on_slowly()

    # Setup both TEMPOROC boards
    setup_temporoc(master, config)
    setup_temporoc(slave, config)

    # Load extra custom config
    load_config([master, slave], config)

    # Launch measurement
    #but before check HV has reached target voltage
    slave.hv.wait_setpoint_reached()
    master.hv.wait_setpoint_reached()

    acquire_data_multi_boards_safe(Nevents, config, [master, slave])

    master.close()
    slave.close()


def save_temperature(tempo, config):
    config['temperature_'+tempo.mode].append(tempo.temperature_sensor.read_temperature())
    threading.Timer(60 * 30, save_temperature, args=(tempo, config)).start()


if __name__ == "__main__":
    output_dir = "../output/Hamamatsu/coincidence/3x3x5_vs_3x3x5_LYSO/"
    # output_dir = "../output/Hamamatsu/coincidence/3x3x5_vs_segm_alu_LYSO/"
    # output_dir = "../output/coincidence/22Na_digital/
    coincidence_Na22_dual_boards(5, 6, output_dir, Nevents=100000)


