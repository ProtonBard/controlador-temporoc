import argparse
import importlib

import pandas as pd
from alive_progress import alive_bar
import yaml

from analyse.ana_energy_spectrum_multi_ch import plot_22Na_spectrum
from analyse.common_analysis import *
from src.utils import *
from src.CONSTANTS import get_ASIC_ch
from src.common_setup import *
from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *

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


board_config_example = {'SiPM_model': 'Hamamatsu_S13361_6597',

            # SiPM_model is defined for memory, as well as channel mapping between SiPM and ASIC channels in CONSTANTS.py

                           'SiPM_breakdown': 52.5, 'target_hv': 57,
                           'CAEN_serial_number': 'AI05VLCGA', # 'A5071TERA',

            # Parameters used when controlling the CAEN HV external module.

                           'light_source': 'LYSO_monolithic_hexa', #'LYSO_3x3x10',

            # Analysis algo is tuned based on the light source : crystal, laser, dark noise only, etc.

                            'dacTL': 200, 'dacTH': 200,

            # Time discriminator global threshold (ASIC-wise) for low and high
            # Range : 0 - 1023

                            'calib_time_discri': True,      # Channel-wise calibration of time discriminator

            # Tuning value is given in file config/TEMPOROC/B*_calib_discri.csv for each channel.

            # Once "TL" (time low) discri thresholds are aligned between channels, tune only dacTL global value.
            # Pedestal value is given in file config/TEMPOROC/B*_calib_discri.csv for each channel :
            # If channels perfectly aligned, then should be exactly the same value in each channel, but
            #                 it is a known limitation of this current ASIC version
            # For board B4I, pedestal is around 180.
            # Running a staircase, you can identify the SiPM gain and the corresponding dacTL value for 1/2/... pe.
            # Once this dacTL value is set, only charge above this threshold will trigger the ASIC.
            # You can start with dacTL = 210 for B4 : you'll miss very low energy pe but you won't be annoyed by noise,
            # triggering constantly the ASIC.

                           'patgain': 63,
            # ASIC time preamplifier gain: small value = large gain, range = [1;63]

                           'palgGain': 15, 'pahgGain': 1,
            # ASIC preamplifier gain for the low/high gain shaper
            # (high and low gain energy measurement are different by a factor 10)
            # Range 0 - 14 (max = 14 = highest gain)

                            'tauLG': 2, 'tauHG': 2,
            # Shaper peaking time : ~20 ns per unit
            # Range 1-15 (max = 15 = longest integration time)

                            'tdc_injected': [['low', 'high']],

                            'dacTQ': 500,
            # ASIC charge discriminator threshold (no channel-wise tunning) on the low-gain shaper
            # Trigger will be delayed

                            'charge_filter': False,
            # FPGA setting to use the ASIC charge trigger (TQ) on the fly during deserialisation
            # to discard data if the charge seen by the ASIC is not above the threshold fixed internally.

                            'deserialiser_time': 0,
            # FPGA setting when receiving frames from ASIC to delete on-the-fly duplicated frames due to error in the
            # digital core of Temporoc2
            # Any frame following one by less than 2200 clock units is discarded and not stored in the FPGA fifo for this given cluster

                            'enabled_ASIC_ch': [list(range(64))], 'enable_TL_ASIC_ch': [list(range(64))],
                            # 'enabled_ASIC_ch': [[1]], 'enable_TL_ASIC_ch':[[1]],

            # List of channels enabled (powered-on) and with discriminator low (TL) enabled

                           'calib_inDAC': False}

            # inputDAC is not needed if the SiPM is not DC connected to the ASIC channel input. (ac-coupled + signal buffered & amplified externally)
            # Thus, no DC correction can be applied (channel wise).

