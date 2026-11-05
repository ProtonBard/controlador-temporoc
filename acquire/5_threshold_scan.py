import glob
import re

from analyse.common_analysis import *
from src.common_setup import *
from src.temporoc3 import *
import src.tools as tools
import pandas as pd

import math
import os
import numpy as np
import uiroc.device as device
from src.tools import *
from src.utils import *
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Qt5Agg')

output_dir = '../output/discri'


# def fast_threshold_scan(channel):
#
#     tempo = temporoc(b'LI_', 3, "../config/temporoc2_hw_default_SC.csv")
#     # test modifications
#     tempo.init_board()
#     tempo.asic.interface.select.dig_modeRO.hit()
#     tempo.asic.interface.dis.TDC_passthrough()
#
    # tempo.asic.ch(channel).set.inDac(8)
#     tempo.asic.interface.select.miller_cap_probeA._100fF()
#
#     tempo.asic.ch.all_except(channel).disable.all_discri()
#     tempo.asic.ch.all_except(channel).disable.ctest()
#
#     # before MUX between internal / external
#     tempo.probeDigital.select.TrigT_L()
#     # tempo.probeDigital.select.TrigT_H()
#
#     # # after MUX between internal / external
#     # tempo.probeDigital.select.TrigTL()
#     # tempo.probeDigital.select.TrigTH()
#     #
#     # # should not be used because latched triggers, and reset occurs a long time after
#     # tempo.probeDigital.select.TrigT_L_RS()
#
#     csv_file = "thresholdScan_hit.csv"
#     threshold_scan_probe_channel_wise(0, 1023, 0, 1023, 50, csv_file, tempo_thresh=100e-9,
#                                       pulser_enable=True, pulser_freq = 10e6, trigger_window= 50e-6)
#
#
# def fast_mux_threshold_scan():
#     # for all channels simultaneously
#
#     tempo = temporoc(b'LI_', 3, "../config/temporoc2_hw_default_SC.csv")
#     # test modifications
#     tempo.init_board()
#     tempo.asic.interface.select.dig_modeRO.hit()
#     tempo.asic.interface.dis.TDC_passthrough()
#
#     channel = 0
#     tempo.asic.ch(channel).set.inDac(8)
#     tempo.asic.interface.select.miller_cap_probeA.fF_100()
#
#
#
#     csv_file = "thresholdScan_hit.csv"
#     threshold_scan_probe_channel_wise(0, 1023, 0, 1023, 50, csv_file, tempo_thresh=100e-9,
#                                       pulser_enable=True, pulser_freq=10e6, trigger_window=50e-6)
#
#
#     pass

# Threshold scan to be repeated while varying the following parameters :
#   S-curve noise comparison between :
#     when TDC are disabled (under reset rstn_delaybox : possible to control this reset independantly from digital ? NOT POSSIBLE !)
#     disabling the other time discriminator
#     enabling the charge path with or without the ADC
#     with all clusters enabled but don't care about the data

def threshold_scan_smart(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    channel = 1
    cluster = channel // 16
    # ext_pulser = tektronix_AFG()

    tempo = temporoc3(config)
    tempo.pll.configure_PLL_with_default_behaviour()
    # tempo.pll.configure_PLL_no_clocks_except_FPGA()
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()
    if tempo.dev.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch) > 0:
        print('SC fifo full at startup. power off asic')
        exit()
    tempo.fpga.set.power_on_ASIC(1)
    tempo.fpga.reset.all_temporoc()
    time.sleep(0.5)
    assert tempo.pll.check_is_locked()

    tempo.correct_default_HW_SC()
    # disable analog & discri for all channels
    # tempo.asic.ch.all().disable.charge()
    # tempo.asic.ch.all().disable.timing()
    # tempo.asic.ch.all().disable.all_discri()

    # by default enabled
    # tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    # tempo.asic.interface.dis.ck320()

    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.asic.interface.set.nb_trigger(31)  # expecting never 3 frames per injection, instead always 2
    tempo.asic.common.en.bypassResetMgmt()


    # Threshold scan requires enabling the digital probe
    tempo.asic.interface.en.digital_probe()
    tempo.asic.interface.en.trigT_L_RS_mux()
    tempo.asic.interface.en.trigT_H_RS_mux()
    tempo.asic.interface.en.trigQ_RS_mux()

    tempo.asic.ch(channel).enable.timing()
    tempo.asic.ch(channel).select.trigTH.internal()
    tempo.asic.ch(channel).select.trigTL.internal()
    tempo.asic.ch(channel).enable.TL()
    tempo.asic.ch(channel).enable.TH()
    tempo.asic.ch(channel).set.patGain(8)
    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()

    # debug:
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT4_select.digit_probe()
    tempo.fpga.OUT7_select.ser_clk(0)
    tempo.fpga.OUT7_select.trig_t_l_rs_mux()
    tempo.fpga.OUT1.en_ck320()

    
    options = "B%d" % (board)

    local_output_dir = '../output/threshold_scan/' + "ch_%d/" % channel
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # find unique new file index
    file_list = glob.glob(local_output_dir + '/*.csv')
    if not file_list:
        new_file_index = 0
    else:
        max_index = -1
        for file in file_list:
            index = re.findall("[0-9]+(?=_B)", os.path.basename(file))
            if index:
                index = int(index[0])
                if index > max_index:
                    max_index = index
        new_file_index = max_index + 1
        # new_file_index = int(re.findall("[0-9]+(?=_B)", file_list[-1])[0]) + 1
    filepath = local_output_dir + "%d_%s.csv"% (new_file_index, options)
    filepath_i2c_df = local_output_dir + "%d_%s_i2c_df.csv"% (new_file_index, options)
    print("Will save events in file %s" % filepath)

    time_acq_window = 2e-3
    Cinj = 100e-12

    df = pd.DataFrame()

    for Vinj in range(0, 1000, 100):

        if Vinj == 0:    # measure pedestal
            # ext_pulser.burst_mode()
            pass
        else:
            pass
            # ext_pulser.set_voltage_amplitude(Vinj)
            # ext_pulser.continuous_mode()

        thres = 512 #2**10/2
        step = 512
        for i in range(7):
            tempo.asic.common.set.dacTL(thres)
            tempo.asic.common.set.dacTH(thres)
            tempo.fpga.reset.tpr_latch()  # without bypassing
            tempo.reset_hit_register()
            hit_reg = tempo.fpga.get.hit_register_channel(channel)
            print(thres, bin(hit_reg))
            # tempo.fpga.get.hit_map()

            if hit_reg & 0b100: # transition from 1 to 0 is above tested threshold
                thres += step//2
            else:
                thres -= step//2
            step = step//2

        print(thres)
        # tempo.reset_hit_register()
        # tempo.fpga.set.hit_register_channel(channel)
        # print(tempo.fpga.get.hit_register_channel())
        tempo.asic.common.probeDig.channel(channel).TrigT_L()
        df_tmp = tempo.threshold_scan(thres-10, thres+10, 1)
        # charge injection with async external pulser through a cap of 100 pF
        # Qinj = 10 pC = 100 mV * 100 pF / 10 (-20 dB attenuator)

        df_tmp['Vinj_mV'] = Vinj / 10  # -20dB attenuator
        df_tmp['Qinj_pC'] = Vinj / 10 * Cinj * 1e9
        df = pd.concat([df, df_tmp])

    tempo.dev.i2c.df_i2c.to_csv(filepath_i2c_df, index=False)
    df.to_csv(filepath, index=False)
    tempo.close()

    pass

