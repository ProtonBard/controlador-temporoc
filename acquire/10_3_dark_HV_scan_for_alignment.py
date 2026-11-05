import argparse
import importlib

import pandas as pd
from alive_progress import alive_bar
import yaml

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


from datetime import datetime


def acquire_Na22_spectrum(Nevents=100000):
    Nevents = int(Nevents)

    config = {
        "board": [2],
        "save_folder": [],
        "tempo_dig_ck": 80,
        "readout_mode": [],
        "step": 0,
        "restart_from_last_step": False,
        "FPGA": [],
        "fw_version_major": [],
        "fw_version_minor": [],
        "fw_hash": [],
        "current_time": [],
        "log": [],
        "start_time": 0,
        "coincidence_rate": 0,
        "debug": [],
    }

    # config["config_B2"] = {
    #     "mode": "master",
    #     "board": 2,
    #     "SiPM_model": "Hamamatsu_S13361_6597",
    #     "SiPM_breakdown": 52.5,
    #     "CAEN_serial_number": "AL04WEE3A",
    #     "light_source": "CeBr3_quartz_encapsulated",
    #     "patgain": 32,
    #     "dacTH": 1023,
    #     "dacTL": 1023,
    #     "dacTQ": 600,
    #     "charge_filter": False,
    #     "palgGain": 9,
    #     "tauLG": 2,
    #     "target_hv": 57,
    #     "tdc_injected": [["low", "high"]],
    #     "nb_trigger": 1,
    #     "deserialiser_time": 2200,
    #     "enabled_TH_fb": False,
    #     "power_cluster": [0, 1, 2, 3],
    #     "enable_TL_ASIC_ch": list(range(64)),
    #     "delay_pdet": 60,
    #     "calib_TL": True,
    #     "calib_inDAC": True,
    #     "VDDD": 1.34,
    # }

    config["config_B2"] = {
        "mode": "master",
        "board": 2,
        "SiPM_model": "Broadcom_S4N44P164M",
        "SiPM_breakdown": 33,
        "CAEN_serial_number": "AL04WEE3A",
        "light_source": "CeBr3_quartz_encapsulated",
        "patgain": 63,
        "dacTH": 1023,
        "dacTL": 1023,
        "dacTQ": 600,
        "charge_filter": False,
        "palgGain": 9,
        "tauLG": 2,
        "target_hv": 43,
        "tdc_injected": [["low", "high"]],
        "nb_trigger": 1,
        "deserialiser_time": 2200,
        "enabled_TH_fb": True,
        "power_cluster": [0, 1, 2, 3],
        "enable_TL_ASIC_ch": list(range(64)),
        "delay_pdet": 60,  # [43]
        "calib_TL": True,
        "calib_inDAC": False,
        "VDDD": 1.34,
    }

    local_output_dir = "../output/Broadcom/Na22_spectra/CeBr3_quartz_encapsulated/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    master = temporoc3(config, mode="master")
    master.hv.connect()

    setup_temporoc([master], config)

    reset_FPGA_FIFO_and_tempo_digital([master])

    ## Acquire channel-wise analog pedestals seen by the ADC, WITHOUT SIGNAL
    acquire_pedestal(config, master)

    master.hv.turn_on_slowly()

    # time.sleep(3)
    # for i in range(3):
    #     time.sleep(2)
    #     print(slave.hv.measure_SiPM_HV(), end='\t\t\t\t')
    #     print(master.hv.measure_SiPM_HV(), end='\n')

    # time.sleep(2)
    # print(master.hv.save_periodically_SiPM_HV(), end='\n')
    master.hv.wait_setpoint_reached()

    acquire_data_multi_boards_safe(Nevents, config, [master], measure_label="_22Na")


def acquire_pedestal(config, master: temporoc3):
    print("Acquiring data to estimate pedestal position [adc]")

    # ALTER temporarly initial configuration
    master.asic.ch.group(master.board_config["injected_channel"][0]).disable.TL()
    master.deserializer.filter.disable.charge()

    # CHECK HV switched OFF
    time.sleep(2)
    print(master.hv.measure_SiPM_HV())
    # time.sleep(2)
    # print(master.hv.measure_SiPM_HV())
    # time.sleep(2)
    # print(master.hv.measure_SiPM_HV())

    # ACQUIRE
    csv_file_list = [
        config["save_folder"] + "B%d_cluster_%d_pedestal.csv" % (master.board, cluster)
        for cluster in range(4)
    ]
    with alive_bar(234, force_tty=True) as bar:  # your expected total
        # force event conversion
        for i in range(151):
            master.fpga.conv_syst_ASIC(1)
            master.fpga.conv_syst_ASIC(0)
            time.sleep(0.0001)

        events_extracted_list = master.deserializer.extract_all(
            csv_file_list, master.board_config
        )
        if min(events_extracted_list) > 0:
            bar(min(events_extracted_list))  # otherwise bar updates

    # BACK to initial configuration
    master.asic.ch.group(master.board_config["injected_channel"][0]).enable.TL()
    if master.board_config["charge_filter"]:
        master.deserializer.filter.enable.charge()


