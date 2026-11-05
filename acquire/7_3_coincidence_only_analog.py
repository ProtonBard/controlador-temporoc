import time

import ftd2xx
import pandas as pd
import matplotlib.pyplot as plt
import math
import os
import numpy as np

import src.utils
import uiroc.device as device
from src import tools
from src.common_setup import *
from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *
from src.tools import *

# OUTPUT unlatched trigger => TOT analysis possible
# DO NOT send 320/40 MHz clock to tempo
# DISABLE Temporoc readout
# DISABLE Temporoc clusters

from datetime import datetime

def setup_temporoc(serial_startswith, config, SiPM_channels_list):

    tempo = temporoc3(serial_startswith=serial_startswith)

    tempo.mode = config['board_to_mode'][tempo.board]
    print("Connecting "+tempo.mode+" as board %d"%tempo.board)

    ####  Setup coincidence
    # Mutual to every board:

    tempo.deserializer.filter.enable.coincidence_inter_asic()

    # Receive distant trigger (= End Of Frame)
    tempo.fpga.select.foreign_eof.input_clk1()

    # Share local trigger (= End Of Frame) to distant
    tempo.fpga.OUT3_select.eof_local()

    # Output coincidence flag to IO for scope debug
    tempo.fpga.OUT4_select.coincidence()

    if tempo.mode == 'master':

        # tempo.setup_coincidence_master_mode()

        # Select temporoc digital clock
        # tempo.fpga.set.PLL_as_clock_source()
        tempo.fpga.set.FPGA_as_clock_source()

        # Output clock to slave
        tempo.fpga.OUT7_select.ck_from_PLL_OUT3()

        # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
        tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

        # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
        tempo.fpga.select.ck_from_FPGA_to_ASIC.off()

        # Output reset to slave
        tempo.fpga.OUT2_select.resetn()

    elif tempo.mode == 'slave':

        # tempo.setup_coincidence_slave_mode()
        # Select temporoc digital clock
        tempo.fpga.set.FPGA_as_clock_source()
        # tempo.fpga.set.PLL_as_clock_source() #todo

        # Transmit temporoc digital clock from master to slave PLL
        tempo.fpga.select.ck_from_FPGA_to_PLL.input_clk2()

        # Transmit temporoc digital clock from master to slave CK MUX
        tempo.fpga.select.ck_from_FPGA_to_ASIC.off()

        # tempo..FPGA_IO.select.ck_towards_PLL.get_config()
        # tempo.FPGA_IO.select.ck_towards_FPGA.get_config()
        # switch off the PLL todo ?

        # IO FPGA 8 fixed to receive tpr_resetn from MASTER (or the other way around) in firmware
        tempo.fpga.enable_foreign_reset_enable()

    else:
        print("Unknown mode : either MASTER or SLAVE")

    tempo_dig_ck_freq = 40
    tempo.pll.flash("../config/PLL/Si5345_11%s_ck_%dMHz-Registers.txt" % (tempo.mode, tempo_dig_ck_freq), tempo_dig_clock=tempo_dig_ck_freq)

    # PLL outputs
    # 0 : FPGA clock : 80M
    # 3 : FPGA clock : 40M
    # 6 : TEMPOROC digital : 40M
    # 7 : external hit : 40M
    # 8 : standalone TDC ck : OFF

    # Expected PLL inputs
    # IN0 : 100M from cristal if MASTER
    # IN0 : 40M from MASTER PLL if SLAVE


    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_sync_ext_trigger()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_40M_dig_ck()  # for internal ADC so no cross talk on MUX
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_80M_dig_ck()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_160M_dig_ck()

    tempo_dig_ck.append(tempo_dig_ck_freq)

    tempo.reset_power_check_correct_clock_init()

    save_temperature(tempo, config)

    readout_mode = 'full_adc_tdc'  # ,'lg_adc_low_tdc', 'hg_adc_low_tdc']   #, 'low_high_tdc', 'low_tdc', ]:
    config['readout_mode'].append(readout_mode)
    tempo.asic.interface.select.dig_modeRO(readout_mode)

    tempo.correct_default_HW_SC()

    

    config['injected_channel_SiPM'].append(SiPM_channels_list)

    channels_list = get_ASIC_ch(SiPM_channels_list, config['SiPM_model'])

    clusters_list = np.unique(np.array(channels_list) // 16).tolist()
    src.utils.update_config_dict(config, clusters_list)
    tempo.asic.ch.all_except(channels_list).disable.front_end_except_pdet()
    # tempo.asic.ch.all_except(channels_list).disable.front_end()

    patgain = 10
    for channel in channels_list:
        # Time PA gain
        tempo.asic.ch(channel).set.patGain(patgain)
        # config['patgain'].append(patgain)

        tempo.asic.ch(channel).set.patComp(0)

        # Shaper and Peak Detector setting
        # tempo.asic.ch(channel).enable.pdetHG()
        # tempo.asic.ch(channel).enable.pdetLG()

        # tempo.asic.ch(channel).set.tauHG(4)  # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.tauHG(15)
        tempo.asic.ch(channel).set.pahgGain(0)
        tempo.asic.ch(channel).set.tauLG(15)  # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.palgGain(0)

        tempo.asic.ch(channel).disable.TL()
        tempo.asic.ch(channel).disable.TQ()


    print(np.sort(channels_list), "injected channels")
    config['enable_TL_ASIC_ch'].append(channels_list)
    config['tdc_injected'].append(['low', 'high'])
    config['power_cluster'].append(clusters_list)
    probed_channel = config['enable_TL_ASIC_ch'][-1][-1]
    config['probed_channel'].append(probed_channel)

    if probed_channel is not None:
        print("probed_channel : ", probed_channel)
        # tempo.fpga.set.hit_register_channel(probed_channel)
        tempo.asic.ch(probed_channel).select.analogProbe.shL()
        tempo.asic.common.probeDig.channel(probed_channel).TrigT_H()

    tempo.asic.common.set.delay_pdet(2 ** 8 - 1)
    # tempo.asic.common.select.trigger.local_time_low()
    # tempo.asic.common.select.trigger.local_time_high()

    tempo.asic.common.select.trigger.global_ASIC()  # to launch all peak detector with ch0 low trigger
    # tempo.asic.interface.select.global_trigger.ORTL()
    tempo.asic.interface.select.global_trigger.ORTH()
    # tempo.asic.interface.select.global_trigger.ORTQ()
    tempo.asic.interface.en.sync_cluster()

    # tempo.asic.bias.pdbuf.enable()
    # tempo.asic.bias.sh.HG.enable()
    # tempo.asic.bias.sh.LG.enable()

    nb_trigger = 31  # to have only one frame with 2 channels injected simultaneously
    tempo.asic.interface.set.nb_trigger(nb_trigger)  # cluster valid
    config['nb_trigger'].append(nb_trigger)

    # tempo.asic.interface.en.sync_cluster()  # not required : only if Cluster specific data conversion
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

    # Digital readout enable and Force conversion settings
    tempo.fpga.set.ro_enable_ASIC(0)

    tempo.asic.interface.en.Inh_rstOnDlyH()  # mask end delay H for digital
    tempo.asic.interface.en.Inh_rstOnDlyL()

    # Val event and Trigger latch enabled
    # tempo.fpga.set.val_evt_ASIC(0)
    print("check val event")
    tempo.asic.common.en.latch()

    # Time Trigger and Threshold settings
    tempo.asic.bias.discri.TL.enable()
    tempo.asic.bias.discri.TH.enable()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.dis.hyst_TL()
    dacTH = 1023
    dacTL = 1023
    tempo.asic.common.set.dacTH(dacTH)
    tempo.asic.common.set.dacTL(dacTL)
    tempo.asic.common.set.dacQ(1023)
    config['dacTH'].append(dacTH)
    config['dacTL'].append(dacTL)

    # Analog probe
    tempo.asic.interface.en.analog_probe()

    # Digital probe
    probed_cluster = config['enable_TL_ASIC_ch'][-1][-1] // 16
    print('probed_cluster : ', probed_cluster)
    # tempo.IO.IO7_select.ser_data(probed_cluster)
    # tempo.IO.OUT7_select.ser_clk(probed_cluster)
    # tempo.IO.IO7_select.pulse_tdc()
    tempo.fpga.OUT4_select.digit_probe()

    # tempo.IO.OUT7_select.or_trig_q_rs()
    # tempo.IO.IO8_select.ser_clk(probed_cluster)
    # tempo.IO.IO8_select.ser_data(probed_cluster)
    tempo.asic.interface.en.digital_probe()

    # useless : used only to probe pdet outside the ASIC through OTA
    tempo.asic.interface.en.LG_pdet_MUX_output()
    tempo.asic.interface.en.HG_pdet_MUX_output()
    tempo.asic.interface.en.Nor_TrigT_L_RS()
    tempo.asic.interface.en.Nor_TrigT_H_RS()
    tempo.asic.interface.en.Nor_TrigQ()
    tempo.asic.interface.en.Nor_TrigQ_RS()
    tempo.asic.interface.en.trigT_L_RS_mux()
    tempo.asic.interface.en.trigT_H_RS_mux()

    # tempo.asic.common.probeDig.channel(channel).TrigT_H()
    # tempo.asic.common.probeDig.channel(channel).TH()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L()
    # tempo.asic.common.probeDig.channel(channel).HOLD_delayed()
    # tempo.asic.common.probeDig.cluster(cluster).rstnADC()
    # tempo.asic.common.probeDig.cluster(cluster).rstnLatchInt()
    # tempo.asic.common.probeDig.cluster(cluster).end_delayH()
    # tempo.asic.common.probeDig.cluster(cluster).convDoneADCLG()

    tempo.save_ASIC_and_FPGA_config(config)

    # test : reset transmitted
    # tempo.deserializer.reset_fifo_for_all_cluster()
    # tempo.fpga.reset.digital()
    # tempo.asic.common.probeDig.channel(probed_channel).rstn_TDC()
    # tempo.asic.common.probeDig.cluster(probed_cluster).reset()

    # debug coincidence
    # tempo.IO.OUT4_select.coincidence()
    # tempo.IO.OUT6_select.eof_local()

    # debug clock
    # tempo.IO.OUT4_select.clk_320()
    return tempo


def coincidence_Na22_dual_boards():

    config = {'board': [1, 2], 'save_folder': [], 'tempo_dig_ck': 80, 'readout_mode': [],
              'step': 0, 'restart_from_last_step': False,
              'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
              'current_time': [], 'log': [], 'start_time': 0, 'coincidence_rate': 0, 'debug': []}

    config['config_B2'] = {'mode': 'slave', 'board': 2, 'SiPM_model': 'Hamamatsu_S13361_6597',
                           'SiPM_breakdown': 52.5,
                           'CAEN_serial_number': 'AI05VLCGA', 'light_source': '3x3x5mm_teflon_wrapped_LYSO',
                           'patgain': 4, 'dacTH': 1023, 'dacTL': 800, 'dacTQ': 600, 'charge_filter': False,
                           'palgGain': 1, 'tauLG': 15, 'target_hv': 57.5, 'tdc_injected': [['low', 'high']],
                           'deserialiser_time': 2200, 'enabled_TH_fb': False,
                           'enable_TL_ASIC_ch': [43],
                           'calib_time_discri': False, 'calib_inDAC': False, 'VDDD': 1.33}

    config['config_B1'] = {'mode': 'master', 'board': 1, 'SiPM_model': 'Hamamatsu_S13361_6597',
                           'SiPM_breakdown': 52.5,
                           'CAEN_serial_number': 'AL04WEE3A', 'light_source': '3x3x5mm_teflon_wrapped_LYSO',
                           'patgain': 4, 'dacTH': 1023, 'dacTL': 800, 'dacTQ': 600, 'charge_filter': False,
                           'palgGain': 1, 'tauLG': 15, 'target_hv': 57.5, 'tdc_injected': [['low', 'high']],
                           'deserialiser_time': 2200, 'enabled_TH_fb': False,
                           'enable_TL_ASIC_ch': [43],
                           'calib_time_discri': False, 'calib_inDAC': False, 'VDDD': 1.34}

    local_output_dir = "../output/coincidence/scope_22Na/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)
    

    scopeLecroy = tools.lecroyOscilloDAQ("LCRY4703N41520")
    scopeLecroy.load_setup("../config/scope/CTR.lss")
    # scopeLecroy.save_setup("../config/scope/CTR.lss")

    slave = temporoc3(config, mode='slave')
    slave.hv.connect()
    slave.hv.turn_on()

    master = temporoc3(config, mode='master')
    master.hv.connect()
    master.hv.turn_on()

    setup_temporoc(master, config)
    setup_temporoc(slave, config)

    hv_voltage_list = list(range(57, 58, 1))

    config['parameters_swept'] = ['hv', 'patGain', 'patComp']
    for hv_voltage in hv_voltage_list:

        slave.hv.set_voltage(hv_voltage)
        master.hv.set_voltage(hv_voltage)
        slave.hv.wait_setpoint_reached()
        master.hv.wait_setpoint_reached()

        for patGain in [4, 16, 32, 40, 63]:
            for patComp in [0, 1]:
                filename = 'hv_%d_patGain_%d_patComp_%d.csv'%(hv_voltage, patGain, patComp)

                # Setup
                master.asic.ch(config['enable_TL_ASIC_ch'][0][0]).set.patGain(patGain)
                slave.asic.ch(config['enable_TL_ASIC_ch'][1][0]).set.patGain(patGain)
                master.asic.ch(config['enable_TL_ASIC_ch'][0][0]).set.patComp(patComp)
                slave.asic.ch(config['enable_TL_ASIC_ch'][1][0]).set.patComp(patComp)
                print(filename)

                # Measure
                scopeLecroy.clearSweep()
                scopeLecroy.oscillo.write('TRMD NORM')
                time.sleep(5)
                while scopeLecroy.getMeasure(1, 'num')<1e3:
                    time.sleep(10)

                scopeLecroy.get_waveforms(local_output_dir, filename)

    print("Done")

    master.close()
    slave.close()



if __name__ == "__main__":
    coincidence_Na22_dual_boards()