def check_stable_i2c(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)
    tempo.init_board()
    tempo.correct_default_HW_SC()

    print(tempo.dev.i2c.read_register(9, 66))
    tempo.asic.common.probeDig.channel(9).TrigT_H()
    print(tempo.dev.i2c.read_register(9, 66))
    tempo.asic.common.set.dacTH(100)
    print(tempo.dev.i2c.read_register(9, 66))
    for thresh in range(100, 150):
        tempo.asic.common.set.dacTH(thresh)
        print(tempo.dev.i2c.read_register(9, 66))

    pass

def basic_threshold_scan(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    tempo = temporoc3(config)


    # disable analog & discri for all channels
    # tempo.asic.ch.all().disable.charge()
    # tempo.asic.ch.all().disable.timing()
    # tempo.asic.ch.all().disable.all_discri()

    # default parameters
    # tempo.asic.ch(channel).enable.timing()
    # tempo.asic.ch(channel).select.trigTH.internal()
    # tempo.asic.ch(channel).select.trigTL.internal()
    # tempo.asic.ch(channel).enable.TL()
    # tempo.asic.ch(channel).enable.TH()

    tempo.asic.ch.all().set.patGain(8)

    # by default enabled
    # tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    # tempo.asic.interface.dis.ck320()

    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.asic.interface.set.nb_trigger(1)  # expecting never 3 frames per injection, instead always 2
    tempo.asic.common.en.bypassResetMgmt()  # needed otherwise temporoc digital under reset (if ro_enable at 0) holds the trigger latch under reset
    tempo.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset

    # Threshold scan requires enabling the digital probe
    tempo.asic.interface.en.digital_probe()
    tempo.asic.interface.en.trigT_L_RS_mux()
    tempo.asic.interface.en.trigT_H_RS_mux()
    tempo.asic.interface.en.trigQ_RS_mux()

    
    options = "B%d" % (board)

    local_output_dir = '../output/threshold_scan/all/'
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # find unique new file index
    # file_list = glob.glob(local_output_dir + '/*.csv')
    # if not file_list:
    #     new_file_index = 0
    # else:
    #     max_index = -1
    #     for file in file_list:
    #         index = re.findall("[0-9]+(?=_B)", os.path.basename(file))
    #         if index:
    #             index = int(index[0])
    #             if index > max_index:
    #                 max_index = index
    #     new_file_index = max_index + 1
    filepath = local_output_dir + "%d_%s.csv" % (0, options)
    filepath_i2c_df = local_output_dir + "%d_%s_i2c_df.csv" % (0, options)
    print("Will save events in file %s" % filepath)

    time_acq_window = 2e-3
    Cinj = 100e-12

    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.probeDig.channel(0).TrigT_H()
    tempo.asic.common.set.dacTH(250)

    # debug:
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT8_select.digit_probe()
    # tempo.IO.IO8_select.trig_t_l_mux()
    tempo.fpga.OUT7_select.ser_clk(0)
    tempo.fpga.OUT7_select.trig_t_l_rs_mux()
    tempo.fpga.OUT1.en_ck320()

    startTL_list = [0]*64
    startTH_list = [0]*64
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        for channel in range(64):
            startTL_list[channel] = df.loc[df.channel == channel, 'TL_dac'].max()
            startTH_list[channel] = df.loc[df.channel == channel, 'TH_dac'].max()
    else:
        df = pd.DataFrame()

    for channel in range(2):
        df_tmp = tempo.common_threshold_scan(channel, range(startTL_list[channel], 1023, 2), range(startTH_list[channel], 1023, 2))
        df = pd.concat([df, df_tmp])
        df.to_csv(filepath, index=False)

    df.to_csv(filepath, index=False)
    pass




def threshold_scan(board, asic_id, forced_index=None):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)

    local_output_dir = "../output/B%d_TPR%d/threshold_scan/" % (board, asic_id)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config, forced_index=forced_index)

    options = "B%d_TPR%d" % (board, asic_id)
    filepath_df = local_output_dir + "%d_%s_threshold_scan.csv"% (new_index, options)
    filepath_df_scurve = local_output_dir + "%d_%s_scurve.csv"% (new_index, options)
    filepath_df_estimated_threshold = local_output_dir + "%d_%s_estimated_threshold.csv"% (new_index, options)

    setup_temporoc([tempo], config)

    tempo.asic.interface.en.Nor_TrigT_L_RS()
    tempo.asic.interface.en.Nor_TrigT_H_RS()



    scan_TL = True
    scan_TH = False

    thres_scan_df = pd.DataFrame()
    channel_list = [1] #range(64)
    print("Channels to explore ", channel_list)

    for asic_config in range(5):
        print("######### ASIC config %d :"%asic_config)

        if asic_config==0:
            label = "One discri, lowest preamplifier gain, no digital, no clocks"
            # Only one discriminator enabled
            tempo.asic.ch.all_except(channel_list).disable.all_discri()
            tempo.asic.ch.group(channel_list).enable.TL()
            tempo.asic.ch.group(channel_list).disable.TH()
            tempo.asic.ch.group(channel_list).disable.TQ()

            tempo.asic.ch.all().set.patGain(63)  # Lowest PA gain
            tempo.asic.common.en.hyst_TL()
            tempo.asic.common.en.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(0)
            tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.dis.ck320()

        if asic_config == 1:
            label = "Turning on digital and 320 MHz clocks"

            # Only one discriminator enabled
            tempo.asic.ch.all_except(channel_list).disable.all_discri()
            tempo.asic.ch.group(channel_list).enable.TL()
            tempo.asic.ch.group(channel_list).disable.TH()
            tempo.asic.ch.group(channel_list).disable.TQ()

            tempo.asic.ch.all().set.patGain(63)  # Lowest PA gain
            tempo.asic.common.en.hyst_TL()
            tempo.asic.common.en.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(1)
            tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.en.ck320()

        if asic_config == 2:
            label = "Enabling all T1 neighbours discri"

            tempo.asic.ch.all().enable.TL()
            tempo.asic.ch.all().disable.TH()
            tempo.asic.ch.all().disable.TQ()

            tempo.asic.ch.all().set.patGain(63)  # Lowest PA gain
            tempo.asic.common.en.hyst_TL()
            tempo.asic.common.en.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(1)
            tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.en.ck320()

        if asic_config == 3:
            label = "Aligning T1 discri"

            tempo.asic.ch.all().enable.TL()
            tempo.asic.ch.all().disable.TH()
            tempo.asic.ch.all().disable.TQ()

            tempo.asic.ch.all().set.patGain(63)  # Lowest PA gain
            tempo.asic.common.dis.hyst_TL()
            tempo.asic.common.dis.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(1)
            tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.en.ck320()


        if asic_config == 4:  # Typical config, only one discri (LOW) per channel
            label = "Increasing preamplifier gain to max"

            tempo.asic.ch.all().enable.TL()
            tempo.asic.ch.all().disable.TH()
            tempo.asic.ch.all().disable.TQ()

            tempo.asic.ch.all().set.patGain(1)  # Highest PA gain
            tempo.asic.common.dis.hyst_TL()
            tempo.asic.common.dis.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(1)
            tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.en.ck320()


        if asic_config == 5:  # Typical config, only one discri (LOW) per channel, with hysteresis
            label = "Enabling hysteresis"

            tempo.asic.ch.all().enable.TL()
            tempo.asic.ch.all().disable.TH()
            tempo.asic.ch.all().disable.TQ()

            tempo.asic.ch.all().set.patGain(1)  # Highest PA gain
            tempo.asic.common.en.hyst_TL()
            tempo.asic.common.en.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(1)
            tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.en.ck320()

        if asic_config == 6:  # Typical config, only one discri (LOW) per channel, with hysteresis
            label = "Enabling all T2 discri"

            tempo.asic.ch.all().enable.TL()
            tempo.asic.ch.all().enable.TH()
            tempo.asic.ch.all().disable.TQ()

            tempo.asic.ch.all().set.patGain(1)  # Highest PA gain
            tempo.asic.common.en.hyst_TL()
            tempo.asic.common.en.hyst_TH()

            tempo.asic.interface.set.nb_trigger(1)
            tempo.fpga.set.ro_enable_ASIC(1)
            tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
            tempo.asic.interface.en.ck320()



        # Locate approximately pedestal
        # if os.path.exists(filepath_df_estimated_threshold):
        #     expected_threshold_df = pd.read_csv(filepath_df_estimated_threshold)
        # else:
        #     expected_threshold_df, fast_scurve_df = tempo.find_approximately_threshold_for_all_channels()
        #     fast_scurve_df.to_csv(filepath_df_scurve, index=False)
        #     expected_threshold_df.to_csv(filepath_df_estimated_threshold, index=False)


        # # Debug
        # tempo.asic.common.dis.latch()
        # tempo.fpga.set.val_evt_ASIC(1)
        # tempo.fpga.OUT3_select.or_trig_l_rs()
        # tempo.fpga.OUT3_select.digit_probe()
        # tempo.asic.interface.en.digital_probe()
        # tempo.asic.common.probeDig.channel(1).TrigT_L_RS()
        #
        # tempo.asic.common.set.dacTL(121)
        # tempo.fpga.OUT2_select.trig_t_l_rs_mux()
        # tempo.fpga.OUT3_select.tpr_read_clk()
        # tempo.fpga.OUT4_select.tpr_read_rstn()
        # tempo.fpga.OUT6_select.val_evnt()


        # START threshold scan measurement
        for channel in channel_list:
            df_tmp = tempo.common_threshold_scan(channel, range(70, 200, 1), None, time_acq_window=50e-3)
            df_tmp['asic_config'] = asic_config
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(filepath_df, index=False)

        continue
        # coarse step
        offset = 10
        coarse_step = 5
        for channel in channel_list:
            TL = expected_threshold_df.loc[expected_threshold_df.channel == channel, 'low_thres_dac'].iloc[0] - offset
            TH = expected_threshold_df.loc[expected_threshold_df.channel == channel, 'high_thres_dac'].iloc[
                     0] - offset
            df_tmp = tempo.common_threshold_scan(channel, thres_range_start_from_center(TL, 30, coarse_step))
                                                 # thres_range_start_from_center(TH, 30, coarse_step))
            df_tmp['asic_config'] = asic_config
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(filepath_df, index=False)

        # finest step
        fine_step = 1
        for channel in channel_list:
            selection = (thres_scan_df.channel == channel) & (thres_scan_df.asic_config == asic_config)
            if scan_TL:
                TL_max_index = thres_scan_df.loc[selection, 'TL_freq'].idxmax()
                TL_first_nonzero_index = thres_scan_df.loc[selection, 'TL_freq'].ne(0).idxmax()-(coarse_step-1)
                TL_half_span = TL_max_index - TL_first_nonzero_index
                TL = int(thres_scan_df.loc[selection, 'TL_dac'][TL_max_index])
                TL_list_left = thres_range(TL, TL_half_span, fine_step, excluding=thres_scan_df.loc[selection, 'TL_dac'])
            else:
                TL_list_left = None

            if scan_TH:
                TH_max_index = thres_scan_df.loc[selection, 'TH_freq'].idxmax()
                TH_first_nonzero_index = thres_scan_df.loc[selection, 'TH_freq'].ne(0).idxmax()-(coarse_step-1)
                TH_half_span = TH_max_index - TH_first_nonzero_index
                TH = int(thres_scan_df.loc[selection, 'TH_dac'][TH_max_index])
                # find threshold left to sweep removing already scanned values
                TH_list_left = thres_range(TH, TH_half_span, fine_step, excluding=thres_scan_df.loc[selection, 'TH_dac'])
            else:
                TH_list_left = None

            df_tmp = tempo.common_threshold_scan(channel, TL_list_left, TH_list_left)
            df_tmp['asic_config'] = asic_config
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(filepath_df, index=False)

        thres_scan_df.to_csv(filepath_df, index=False)

        # Save asic configuration
        filepath_i2c_df = local_output_dir + "%d_%s_i2c_df_asic_config_%d.csv" % (new_index, options, asic_config)
        tempo.asic.i2c.df_i2c.to_csv(filepath_i2c_df, index=False)

    # tempo.asic.common.probeDig.channel(0).TrigT_H()
    # tempo.asic.common.set.dacTH(0)
    # tempo.asic.common.set.dacTL(0)

    # debug:
    # tempo.fpga.OUT5.en_ck40M()
    # tempo.fpga.OUT2_select.digit_probe()
    # tempo.IO.IO8_select.trig_t_l_mux()
    # tempo.fpga.OUT7_select.ser_clk(0)
    # tempo.fpga.OUT7_select.trig_t_l_mux()
    # tempo.fpga.OUT1.en_ck320()

    # tempo.asic.ch.all_except(0).disable.front_end()
    # tempo.asic.ch.all_except(0).disable.all_discri()
    # for i in range(1, 64):
    #     tempo.asic.ch(i).disable.all_discri()
    # tempo.dev.i2c.check_all_register()
    # tempo.asic.i2c.SC_stats()


    # if os.path.exists(filepath_df):
    #     thres_scan_df = pd.read_csv(filepath_df)
    #     # find channels left to sweep : where pedestal has not been found
    #     # channel_list_swept_not_null = thres_scan_df.loc[thres_scan_df.groupby('channel').TL_count.transform(lambda x: x.sum()==0), 'channel'].unique().tolist()
    #     channel_list_swept_not_null = thres_scan_df.groupby('channel').filter(lambda x: (x.TL_count.sum()!=0) & (x.TH_count.sum()!=0)).channel.unique()
    #     channel_list = set(channel_list_swept_not_null) ^ set(range(64))  # complementary list
    #     if 'acquisition_time_ms' not in thres_scan_df.columns:
    #         thres_scan_df['acquisition_time_ms'] = 2e-3 # default
    #     pass
    # else:


    tempo.close()
    pass