def acquire_Na22_spectrum(board, output_folder=None, Nevents=10000, with_HV_control=False):
    Nevents = int(Nevents)

    config = {'board': [board],
              'config_B%d' % board: {'mode': 'master', 'board': board},
              'test': 'Energy spectrum with multiple channels'}


    config['config_B%d' % board].update(board_config_example)

    # Build default folder name
    if output_folder is None:
        output_folder = f"../output/{board_config_example['SiPM_model']}/Na22_spectra/{board_config_example['light_source']}/"

    new_index, local_output_dir = find_new_folder_index(output_folder, config)

    tempo = temporoc3(config, mode='master')

    if with_HV_control:
        # Turn ON HV CAEN (external module)
        tempo.hv.connect()

    # Setup TEMPOROC board
    setup_temporoc([tempo], config)

    tempo.asic.interface.set.nb_trigger(1)
    tempo.asic.interface.en.analog_probe()
    tempo.asic.ch(1).select.analogProbe.off()
    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT2_select.digit_probe()
    # tempo.asic.common.probeDig.channel(1).TrigT_L()
    # tempo.asic.interface.select.dig_modeRO.lg_adc_low_tdc()
    tempo.asic.common.set.event_window_length(2**6-1)
    tempo.asic.common.set.shaper_delay_length(2**5-1)
    # tempo.asic.common.en.FallingEdgeDetectorH()

    # Load extra custom config
    load_config([tempo], config)

    # TQ filter
    tempo.asic.common.en.TQ()
    tempo.asic.interface.dis.trigger_charge_inh() # take into account TQ
    tempo.asic.interface.en.trigger_charge_inh() # todo test
    tempo.asic.interface.en.sync_cluster()

    reset_FPGA_FIFO_and_tempo_digital([tempo])

    if with_HV_control:
        ## Acquire channel-wise analog pedestals seen by the ADC, WITHOUT SIGNAL
        acquire_pedestal(config, tempo)
        tempo.hv.turn_on_slowly()
        tempo.hv.wait_setpoint_reached()
        pass

    # for TQ_thresh in [0,50]: #range(0, 1023, 100):
    #     tempo.asic.common.set.dacTQ(TQ_thresh)
    #     time.sleep(0.1)
    #     acquire_data_multi_boards_safe(Nevents, config, [tempo], measure_label='_22Na_TQ_%d'%TQ_thresh)
    acquire_data_multi_boards_safe(Nevents, config, [tempo], measure_label='_22Na')

    tempo.close()
    return local_output_dir

def acquire_pedestal(config, master: temporoc3):
    print("Acquiring data to estimate pedestal position [adc]")

    # ALTER temporarly initial configuration
    master.asic.ch.group(master.board_config['enable_TL_ASIC_ch'][0]).disable.TL()
    master.deserializer.filter.disable.charge()

    # CHECK HV switched OFF
    master.hv.wait_setpoint_reached(0)

    # ACQUIRE
    master.fpga.set.conv_syst_ASIC(1)  # force event conversion
    time.sleep(1)
    master.fpga.set.conv_syst_ASIC(0)

    acquire_data_multi_boards(200, config, [master], measure_label='_pedestal')

    # BACK to initial configuration
    master.asic.ch.group(master.board_config['enable_TL_ASIC_ch'][0]).enable.TL()
    if master.board_config['charge_filter']:
        master.deserializer.filter.enable.charge()