def sweep_config(config, tempo: temporoc3):

    config["swept_hv_voltage"] = []
    config["swept_palgGain"] = []
    config["swept_tauLG"] = []
    config["swept_patgain"] = []
    config["swept_delay_pdet"] = []

    # tempo.asic.ch.all().select.Zin.low()

    # tempo.asic.ch.group(ASIC_noisy_channels_list).disable.all_discri()

    # BIAS SIPM
    for hv_voltage in [57]:  # [55, 56, 57, 58]:
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
        print(tempo.hv.save_periodically_SiPM_HV(hv, config))

        for palgGain in [4, 7, 9, 11, 15]:  # , 12, 15]: #[15]: #
            tempo.asic.ch.all().set.palgGain(palgGain)

            for tauLG in [2, 1, 4]:  # [1, 4, 8, 15]:
                tempo.asic.ch.all().set.tauLG(tauLG)

                shaping_time = tauLG * 20  # ns
                delay_pdet = int(
                    2 * shaping_time / 3.55
                )  # lsb = 3.55 ns/lsb if slopeTrim = 4
                tempo.asic.common.set.delay_pdet(delay_pdet)
                # code 12 = 43 ns  good for tau = 1 = 20 ns  to avoid pile up

                for patgain in [32, 20]:
                    tempo.asic.ch.all().set.patGain(patgain)

                    config["swept_hv_voltage"].append(hv_voltage)
                    config["swept_palgGain"].append(palgGain)
                    config["swept_tauLG"].append(tauLG)
                    config["swept_patgain"].append(patgain)
                    config["swept_delay_pdet"].append(delay_pdet)

                    print(
                        "hv_voltage",
                        hv_voltage,
                        "palgGain",
                        palgGain,
                        "tauLG",
                        tauLG,
                        "patgain",
                        patgain,
                        "delay_pdet",
                        delay_pdet,
                    )
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
                    csv_file_list = [
                        config["save_folder"]
                        + "B%d_cluster_%d_22Na_HV_%.1f_palgGain_%d_tauLG_%d_patgain_%d.csv"
                        % (tempo.board, cluster, hv_voltage, palgGain, tauLG, patgain)
                        for cluster in range(4)
                    ]
                    # with alive_bar(Nevents, force_tty=True) as bar:  # your expected total
                    if 1:
                        while events_received < Nevents:
                            loop += 1
                            # time.sleep(0.5)
                            start = time.perf_counter()
                            events_extracted_list = tempo.deserializer.extract_all(
                                csv_file_list, config
                            )
                            all_event_counts_equal = events_extracted_list.count(
                                events_extracted_list[0]
                            ) == len(events_extracted_list)
                            all_event_counts_equal_total += int(all_event_counts_equal)
                            events_received_min = min(events_extracted_list)
                            events_received += events_received_min
                            if events_received_min > 0:
                                # bar(events_received_min)
                                stop = time.perf_counter()
                                print(
                                    "events : %d  %s  %d rate : %d/s   averaged rate %d/s"
                                    % (
                                        events_received,
                                        str(all_event_counts_equal),
                                        events_received_min,
                                        events_received_min / (stop - start),
                                        events_received / (stop - init_start),
                                    )
                                )
                            else:
                                # no events => wait to accumulate (otherwise USB errors because too quick consecutive requests)
                                time.sleep(0.1)
                    config["rate"].append(events_received / (stop - init_start))
                    config["all_event_counts_equal_ratio"] = (
                        all_event_counts_equal_total / loop
                    )
                    tempo.save_ASIC_and_FPGA_config(config)

    hv.close()
    tempo.close()
    print("Done")