def threshold_scan2(board, asic_id):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)

    local_output_dir = "../output/threshold_scan/B%d_TPR%d/" % (board, asic_id)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    setup_temporoc([tempo], config)

    # disable analog & discri for all channels
    # tempo.asic.ch.all().disable.charge()
    # tempo.asic.ch.all().disable.timing()
    # tempo.asic.ch.all().disable.all_discri()

    # default parameters
    # tempo.asic.ch(channel).enable.timing()
    # tempo.asic.ch(channel).select.trigTH.internal()
    # tempo.asic.ch(channel).select.trigTL.internal()
    # tempo.asic.ch(channel).enable.TL()
    # tempo.asic.ch(channel).enable.TH()

    tempo.asic.ch.all().set.patGain(8)

    # by default enabled
    # tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    # tempo.asic.interface.dis.ck320()

    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.dis.latch() # enable if you have a reset strategy from the FPGA via resetn_latch
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.asic.interface.set.nb_trigger(1)
    tempo.asic.common.en.bypassResetMgmt()  # needed otherwise temporoc digital under reset (if ro_enable at 0) holds the trigger latch under reset
    tempo.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset

    # Threshold scan requires enabling the digital probe
    tempo.asic.interface.en.digital_probe()
    tempo.asic.interface.en.trigT_L_RS_mux()
    tempo.asic.interface.en.Nor_TrigT_L_RS()
    tempo.asic.interface.en.Nor_TrigT_H_RS()
    # tempo.asic.interface.en.trigT_L_mux()
    # tempo.asic.interface.en.trigT_H_mux()
    # tempo.asic.interface.en.trigQ_mux()

    #
    # if not os.path.exists(local_output_dir):
    #     os.makedirs(local_output_dir)

    # # find unique new file index
    # file_list = glob.glob(local_output_dir + '/*.csv')
    # if not file_list:
    #     new_file_index = 0
    # else:
    #     max_index = -1
    #     for file in file_list:
    #         index = re.findall("[0-9]+(?=_B)", os.path.basename(file))
    #         if index:
    #             index = int(index[0])
    #             if index > max_index:
    #                 max_index = index
    #     new_file_index = max_index + 1
    # new_file_index=9

    filepath_df = local_output_dir + "%d.csv" % (new_index)
    print("Will save events under index %d" % new_index)

    time_acq_window = 2e-3
    Cinj = 100e-12

    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.dis.hyst_TH()
    # tempo.asic.common.probeDig.channel(0).TrigT_H()
    #
    # # debug:
    # tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT2_select.digit_probe()
    # tempo.fpga.OUT7_select.ser_clk(0)
    # tempo.fpga.OUT7_select.trig_t_l_mux()
    # tempo.fpga.OUT1.en_ck320()

    channel_list = [8]

    # tempo.asic.ch.all_except(channel_list).disable.front_end_except_pdet()
    tempo.asic.ch.all_except(channel_list).disable.all_discri()
    tempo.asic.ch(8).enable.TL()
    # tempo.asic.ch(8).enable.timing()
    # tempo.asic.ch(8).select.trigTL.internal()

    # tempo.asic.common.probeDig.channel(0).TrigT_L()
    # tempo.asic.common.set.dacTL(0)  # set threshold

    pass
    # for i in range(1, 64):
    #     tempo.asic.ch(i).disable.all_discri()

    print("Channels to explore ", channel_list)
    for channel in channel_list:
        TL = 168
        TH = 152
        df = tempo.common_threshold_scan(channel, range(160,175,1),None, time_acq_window=10e-3)
        df.to_csv(filepath_df, index=False)

        plt.figure()
        for gain in ['TL', 'TH']:
            not_nan_selection = ~(df.loc[:, gain + '_dac'].isna())
            thres_dac = df.loc[not_nan_selection, gain + '_dac']
            counts = df.loc[not_nan_selection, gain + '_freq']
            plt.plot(thres_dac, counts, label='ch%d' % channel)
        plt.grid()
        plt.legend()
        # plt.yscale('log')
        plt.title(gain + ' threshold scan')
        plt.suptitle("Channel %d" % channel)
        plt.tight_layout()
        plt.savefig(local_output_dir + 'ch%d.png' % channel)
        plt.show()


    tempo.close()
    pass