def sweep_config(config, tempo: temporoc3):

    config['swept_hv_voltage'] = []
    config['swept_palgGain'] = []
    config['swept_tauLG'] = []
    config['swept_patgain'] = []
    config['swept_delay_pdet'] = []

    # tempo.asic.ch.all().select.Zin.low()

    # tempo.asic.ch.group(ASIC_noisy_channels_list).disable.all_discri()

    # BIAS SIPM
    for hv_voltage in [57]: #[55, 56, 57, 58]:
        # print("Biasing SiPM to %.1f V"%(config['target_hv_voltage']))
        # hv.set_voltage_modulating_ramp(config['target_hv_voltage'], config['SiPM_breakdown'][config['SiPM_model']])
        # hv.set_voltage_modulating_ramp(hv_voltage, config['SiPM_breakdown'][config['SiPM_model']])
        tempo.hv.set_voltage(hv_voltage)
        time.sleep(2)
        print(tempo.hv.measure_SiPM_HV())
        time.sleep(2)
        print(tempo.hv.measure_SiPM_HV())
        time.sleep(2)
        print(tempo.hv.measure_SiPM_HV())
        time.sleep(2)
        print(tempo.hv.save_periodically_SiPM_HV())

        for palgGain in [4, 7, 9, 11, 15]: #, 12, 15]: #[15]: #
            tempo.asic.ch.all().set.palgGain(palgGain)

            for tauLG in [2, 1, 4]: #[1, 4, 8, 15]:
                tempo.asic.ch.all().set.tauLG(tauLG)

                shaping_time = tauLG*20 # ns
                delay_pdet = int(2*shaping_time/3.55)  # lsb = 3.55 ns/lsb if slopeTrim = 4
                tempo.asic.common.set.delay_pdet(delay_pdet)
                # code 12 = 43 ns  good for tau = 1 = 20 ns  to avoid pile up

                for patgain in [32, 20]:
                    tempo.asic.ch.all().set.patGain(patgain)

                    config['swept_hv_voltage'].append(hv_voltage)
                    config['swept_palgGain'].append(palgGain)
                    config['swept_tauLG'].append(tauLG)
                    config['swept_patgain'].append(patgain)
                    config['swept_delay_pdet'].append(delay_pdet)

                    print('hv_voltage', hv_voltage, 'palgGain', palgGain, 'tauLG', tauLG, 'patgain', patgain, 'delay_pdet', delay_pdet)
                    save_config_file(config)

                    ## SAVE SPECTRUM
                    print("Acquiring data : radioactive source spectrum")
                    events_received = 0
                    Nevents = 50000
                    tempo.fpga.reset.tpr_digital()
                    tempo.deserializer.reset_fifo_for_all_cluster()
                    time.sleep(0.5)

                    init_start = time.perf_counter()
                    all_event_counts_equal_total = 0
                    loop = 0
                    csv_file_list = [config['save_folder'] + "B%d_cluster_%d_22Na_HV_%.1f_palgGain_%d_tauLG_%d_patgain_%d.csv" % (tempo.board, cluster, hv_voltage, palgGain, tauLG, patgain) for cluster in range(4)]
                    # with alive_bar(Nevents, force_tty=True) as bar:  # your expected total
                    if 1:
                        while events_received < Nevents:
                            loop += 1
                            # time.sleep(0.5)
                            start = time.perf_counter()
                            events_extracted_list = tempo.deserializer.extract_all(csv_file_list, config)
                            all_event_counts_equal = events_extracted_list.count(events_extracted_list[0]) == len(events_extracted_list)
                            all_event_counts_equal_total += int(all_event_counts_equal)
                            events_received_min = min(events_extracted_list)
                            events_received += events_received_min
                            if events_received_min > 0:
                                # bar(events_received_min)
                                stop = time.perf_counter()
                                print("events : %d  %s  %d rate : %d/s   averaged rate %d/s" % (events_received, str(all_event_counts_equal), events_received_min, events_received_min / (stop - start), events_received / (stop - init_start)))
                            else:
                                # no events => wait to accumulate (otherwise USB errors because too quick consecutive requests)
                                time.sleep(0.1)
                    config['rate'].append(events_received / (stop - init_start))
                    config['all_event_counts_equal_ratio']=all_event_counts_equal_total/loop
                    tempo.save_ASIC_and_FPGA_config(config)

    tempo.close()
    print("Done")



if __name__ == '__main__':
    search_folder = acquire_Na22_spectrum(4)
    # root_folder = "../output/"
    # shutil.copyfile(root_folder + '/Hamamatsu_single/Na22_spectra/LYSO_3x3x10/37/raw/B6_master_cluster_0_pedestal.csv', search_folder+'B6_master_cluster_0_pedestal.csv')
    # plot_22Na_spectrum(root_folder, search_folder)