def scan_HV(Nevents=100000, hv_range=(30, 45), n_steps=10):
    Nevents = int(Nevents)
    n_steps = int(n_steps)

    config = {
        "board": [2],
        "save_folder": [],
        "tempo_dig_ck": 80,
        "readout_mode": ["lg_adc"],
        "step": 0,
        "restart_from_last_step": False,
        "FPGA": [],
        "fw_version_major": [],
        "fw_version_minor": [],
        "fw_hash": [],
        "current_time": [],
        "log": [],
        "start_time": 0,
        "coincidence_rate": 0,
        "debug": [],
    }

    # config["config_B2"] = {
    #     "mode": "master",
    #     "board": 2,
    #     "SiPM_model": "Hamamatsu_S13361_6597",
    #     "SiPM_breakdown": 52.5,
    #     "CAEN_serial_number": "AL04WEE3A",
    #     "light_source": "CeBr3_quartz_encapsulated",
    #     "patgain": 32,
    #     "dacTH": 1023,
    #     "dacTL": 1023,
    #     "dacTQ": 600,
    #     "charge_filter": False,
    #     "palgGain": 9,
    #     "tauLG": 2,
    #     "target_hv": 57,
    #     "tdc_injected": [["low", "high"]],
    #     "nb_trigger": 1,
    #     "deserialiser_time": 2200,
    #     "enabled_TH_fb": False,
    #     "power_cluster": [0, 1, 2, 3],
    #     "enable_TL_ASIC_ch": list(range(64)),
    #     "delay_pdet": 60,
    #     "calib_TL": True,
    #     "calib_inDAC": True,
    #     "VDDD": 1.34,
    # }

    config["config_B2"] = {
        "mode": "master",
        "board": 2,
        "SiPM_model": "Broadcom_S4N44P164M",
        "SiPM_breakdown": 33,
        "CAEN_serial_number": "AL04WEE3A",
        "light_source": "CeBr3_quartz_encapsulated",
        "patgain": 63,
        "dacTH": 1023,
        "dacTL": 1023,
        "dacTQ": 600,
        "charge_filter": False,
        "palgGain": 9,
        "tauLG": 2,
        "target_hv": hv_range[0],
        "tdc_injected": [["low", "high"]],
        "nb_trigger": 1,
        "deserialiser_time": 2200,
        "enabled_TH_fb": True,
        "power_cluster": [0, 1, 2, 3],
        "enable_TL_ASIC_ch": list(range(64)),
        "delay_pdet": 60,  # [43]
        "calib_TL": True,
        "calib_inDAC": False,
        "VDDD": 1.34,
    }
    config['config_B2']["palgGain_ch"] = [9] * 64

    scan_values = np.linspace(hv_range[0], hv_range[1], n_steps)
    scan_values = np.round(scan_values, 2)

    local_output_dir = "../output/Broadcom/Na22_spectra/CeBr3_quartz_encapsulated/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    master = temporoc3(config, mode="master")
    master.hv.connect()

    setup_temporoc([master], config)

    reset_FPGA_FIFO_and_tempo_digital([master])

    ## Acquire channel-wise analog pedestals seen by the ADC, WITHOUT SIGNAL
    acquire_pedestal(config, master)

    master.hv.turn_on_slowly()
    master.hv.wait_setpoint_reached()
    time.sleep(2)
    master.fpga.conv_syst_ASIC(1)

    for inDacVal in [0, 255]:
        config['config_B2']["inDac"] = [inDacVal] * 64

        for ch, dac in enumerate(config['config_B2']["inDac"]):
            master.asic.ch(ch).set.inDac(dac)

        for hv_voltage in scan_values:
            new_index_step, local_output_dir_step = find_new_folder_index(
                local_output_dir, config
            )
            config["config_B2"]["target_hv"] = float(hv_voltage)
            master.hv.turn_on_slowly()
            # master.hv.set_voltage(hv_voltage)
            time.sleep(2)
            master.hv.wait_setpoint_reached()
            time.sleep(2)

            measured_I_before, measured_V_before = master.hv.get_IV()
            config["config_B2"]["measured_I_before"] = measured_I_before
            config["config_B2"]["measured_V_before"] = measured_V_before

            acquire_data_multi_boards_safe(Nevents, config, [master], measure_label="_22Na")

            # measured_I_after, measured_V_after = master.hv.get_IV()
            # config["config_B2"]["measured_I_after"] = measured_I_after
            # config["config_B2"]["measured_V_after"] = measured_V_after



    master.fpga.conv_syst_ASIC(0)

    master.close()

if __name__ == "__main__":
    # acquire_Na22_spectrum()
    scan_HV(
        Nevents=5000,
        hv_range=(25., 48.),
        n_steps=40,
    )

    # m = importlib.import_module('analyse.10_ana_Na22_spectrum_multi_ch', package=None)
    # root_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    # folder = root_folder + "Hamamatsu/Na22_spectra/full_segmented_alu_coated_LYSO/"
    # i = m.find_latest_folder_index(folder)
    # m.plot_22Na_spectrum(folder + "%d/raw/" % i)
    # m = importlib.import_module('7_2_coincidence_dual_board', package=None)
    # m.coincidence_Na22_dual_boards()