def check_ib_calib_dac_issue(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)
    tempo.init_board()
    tempo.correct_default_HW_SC()
    config = {}
    
    options = "B%d" % (board)

    local_output_dir = '../output/basic/DC/calibdac/'
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # find unique new file index
    file_list = glob.glob(local_output_dir + '/*.csv')
    if not file_list:
        new_file_index = 0
    else:
        max_index = -1
        for file in file_list:
            index = re.findall("[0-9]+(?=_B)", os.path.basename(file))
            if index:
                index = int(index[0])
                if index > max_index:
                    max_index = index
        new_file_index = max_index + 1

    filepath_df = local_output_dir + "%d_%s.csv"% (new_file_index, options)
    filepath_i2c_df = local_output_dir + "%d_%s_i2c_df.csv"% (new_file_index, options)
    print("Will save events under index %d" % new_file_index)

    df = pd.DataFrame()
    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.dis.hyst_TH()

    # fix arbitrary values : should not impact on the ib_calibdac issue
    tempo.asic.common.set.dacTH(0)
    tempo.asic.common.set.dacTL(0)
    tempo.asic.ch.all().set.calibDACT1(0)
    tempo.asic.ch.all().set.calibDACT2(0)

    expected_threshold_df, fast_scurve_df = tempo.find_approximately_threshold_for_all_channels()

    tempo.close()


