import argparse
import numpy as np
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


def run_scurve_alignment(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/scurve/"
    find_new_folder_index(local_output_dir, config)

    tempo = temporoc3(config)

    # For ALL channels (otherwise analysis fails)
    enabled_ASIC_ch = list(range(64))
    enable_TL_ASIC_ch = list(range(64))

    setup_temporoc([tempo], config)

    tempo.board_config['enabled_ASIC_ch'] = [enabled_ASIC_ch]
    print("enabled_ASIC_ch: ", np.sort(enabled_ASIC_ch))
    tempo.board_config['enable_TL_ASIC_ch'] = [enable_TL_ASIC_ch]

    TL_efficiency_50_after_calib, TH_efficiency_50_after_calib = align_thresholds_with_scurve_align(tempo, config)

    tempo.save_ASIC_and_FPGA_config(config)

    tempo.close()
    print("Done")



def threshold_scan(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/threshold_scan/"
    find_new_folder_index(local_output_dir, config)

    tempo = temporoc3(config,)

    setup_temporoc([tempo], config)

    # SiPM_channels_list = list(range(1, 62))
    # config['injected_channel_SiPM'].append(SiPM_channels_list)
    # injected_channels_ASIC = get_ASIC_ch(SiPM_channels_list)
    enabled_ASIC_ch = [8]
    enable_TL_ASIC_ch = [8]
    tempo.board_config['enabled_ASIC_ch'] = [enabled_ASIC_ch]
    print("enabled_ASIC_ch: ", np.sort(enabled_ASIC_ch))
    tempo.board_config['enable_TL_ASIC_ch'] = [enable_TL_ASIC_ch]

    setup_temporoc([tempo], config)

    tempo.asic.ch.all_except(enabled_ASIC_ch).disable.front_end_except_pdet()
    tempo.asic.ch.group(enable_TL_ASIC_ch).set.patGain(63)
    tempo.asic.ch.group(enable_TL_ASIC_ch).set.patComp(0)
    tempo.asic.ch.group(enable_TL_ASIC_ch).disable.all_discri()
    tempo.asic.ch.group(enable_TL_ASIC_ch).enable.TL()
    tempo.asic.ch.all_except(enabled_ASIC_ch).disable.all_discri()

    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.fpga.set.FPGA_as_clock_source()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.off()
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.asic.common.dis.tpr_latch()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.fpga.resetn_digital_ASIC(0)
    tempo.asic.interface.select.global_trigger.ground()

    # tempo.hv.connect()
    # tempo.hv.set_enHV(0)
    # time.sleep(1)
    # print(tempo.hv.measure_SiPM_HV())
    # time.sleep(1)
    # print(tempo.hv.measure_SiPM_HV())

    tempo.fpga.OUT4_select.digit_probe()
    # tempo.IO.OUT4_select.or_trig_l_rs()

    patgain = 1
    # tempo.asic.ch.all().disable.all_discri()

    for channel in enable_TL_ASIC_ch:
        # Time PA gain
        tempo.asic.ch(channel).set.patGain(patgain)
        print('patgain', tempo.asic.ch(channel).get.patGain())
        config['patgain'].append(patgain)

        tempo.asic.ch(channel).enable.cmd_test()
        tempo.asic.ch(channel).disable.use_ctest()
        tempo.asic.ch(channel).set.patComp(0)

        tempo.asic.ch(channel).enable.TL()
        tempo.asic.ch(channel).disable.TH()
        tempo.asic.ch(channel).disable.TQ()


    # print(tempo.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common))
    calib_TL_file = '../config/TEMPOROC/B%d_calib_TL.csv' % (config['board'][0])
    if not os.path.exists(calib_TL_file):
        print("Should run uniformize_ch_reponse.py first to get file %s "%calib_TL_file)
        exit(0)
    else:
        print("Aligning discri thresholds : using channelwise correction : %s" % calib_TL_file)
        df_calib_TL = pd.read_csv(calib_TL_file)
        TL_efficiency_50_after_calib = df_calib_TL.TL_efficiency_50_after_calib
        for channel in range(64):
            dac_calib_value = int(df_calib_TL.loc[df_calib_TL.channel == channel, 'calib_DAC_local'].iloc[0])
            tempo.asic.ch(channel).set.calibDACT1(dac_calib_value)


    # Check discriminator threshold alignments with threshold scan counting edges
    aligned_TL = round(np.mean(TL_efficiency_50_after_calib))
    # TL_list_left = thres_range(aligned_TL, 50, 1)
    TL_list_left = range(aligned_TL-30, 1023, 1)
    thres_scan_df = pd.DataFrame()
    thres_scan_df_filename = local_output_dir + "B%d_trigger_counting_threshold_scan.csv" % (config['board'][0])
    for channel in enable_TL_ASIC_ch:
        df_tmp = tempo.common_threshold_scan(int(channel), TL_list_left, None)
        thres_scan_df = pd.concat([thres_scan_df, df_tmp])
        thres_scan_df.to_csv(thres_scan_df_filename, index=False)

    gain = 'TL'
    plt.figure(figsize=(14, 8))
    not_nan_selection = ~(thres_scan_df.loc[:, gain + '_dac'].isna())
    for channel in config['enable_TL_ASIC_ch'][0]:
        selection = thres_scan_df.channel == channel
        thres_dac = thres_scan_df.loc[selection & not_nan_selection, gain + '_dac']
        counts = thres_scan_df.loc[selection & not_nan_selection, gain + '_freq']
        plt.plot(thres_dac, counts, label='ch%d HV OFF' % channel, linestyle='--')
    plt.axvline(x=aligned_TL, color='r', linestyle='--', label='TL aligned value')
    plt.grid()
    plt.legend()
    plt.yscale('log')
    plt.xlabel('Global threshold [dac]')
    plt.ylabel('Trigger frequency')
    plt.title("Trigger frequency counting rising edges (capped at 400 MHz due to fw)")
    plt.tight_layout()

    plt.savefig(config['output_folder'] + 'trigger_frequency_vs_threshold.png')
    # plt.show()
    # pass


    # BIAS SIPM
    print("Turning ON the HV : 22Na radioactive source should be REMOVED")
    hv_voltage = 59
    tempo.hv.set_voltage(hv_voltage)
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    print(tempo.hv.save_periodically_SiPM_HV())


    TL_list_left = range(round(np.mean(TL_efficiency_50_after_calib))-30, 1023, 1)
    thres_scan_df2 = pd.DataFrame()
    thres_scan_df_filename = local_output_dir + "B%d_trigger_counting_threshold_scan_HV_%.1f.csv" % (config['board'][0], hv_voltage)
    for channel in enable_TL_ASIC_ch:
        df_tmp = tempo.common_threshold_scan(int(channel), TL_list_left, None)
        thres_scan_df2 = pd.concat([thres_scan_df2, df_tmp])
        thres_scan_df2.to_csv(thres_scan_df_filename, index=False)

    gain = 'TL'
    # plt.figure(figsize=(14, 8))
    not_nan_selection = ~(thres_scan_df2.loc[:, gain + '_dac'].isna())
    for channel in config['enable_TL_ASIC_ch'][0]:
        selection = thres_scan_df2.channel == channel
        thres_dac = thres_scan_df2.loc[selection & not_nan_selection, gain + '_dac']
        counts = thres_scan_df2.loc[selection & not_nan_selection, gain + '_freq']
        plt.plot(thres_dac, counts, label='ch%d HV %d' % (channel, hv_voltage), marker='+')
    # plt.grid()
    plt.legend()
    # plt.yscale('log')
    # plt.xlabel('Global threshold [dac]')
    # plt.ylabel('Trigger frequency')
    # plt.title("Trigger frequency counting rising edges (capped at 400 MHz due to fw)")
    plt.tight_layout()
    plt.savefig(config['output_folder'] + 'trigger_frequency_vs_threshold_HV_%.1f.png'%hv_voltage)
    plt.show()

def align_SiPM_gain_with_inDAC(board, gain = 'TL'):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    # config = {'board': [1], 'save_folder': [], 'tempo_dig_ck': 80, 'readout_mode': [],
    #           'step': 0, 'restart_from_last_step': False,
    #           'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
    #           'current_time': [], 'log': [], 'start_time': 0, 'coincidence_rate': 0, 'debug': []}

    config.update({'staircase_acq_time': 300e-3})

    config['config_B1'].update({'SiPM_model': 'Hamamatsu_S13361_6597',
                           'SiPM_breakdown': 52.5,
                           'CAEN_serial_number': 'AL04WEE3A', 'light_source': '3x3x5mm_teflon_wrapped_LYSO',
                           'patgain': 4, 'dacTH': 1023, 'dacTL': 800, 'dacTQ': 600, 'charge_filter': False,
                           'palgGain': 1, 'tauLG': 15, 'target_hv': 57.5, 'tdc_injected': [['low', 'high']],
                           'deserialiser_time': 2200, 'enabled_TH_fb': False,
                           'enable_TL_ASIC_ch': [43],
                           'calib_time_discri': False, 'calib_inDAC': False, 'VDDD': 1.34})


    local_output_dir = "../output/align_SiPM_gain_with_inDAC/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    SiPM_channels_list = list(range(1, 62))
    # SiPM_channels_list = list(range(40, 62))
    injected_channels_ASIC = get_ASIC_ch(SiPM_channels_list, config['SiPM_model'])

    if config['step'] < 1:
        tempo = temporoc3(config, mode='')

        tempo = setup_temporoc([tempo], config, injected_channels_ASIC)
        df_calib_discri = setup_align_SiPM_gain_with_inDAC(tempo, config)
        thres_scan_df, pedestal_df = measure_align_SiPM_gain_with_inDAC(tempo, config)
        config['step'] = 1
    else:
        board = config['board'][0]
        hv_voltage = config['target_hv_voltage']

        thres_scan_df_filename = local_output_dir + "B%d_trigger_counting_threshold_scan_HV_%.1f.csv" % (board, hv_voltage)
        thres_scan_df = pd.read_csv(thres_scan_df_filename)

        pedestal_df_filename = local_output_dir + "B%d_trigger_counting_threshold_scan_pedestal.csv" % board
        pedestal_df = pd.read_csv(pedestal_df_filename)

        file_calib_discri = "../config/TEMPOROC/B%d_calib_TL_staircase.csv" % config['board'][0]
        df_calib_discri = pd.read_csv(file_calib_discri)

    # plot_all_channels_SiPM(thres_scan_df, config, 'biased_SiPM')
    # plot_all_channels_SiPM(pedestal_df, config, 'unbiased_SiPM')

    # BASED ON PE IDENTIFICATION
    # print("Find 1 pe for each channel each inDAC value")
    # res_df = find_1pe_amplitude(thres_scan_df, pedestal_df, config['plot_folder'])
    # plot_SiPM_non_uniformity(res_df, config['plot_folder'])

    file_calib_inDAC = local_output_dir + "B%d_calib_inDAC.csv" % 2

    if config['step'] < 2:
        # BASED ON PE SLOPE
        print("Find slope for each channel each inDAC value")
        slope_df = find_slope_staircase(thres_scan_df, df_calib_discri, config)
        slope_df.to_csv(config['save_folder'] + "SiPM_gain_slope_offset.csv", index=False)

        print("Find inDAC correction value to apply to each channel")
        target_slope = np.nanmedian(((slope_df.slope_inDAC_0.values + slope_df.slope_inDAC_255.values)/2))

        inDAC_lsb = (slope_df.slope_inDAC_255.values - slope_df.slope_inDAC_0.values) / 256
        inDAC_calib = np.int32(255 - ((slope_df.slope_inDAC_255.values - target_slope) / inDAC_lsb))
        inDAC_calib = np.clip(inDAC_calib, 0, 255)  # saturate to 8 bits
        print(inDAC_calib)
        slope_df['expected_corrected_slope'] = slope_df.slope_inDAC_255.values - inDAC_lsb * (255-inDAC_calib)

        res = {'channel': slope_df.channel, 'inDAC_lsb': inDAC_lsb, 'inDAC_calib': inDAC_calib,
                                       'expected_corrected_slope': slope_df['expected_corrected_slope']}



        df_calib_inDAC = pd.DataFrame(res)
        df_calib_inDAC.to_csv(file_calib_inDAC, index=False)
        config['step'] = 2
    else:
        df_calib_inDAC = pd.read_csv(file_calib_inDAC)
        slope_df = pd.read_csv(config['save_folder'] + "/SiPM_gain_slope_offset.csv")
        target_slope = np.nanmedian(((slope_df.slope_inDAC_0.values + slope_df.slope_inDAC_255.values) / 2))

    thres_scan_df_post_inDAC_calib_filename = config['save_folder'] + "/B%d_trigger_counting_threshold_scan_HV_%.1f_post_calib.csv" % (
                                 config['board'][0], config['target_hv_voltage'])
    if config['step'] < 3:
        if config['step'] > 1:
            tempo = temporoc3(config, mode='master')

            setup_temporoc([tempo], config, injected_channels_ASIC)
            df_calib_discri = setup_align_SiPM_gain_with_inDAC(tempo, config)

        print("Applying inDAC channel-wise correction")
        for channel in config['enable_TL_ASIC_ch'][0]:
            channel_inDac_correction = df_calib_inDAC.loc[df_calib_inDAC.channel == channel, 'inDAC_calib']
            # if len(channel_inDac_correction)==0:
            #     inDAC_value = 128
            # else:
            inDAC_value = int(channel_inDac_correction.iloc[0])
            tempo.asic.ch(channel).set.inDac(inDAC_value)

        print("Turning ON the HV : 22Na radioactive source should be REMOVED")
        tempo.hv.connect()
        # hv = setup_hv(config, serial_number=list(config['CAEN_serial_number_to_board'].keys())[
        #     list(config['CAEN_serial_number_to_board'].values()).index(config['board'][0])])
        tempo.hv.set_voltage_modulating_ramp(config['target_hv_voltage'], config['SiPM_breakdown'][config['SiPM_model']])
        time.sleep(2)
        print(tempo.hv.measure_SiPM_HV())
        time.sleep(2)
        print(tempo.hv.measure_SiPM_HV())
        time.sleep(2)
        print(tempo.hv.measure_SiPM_HV())
        print(tempo.hv.save_periodically_SiPM_HV())

        thres_scan_df_post_inDAC_calib = pd.DataFrame()
        print("Sweeping threshold")
        TL_list = range(config['aligned_discri_threshold'] - 30,
                        config['aligned_discri_threshold'] + 100, 1)
        tempo.asic.ch.all().disable.all_discri()

        # SiPM_channels_list = list(range(36, 62))
        # injected_channels_ASIC = get_ASIC_ch(SiPM_channels_list, config['SiPM_model'])
        for channel in config['enable_TL_ASIC_ch'][0]: # injected_channels_ASIC : #
            tempo.asic.ch(channel).enable.TL()
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, None,
                                                 time_acq_window=config['staircase_acq_time'])
            tempo.asic.ch(channel).disable.TL()
            inDAC_value = df_calib_inDAC.loc[df_calib_inDAC.channel == channel, 'inDAC_calib'].iloc[0]
            df_tmp['inDAC'] = inDAC_value
            thres_scan_df_post_inDAC_calib = pd.concat([thres_scan_df_post_inDAC_calib, df_tmp])
            thres_scan_df_post_inDAC_calib.to_csv(thres_scan_df_post_inDAC_calib_filename, index=False)

        save_config_file(config)
        hv.close()

        config['step'] = 3
    else:
         thres_scan_df_post_inDAC_calib = pd.read_csv(thres_scan_df_post_inDAC_calib_filename)

    plot_all_channels_SiPM(thres_scan_df_post_inDAC_calib, config, 'biased_SiPM_post_calib')

    print("Find slope for each channel with inDAC correction")
    slope_df_post_calib = find_slope_staircase(thres_scan_df_post_inDAC_calib, df_calib_discri, config, gain, post_calib=True)
    slope_df_post_calib.to_csv(config['save_folder'] + "/SiPM_gain_slope_offset_post_calib.csv", index=False)

    plot_per_channel = True
    if plot_per_channel:
        channel_folder = config['save_folder'] + '/../channel/'
        if not os.path.exists(channel_folder):
            os.makedirs(channel_folder)

        for channel in config['enable_TL_ASIC_ch'][0]:
            plt.figure(figsize=(14, 8))

            # Pedestal from staircase with unbiased sipm
            selection = (pedestal_df.channel == channel)
            plt.plot(pedestal_df.loc[selection, gain + '_dac'], pedestal_df.loc[selection, gain + '_freq'], label='unbiased SiPM')

            # Pedestal from last staircase
            pedestal = df_calib_discri.loc[df_calib_discri.channel == channel, 'expected_aligned_pedestal'].iloc[0]
            plt.axvline(pedestal, linestyle='--', color='red', label='pedestal')

            # Staircase with inDAC sweep extrema value
            for inDAC in np.unique(thres_scan_df.inDAC):
                selection = (thres_scan_df.channel == channel) & (thres_scan_df.inDAC == inDAC)

                thres_dac = thres_scan_df.loc[selection, gain + '_dac']
                counts = thres_scan_df.loc[selection, gain + '_freq']
                ax = plt.plot(thres_dac, counts, label='ch%d inDAC %d' % (channel, inDAC))

                slope = slope_df.loc[slope_df.channel==channel, 'slope_inDAC_%d' % inDAC].iloc[0]
                offset = slope_df.loc[slope_df.channel==channel, 'offset_inDAC_%d' % inDAC].iloc[0]

                if ~np.isnan(slope) & ~np.isnan(offset):
                    xfit = range(pedestal, max(thres_dac), 1)
                    plt.plot(xfit, np.exp(modelFitLinear(xfit, slope, offset)), linestyle='--', color=ax[0].get_color())

            # Staircase post_calib
            selection = (thres_scan_df_post_inDAC_calib.channel == channel)
            thres_dac = thres_scan_df_post_inDAC_calib.loc[selection, gain + '_dac']
            counts = thres_scan_df_post_inDAC_calib.loc[selection, gain + '_freq']
            inDAC_value = df_calib_inDAC.loc[df_calib_inDAC.channel == channel, 'inDAC_calib'].iloc[0]
            ax = plt.plot(thres_dac, counts, label='ch%d inDAC %d post calib' % (channel, inDAC_value))

            slope = slope_df_post_calib.loc[slope_df_post_calib.channel == channel, 'slope_inDAC_post_calib'].iloc[0]
            offset = slope_df_post_calib.loc[slope_df_post_calib.channel == channel, 'offset_inDAC_post_calib'].iloc[0]

            if ~np.isnan(slope) & ~np.isnan(offset):
                xfit = range(pedestal, max(thres_dac), 1)
                plt.plot(xfit, np.exp(modelFitLinear(xfit, slope, offset)), linestyle='--', color=ax[0].get_color())

            plt.grid()
            plt.legend()
            plt.yscale('log')
            plt.xlabel('Global threshold [dac]')
            plt.ylabel('Trigger rising edge count [Hz]')
            plt.title('Channel %d '%channel+gain)
            plt.tight_layout()
            plt.savefig(channel_folder + '/staircase_ch%d.png' % channel)
            # plt.show()
            plt.close()


    plt.figure(figsize=(14, 8))
    slope_df = slope_df[slope_df.channel != 32] # exclude absurd point
    # absolute unit
    # plt.plot(slope_df.slope_inDAC_0, label='slope_inDAC_0')
    # plt.plot(slope_df.slope_inDAC_255, label='slope_inDAC_255')
    # plt.fill_between(x=slope_df.channel, y1=slope_df.slope_inDAC_0, y2=slope_df.slope_inDAC_255, label='inDAC range', color='lightskyblue')
    # plt.scatter(slope_df.channel, corrected_slope, label='Expected correction', marker='o', color='green')
    # plt.axhline(y=target_slope, linestyle='dashed', color='red', label='Target (median of inDAC=128)')
    # plt.ylabel("SiPM gain [a.u.]")

    # relative units
    slope_df.sort_values(by='channel', inplace=True)
    plt.plot(slope_df.channel, (slope_df.slope_inDAC_255-target_slope)/target_slope*100, label='slope_inDAC_255', color='dodgerblue')
    plt.plot(slope_df.channel, (slope_df.slope_inDAC_0-target_slope)/target_slope*100, label='slope_inDAC_0', color='tab:orange')
    plt.fill_between(x=slope_df.channel, y1=(slope_df.slope_inDAC_0-target_slope)/target_slope*100,
                     y2=(slope_df.slope_inDAC_255-target_slope)/target_slope*100, label='inDAC range', color='lightskyblue')
    # plt.scatter(slope_df.channel, (expected_corrected_slope[slope_df.channel]-target_slope)/target_slope*100, label='Expected correction', marker='o', color='green')
    plt.scatter(df_calib_inDAC.channel, (df_calib_inDAC.expected_corrected_slope-target_slope)/target_slope*100, label='Expected correction', marker='o', color='green')
    plt.axhline(y=0, linestyle='dashed', color='red', label='Target (median of inDAC=128)')
    plt.scatter(slope_df_post_calib.channel, (slope_df_post_calib.slope_inDAC_post_calib-target_slope)/target_slope*100,
                label='Post calib', marker='x', color='red')


    plt.title('SiPM channel-wise non uniformity gain')
    plt.grid()
    plt.ylabel("Normalised SiPM gain dispersion [%]")
    plt.xlabel("Channel")
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['plot_folder']+'SiPM_gain_dispersion.png')
    plt.show()
    pass


if __name__ == '__main__':
    run_scurve_alignment(6)
    # threshold_scan(6)
    # align_SiPM_gain_with_inDAC()