def setup_tempo(config):

    print("Connecting Temporoc")
    tempo = temporoc3(config)

    tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_sync_ext_trigger()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_40M_dig_ck()  # for internal ADC so no cross talk on MUX
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_80M_dig_ck()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_160M_dig_ck()

    tempo_dig_ck.append(tempo_dig_ck_freq)
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()

    tempo.reset_power_check_correct_clock_init()

    tempo.correct_default_HW_SC()
    

    tempo.fpga.pulser.mask_on_ext_trigger()
    tempo.fpga.pulser.mask_on_IO0()
    tempo.fpga.pulser.disable()
    tempo.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset

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

    nb_trigger = 31
    tempo.asic.interface.set.nb_trigger(nb_trigger)  # cluster valid
    config['nb_trigger'].append(nb_trigger)

    # tempo.asic.interface.en.sync_cluster()  # not required : only if Cluster specific data conversion
    # tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)


    tempo.asic.interface.en.Inh_rstOnDlyH()  # mask end delay H for digital
    tempo.asic.interface.en.Inh_rstOnDlyL()

    # Time Trigger and Threshold settings
    tempo.asic.bias.discri.TL.enable()
    tempo.asic.bias.discri.TH.enable()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.dis.hyst_TL()

    # Analog probe
    # tempo.asic.interface.en.analog_probe()

    # Digital probe
    # probed_cluster = None #config['enable_TL_ASIC_ch'][-1] // 16
    # print('probed_cluster : ', probed_cluster)
    # tempo.IO.IO7_select.ser_data(probed_cluster)
    # tempo.IO.OUT7_select.digit_probe()
    # tempo.IO.IO7_select.pulse_tdc()
    # tempo.IO.OUT4_select.ser_clk(probed_cluster)
    # tempo.IO.OUT4_select.trig_t_l_mux()

    # tempo.IO.OUT4_select.or_trig_q()
    # tempo.IO.OUT7_select.or_trig_q_rs()
    # tempo.IO.OUT4_select.ser_clk(probed_cluster)
    # tempo.IO.OUT4_select.ser_data(probed_cluster)
    # tempo.asic.interface.en.digital_probe()

    readout_mode = 'full_adc_tdc'  # ,'lg_adc_low_tdc', 'hg_adc_low_tdc']   #, 'low_high_tdc', 'low_tdc', ]:
    config['readout_mode'].append(readout_mode)
    tempo.asic.interface.select.dig_modeRO(readout_mode)

    # print("Disabling all cluster clks")
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.fpga.select.ck_from_FPGA_to_ASIC.off()
    tempo.fpga.set.ro_enable_ASIC(0)

    config['ro_enable'].append(0)
    config['dig_clock'].append(0)
    config['all_cluster_ck'].append(0)

    tempo.save_ASIC_and_FPGA_config(config)

    return tempo

def setup_SiPM_channel(tempo, config, SiPM_channels_list):
    config['injected_channel_SiPM'] = SiPM_channels_list
    ASIC_channels_list = get_ASIC_ch(SiPM_channels_list, config['SiPM_model'])

    setup_ASIC_channel(tempo, config, ASIC_channels_list)

    return ASIC_channels_list

def setup_ASIC_channel(tempo, config, ASIC_channels_list):

    clusters_list = np.unique(np.array(ASIC_channels_list) // 16).tolist()
    update_config_dict(config, clusters_list)
    # tempo.asic.ch.all_except(channels_list).disable.front_end_except_pdet()
    tempo.asic.ch.all_except(ASIC_channels_list).disable.front_end()
    # tempo.asic.ch.group(channels_list).enable.front_end()

    for channel in ASIC_channels_list:
        tempo.asic.ch(channel).enable.front_end()
        tempo.asic.ch(channel).disable.TH()
        tempo.asic.ch(channel).disable.TQ()
        # tempo.asic.ch(channel).enable.TL()


        # Time PA gain
        # tempo.asic.ch(channel).set.patGain(16)
        # tempo.asic.ch(channel).set.patComp(0)

        # tempo.asic.ch(channel).disable.charge()
        # Shaper and Peak Detector setting
        # tempo.asic.ch(channel).enable.pdetHG()
        # tempo.asic.ch(channel).enable.pdetLG()

        # tempo.asic.ch(channel).set.tauHG(4)  # 4 x 20 ns = 80 ns
        # tempo.asic.ch(channel).set.tauHG(15)
        # tempo.asic.ch(channel).set.pahgGain(15)
        # tempo.asic.ch(channel).set.tauLG(4)  # 4 x 20 ns = 80 ns
        # tempo.asic.ch(channel).set.palgGain(1)

    print(np.sort(ASIC_channels_list), "injected channels")
    config['enable_TL_ASIC_ch'].append(ASIC_channels_list)
    config['tdc_injected'].append(['low']) # , 'high'
    config['power_cluster'].append(clusters_list)
    probed_channel = None #config['enable_TL_ASIC_ch'][-1]
    config['probed_channel'].append(probed_channel)

    if probed_channel is not None:
        print("probed_channel : ", probed_channel)
        tempo.fpga.set.hit_register_channel(probed_channel)
        tempo.asic.ch(probed_channel).select.analogProbe.shL()
        tempo.asic.common.probeDig.channel(probed_channel).TrigT_H_RS()
        pass



def debug_scurve():

    config = {'save_folder': [],
              'tempo_dig_ck': [], 'enable_TL_ASIC_ch': [], 'injected_channel_SiPM': [], 'tdc_injected': [],
              'power_cluster': [],
              'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
              'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [], 'hv_eff_current': [],
              'hv_eff_voltage': [], 'probed_channel': [], 'current_time': [], 'log': [],
              'patGain': [], 'patComp': [], 'hv_voltage': [], 'hv_current': [],
              'ro_enable': [], 'dig_clock': [], 'all_cluster_ck': []}

    local_output_dir = "../" + output_dir + "/scurve/raw/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)
    

    # print("Setup CAEN HV")
    # hv = CAEN_HV()

    tempo = setup_tempo(config)
    board = config['board'][0]

    filepath_df_trigger_effiency_threshold_scan = local_output_dir + "B%d_trigger_effiency_threshold_scan.csv" % board

    # hv_voltage_list = list(range(58, 65, 2))
    # hv.set_voltage(hv_voltage_list[0])
    # time.sleep(4)

    # SiPM_channel_list = [19]  # [1, 6, 12, 19, 40, 48, 55, 61]

    # for hv_voltage in hv_voltage_list:
    #     hv.set_voltage(hv_voltage)
    #     time.sleep(2)
    #     i, v = tempo.hv.measure_SiPM_HV()
    #     print(i, v)

    # for SiPM_channel in SiPM_channel_list:
    #
    #         ASIC_channel_list = setup_channel(tempo, config, [SiPM_channel])

            # for patGain in [1, 4, 16, 32, 63]:  # [4]: #
            #     for patComp in [0, 1]:  # [0]: #
            #         print('patGain, patComp', patGain, patComp)

    ASIC_channel_list = list(range(64))
    # [0, 1] #
    setup_ASIC_channel(tempo, config, ASIC_channel_list)

    # for ASIC_channel in ASIC_channel_list:
    #     tempo.asic.ch(ASIC_channel).set.patGain(patGain)
    #     tempo.asic.ch(ASIC_channel).set.patComp(patComp)

    # scurve
    tempo.setup_scurve_all_ch()
    df_tmp = tempo.get_scurve_all_ch( range(150, 500, 1))

    # df_tmp['patGain'] = patGain
    # df_tmp['patComp'] = patComp
    # df_tmp['hv_voltage'] = round(v)
    # df_tmp['hv_current'] = i
    # df_tmp['ASIC_channel'] = ASIC_channel
    # df_tmp['SiPM_channel'] = SiPM_channel

    df_tmp.to_csv(filepath_df_trigger_effiency_threshold_scan, index=False)

    # config['patGain'].append(patGain)
    # config['patComp'].append(patComp)
    # config['hv_voltage'].append(v)
    # config['hv_current'].append(i)
    tempo.save_ASIC_and_FPGA_config(config)


def get_scurve_all_discri_individually_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDac,
                                                               min_TL_range_per_channel, min_TH_range_per_channel):
    if os.path.exists(file_calibDAC):
        df0 = pd.read_csv(file_calibDAC)
        df0 = df0[(df0['IbCalibDAC'] == IbCalibDAC) & (df0['calibDac'] == calibDac)]
    else:
        df0 = []

    if len(df0) == 0:
        df0 = tempo.get_scurve_all_discri_individually(min_TL_range_per_channel, min_TH_range_per_channel)
        df0['IbCalibDAC'] = IbCalibDAC
        df0['calibDac'] = calibDac
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_calibDAC, index=False)
    return df, df0


def get_scurve_all_discri_groupsize_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDac,
                                                               min_threshold_range_per_channel, discri_list):
    if os.path.exists(file_calibDAC):
        df0 = pd.read_csv(file_calibDAC)
        df0 = df0[(df0['IbCalibDAC'] == IbCalibDAC) & (df0['calibDac'] == calibDac)]
    else:
        df0 = []

    if len(df0) == 0:
        df0 = tempo.get_scurve_all_discri_bygroup(min_threshold_range_per_channel, discri_list=discri_list)
        df0['IbCalibDAC'] = IbCalibDAC
        df0['calibDac'] = calibDac
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_calibDAC, index=False)
    return df, df0

def get_scurve_all_ch_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDac, dac_range):
    if os.path.exists(file_calibDAC):
        df0 = pd.read_csv(file_calibDAC)
        df0 = df0[(df0['IbCalibDAC'] == IbCalibDAC) & (df0['calibDac'] == calibDac)]
    else:
        df0 = []

    if len(df0) == 0:
        df0 = tempo.get_scurve_all_ch(dac_range)
        df0['IbCalibDAC'] = IbCalibDAC
        df0['calibDac'] = calibDac
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_calibDAC, index=False)
    return df, df0



def calibDAC6b_linearity(board, asic_id):

    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/B%d_TPR%d/calibDAC6b/" % (board, asic_id)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    tempo = temporoc3(config)
    board = config['board'][0]
    calibDac_list = list(range(64)) # order matters from min to max (ie from max negative correction to null correction)
    discri_list = [1]


    setup_temporoc([tempo], config)
    tempo.setup_scurve_all_ch(discri_list=['TL'])

    file_calibDAC = local_output_dir + "B%d_trigger_effiency_threshold_scan.csv" % board
    file_T1_vs_calibDAC = local_output_dir + "B%d_T1_vs_calibDAC.csv" % board

    res = {'channel': [], 'IbCalibDAC': [], 'calibDAC': [], 'T1':[]}
    df = pd.DataFrame()

    for IbCalibDAC in [7]:
        # FIND DAC ratio dac10b/dac6b by sweeping THRESHOLDS for each Ib_calibDAC for each channel
        tempo.asic.bias.calibDac.Ib.set_4b(IbCalibDAC)
        print("### Ib_calibDAC = %d " % IbCalibDAC)

        global_dac_min = 0
        tmp = []
        # SWEEP DAC LOCAL from MIN 0 to MAX 63
        for calibDAC in calibDac_list:
            figname = "B%d_IbCalibDAC_%d_calibDac_%d" % (board, IbCalibDAC, calibDAC)
            tempo.asic.ch.all().set.calibDACT1(calibDAC)
            tempo.asic.ch.all().set.calibDACT2(calibDAC)
            time.sleep(0.1)

            # FIND THRESHOLD INTERVAL for lowest threshold among all calibDAC values (ie when calibDAC=0)
            if calibDAC == 0: # first value swept
                # COARSE STEP
                df_tmp = tempo.get_scurve_all_ch(range(0, 1023, 10), discri_list=discri_list)
                # df_tmp = tempo.get_scurve_all_discri_individually(0, 0, step=10)

                figtitle = "FIND THRESHOLD COARSE INTERVAL (coarse step)"
                (local_thresh_in_global_dacu_for_each_gain,
                 channel_to_ignore_for_each_gain) = analyse_poor_granularity_scurve(df_tmp,
                                                                                    local_output_dir + '/coarse_step/',
                                                                                    figname, board, figtitle,
                                                                                    discri_list=discri_list)
                global_dac_min = int(np.min(local_thresh_in_global_dacu_for_each_gain[np.nonzero(local_thresh_in_global_dacu_for_each_gain)])-20)

            # FINE STEP
            dac_range = range(global_dac_min, 1024, 1)
            df, df0 = get_scurve_all_ch_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDAC, dac_range)

            figtitle = "(fine step)"
            local_thresh_in_global_dacu_TL_calibDacTL_A, _, _ = analyse_scurve(df0, local_output_dir, figname, board, figtitle, discri_list=discri_list)

            global_dac_min = int(np.min(local_thresh_in_global_dacu_TL_calibDacTL_A[np.nonzero(local_thresh_in_global_dacu_TL_calibDacTL_A)])-10)
            tmp.append(local_thresh_in_global_dacu_TL_calibDacTL_A)

            res['channel'] += list(range(64))
            res['IbCalibDAC'] += [IbCalibDAC] * 64
            res['calibDAC'] += [calibDAC]*64
            res['T1'] += local_thresh_in_global_dacu_TL_calibDacTL_A.tolist()
            channel_looked = 0
            print("ch %d   calibDAC %d   T1 %.1f"%(channel_looked, calibDAC, local_thresh_in_global_dacu_TL_calibDacTL_A[channel_looked]))

        df_res = pd.DataFrame(res)
        df_res.to_csv(file_T1_vs_calibDAC, index=False)

    print("Done")


def calibDAC6b_neighbours(board, asic_id):

    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/B%d_TPR%d/calibDAC6b/" % (board, asic_id)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    tempo = temporoc3(config)
    board = config['board'][0]
    calibDac_list = list(range(64)) # order matters from min to max (ie from max negative correction to null correction)
    discri_list = [1]

    setup_temporoc([tempo], config)
    tempo.setup_scurve_all_ch(discri_list=['TL'])

    file_calibDAC = local_output_dir + "B%d_trigger_effiency_threshold_scan.csv" % board
    file_T1_vs_calibDAC = local_output_dir + "B%d_T1_vs_calibDAC.csv" % board

    res = {'channel': [], 'IbCalibDAC': [], 'calibDAC': [], 'T1':[]}
    df = pd.DataFrame()

    for IbCalibDAC in [15]:
        # FIND DAC ratio dac10b/dac6b by sweeping THRESHOLDS for each Ib_calibDAC for each channel
        tempo.asic.bias.calibDac.Ib.set_4b(IbCalibDAC)

        print("### Ib_calibDAC = %d " % tempo.asic.bias.calibDac.Ib.get())

        global_dac_min = 0
        tmp = []
        tempo.asic.ch(0).set.calibDACT1(0)
        tempo.asic.ch.all().set.calibDACT2(0)
        # tempo.asic.ch.all_except([0,1]).disable.all_discri()

        # SWEEP DAC LOCAL from MIN 0 to MAX 63
        for calibDAC in calibDac_list:
            figname = "B%d_IbCalibDAC_%d_calibDac_%d" % (board, IbCalibDAC, calibDAC)
            tempo.asic.ch.all_except([0]).set.calibDACT1(calibDAC)
            # tempo.asic.ch.all_except([0]).set.calibDacTH(calibDAC)
            tempo.asic.ch(0).set.calibDACT1(0)
            time.sleep(0.1)
            # print(tempo.asic.ch.all().get.calibDacTL())
            print(f"ch0 {tempo.asic.i2c.read_register(0, 5)}   ch1 {tempo.asic.i2c.read_register(1, 5)}")


            # FIND THRESHOLD INTERVAL for lowest threshold among all calibDAC values (ie when calibDAC=0)
            if calibDAC == 0: # first value swept
                # COARSE STEP
                df_tmp = tempo.get_scurve_all_ch(range(0, 1023, 10), discri_list=discri_list)
                # df_tmp = tempo.get_scurve_all_discri_individually(0, 0, step=10)

                figtitle = "FIND THRESHOLD COARSE INTERVAL (coarse step)"
                (local_thresh_in_global_dacu_for_each_gain,
                 channel_to_ignore_for_each_gain) = analyse_poor_granularity_scurve(df_tmp,
                                                                                    local_output_dir + '/coarse_step/',
                                                                                    figname, board, figtitle,
                                                                                    discri_list=discri_list)
                global_dac_min = int(np.min(local_thresh_in_global_dacu_for_each_gain[np.nonzero(local_thresh_in_global_dacu_for_each_gain)])-20)

            # FINE STEP
            dac_range = range(global_dac_min, 1024, 1)
            df, df0 = get_scurve_all_ch_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDAC, dac_range)

            figtitle = "(fine step)"
            local_thresh_in_global_dacu_TL_calibDacTL_A, _, _ = analyse_scurve(df0, local_output_dir, figname, board, figtitle, discri_list=discri_list)

            global_dac_min = int(np.min(local_thresh_in_global_dacu_TL_calibDacTL_A[np.nonzero(local_thresh_in_global_dacu_TL_calibDacTL_A)])-10)
            tmp.append(local_thresh_in_global_dacu_TL_calibDacTL_A)

            res['channel'] += list(range(64))
            res['IbCalibDAC'] += [IbCalibDAC] * 64
            res['calibDAC'] += [calibDAC]*64
            res['T1'] += local_thresh_in_global_dacu_TL_calibDacTL_A.tolist()
            channel_looked = 0
            print("ch %d   calibDAC %d   T1 %.1f"%(channel_looked, calibDAC, local_thresh_in_global_dacu_TL_calibDacTL_A[channel_looked]))

        df_res = pd.DataFrame(res)
        df_res.to_csv(file_T1_vs_calibDAC, index=False)

    print("Done")


def ib_calibDAC_characterisation(board, asic_id, force_index=None, enabled_discri='all', offline=False):
    # enabled_discri among low or high / 1 or 2

    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/B%d_TPR%d/ib_calibDAC/"%(board, asic_id)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config, forced_index=force_index)
    
    tempo = temporoc3(config)
    board = config['board'][0]
    calibDac_list = [0, 63]
    discri_list = [1,2]

    if offline:
        config_file = local_output_dir + "/config.yaml"
        with open(config_file, 'r') as outfile:
            config = yaml.safe_load(outfile)
    else:
        setup_temporoc([tempo], config)
        tempo.setup_scurve_all_ch(discri_list=discri_list)

    file_calibDAC = local_output_dir + "B%d_trigger_effiency_threshold_scan.csv" % board
    file_DACratio = local_output_dir + "B%d_DAC_ratio.csv" % board

    DAC_ratio_per_ch = {'channel': [], 'IbCalibDAC':[]}
    DAC_ratio_per_ch.update({'T%d_calibDac_%d'%(discri, calibDac):[]
                                            for calibDac in calibDac_list for discri in discri_list})
    DAC_ratio_per_ch.update({'T%d_DAC_ratio'%discri:[] for discri in discri_list})

    df = pd.DataFrame()
    for IbCalibDAC in range(8,0,-1): # start for high value because at a random low value, calibDAC will be unbiased
        # FIND DAC ratio dac10b/dac6b by sweeping THRESHOLDS for each Ib_calibDAC for each channel
        if not offline:
            tempo.asic.bias.calibDac.Ib.set_4b(IbCalibDAC)
        print("### Ib_calibDAC = %d " % IbCalibDAC)


        # SET DAC LOCAL to MIN then MAX  (min 0 can be out of global DAC range)
        for calibDac in calibDac_list:
            figname = "B%d_IbCalibDAC_%d_calibDac_%d" % (board, IbCalibDAC, calibDac)

            # FIND THRESHOLD INTERVAL
            if offline:
                df0 = pd.read_csv(file_calibDAC)
                df0 = df0[(df0['IbCalibDAC'] == IbCalibDAC) & (df0['calibDac'] == calibDac)]
            else:
                tempo.asic.ch.all().set.calibDACT1(calibDac)
                tempo.asic.ch.all().set.calibDACT2(calibDac)
                time.sleep(0.1)

                # COARSE STEP
                df_tmp = tempo.get_scurve_all_ch(range(0,1023,10), discri_list=discri_list)
                # df_tmp = tempo.get_scurve_all_discri_individually(0, 0, step=10)

                figtitle = "FIND THRESHOLD COARSE INTERVAL (coarse step)"
                (local_thresh_in_global_dacu_for_each_gain,
                 channel_to_ignore_for_each_gain) = analyse_poor_granularity_scurve(df_tmp, local_output_dir+'/coarse_step/',
                                                                                    figname, board, figtitle,
                                                                                    discri_list = discri_list)

                # SMALL STEP
                if enabled_discri == 'group':
                    df, df0 = get_scurve_all_discri_groupsize_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDac,
                                                                        local_thresh_in_global_dacu_for_each_gain-100, discri_list=discri_list)
                elif enabled_discri == 'one_by_one':
                    df, df0 = get_scurve_all_discri_individually_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDac,
                                                                                local_thresh_in_global_dacu_for_each_gain[0]-100,
                                                                                local_thresh_in_global_dacu_for_each_gain[1]-100)
                elif enabled_discri == 'all':
                    global_dac_min = np.clip(np.min(local_thresh_in_global_dacu_for_each_gain[np.nonzero(local_thresh_in_global_dacu_for_each_gain)])-20,0,1023)
                    dac_range = range(global_dac_min, 1024, 1)
                    df, df0 = get_scurve_all_ch_if_not_already_existing(tempo, df, file_calibDAC, IbCalibDAC, calibDac, dac_range)
                else:
                    print("Not reconized enabled_discri parameter "+str(enabled_discri))
                    exit(0)


            figtitle = "(fine step)"
            thresholds = analyse_scurve(df0, local_output_dir, figname, board, figtitle, discri_list = discri_list)
            for discri in discri_list:
                DAC_ratio_per_ch['T%d_calibDac_%d' % (discri, calibDac)] += thresholds[discri-1].tolist()


        # COMPUTE DAC_ratio = 10b_DAC_global / 6b_DAC_local
        for discri in discri_list:
            DAC_ratio =  np.array(DAC_ratio_per_ch['T%d_calibDac_%d' % (discri, calibDac_list[0])][-64:])
            DAC_ratio -= np.array(DAC_ratio_per_ch['T%d_calibDac_%d' % (discri, calibDac_list[1])][-64:])
            DAC_ratio /= (calibDac_list[0] - calibDac_list[1])
            DAC_ratio_per_ch['T%d_DAC_ratio'%discri] += list(DAC_ratio)

        DAC_ratio_per_ch['channel'] += list(range(64))
        DAC_ratio_per_ch['IbCalibDAC'] += [IbCalibDAC] * 64

        df_DACratio = pd.DataFrame(DAC_ratio_per_ch)
        df_DACratio.to_csv(file_DACratio, index=False)

    print("Done: see results in %s"%local_output_dir)
    tempo.close()
    return local_output_dir


if __name__ == '__main__':
    # board_asic_id = (6, 108)
    board_asic_id = (4, 104)
    # threshold_scan(*board_asic_id) #, forced_index=11)

    # threshold_scan2(6, 108)
    # basic_threshold_scan()
    # check_stable_i2c()
    # test_scurve()
    # ib_calibDAC_characterisation(5, 2)
    # ib_calibDAC_characterisation(2, 180)
    # ib_calibDAC_characterisation(6, 108)
    # force_index = 42
    # ibCalibDAC_folder = ib_calibDAC_characterisation(*board_asic_id) #, force_index=force_index)
    # calibDAC6b_linearity(*board_asic_id)
    # calibDAC6b_neighbours(*board_asic_id)
    # align_thresholds_with_scurve_following_IbcalibDAC_sweep(4,104,"../output/B4_TPR104/ib_calibDAC/73/raw/") #, forced_index=11)
    ibCalibDAC_folder = "../output/B4_TPR104/ib_calibDAC/91/raw/"
    align_thresholds_with_scurve_following_IbcalibDAC_sweep(*board_asic_id, ibCalibDAC_folder=ibCalibDAC_folder, forced_index=61)
