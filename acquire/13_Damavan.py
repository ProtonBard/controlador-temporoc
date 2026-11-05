import argparse
import time

import pandas as pd
from alive_progress import alive_bar
import yaml

from analyse.common_analysis import *
from src.utils import find_new_folder_index, thres_range
from src.common_setup import *
from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *
from src.CONSTANTS import *


def threshold_scan():
    config = {'CAEN_serial_number_to_board': {'AL04WEE3A': 1, 'AI05VLCGA': 2}, 'CAEN_serial_number': [],
              'save_folder': [],
              'tempo_dig_ck': [], 'enable_TL_ASIC_ch': [], 'injected_channel_SiPM': [], 'tdc_injected': [],
              'power_cluster': [],
              'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
              'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
              'probed_channel': [], 'current_time': [], 'log': [], 'start_time': 0, 'coincidence_rate': 0,
              'temperature_master': [], 'temperature_slave': [], 'patgain': [], 'dacTH': [], 'dacTL': [],
              'palgGain': [], 'tauLG': []}

    local_output_dir = "../output/Damavan/threshold_scan/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    plot_folder = local_output_dir+'../plot/'
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)

    SiPM_channels_list = ['A1', 'A2']
    SiPM_channels_list = [letter+str(number) for letter in ['E'] for number in range(1, 5)]
    # config['injected_channel_SiPM'].append(SiPM_channels_list)
    injected_channels_ASIC = get_ASIC_ch_Damavan(SiPM_channels_list)

    # injected_channels_ASIC.remove(16)
    # injected_channels_ASIC.remove(32)
    # injected_channels_ASIC.remove(48)
    injected_channels_ASIC = list(range(64))
    # injected_channels_ASIC = [37, 38]
    tempo = temporoc3(config)

    tempo = setup_temporoc([tempo], config, injected_channels_ASIC)
    tempo.fpga.select.trigger_mon.or_trig_l_rs()
    tempo.asic.interface.en.Nor_TrigT_L_RS()

    # cut the digital
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.pll.fpga.set.FPGA_as_clock_source()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.off()
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.fpga.resetn_digital_ASIC(0)

    # disable latch mode & reset from temporoc's digital
    tempo.asic.common.dis.tpr_latch()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.bypassResetMgmt()
    tempo.fpga.fpga.reset.latch_ASIC(1)

    tempo.asic.interface.select.global_trigger.ground()

    # patgain = 63
    # config['patgain'] = []
    # # injected_channels_ASIC = [8]
    # # config['enable_TL_ASIC_ch'] = [injected_channels_ASIC]
    # # tempo.asic.ch.all().disable.all_discri()
    #
    # for channel in injected_channels_ASIC:
    #     # Time PA gain
    #     tempo.asic.ch(channel).set.patGain(patgain)
    #     print('patgain', tempo.asic.ch(channel).get.patGain())
    #     config['patgain'].append(patgain)
    #
    #     tempo.asic.ch(channel).enable.cmd_test()
    #     tempo.asic.ch(channel).disable.use_ctest()
    #     tempo.asic.ch(channel).set.patComp(0)
    #
    #     tempo.asic.ch(channel).enable.TL()
    #     tempo.asic.ch(channel).disable.TH()
    #     tempo.asic.ch(channel).disable.TQ()

    # injected_channels_ASIC = [37, 38]

    file_calib_discri = "../config/TEMPOROC/B%d_calib_TL_staircase.csv" % 2
    if os.path.exists(file_calib_discri):
        print("Using staircase alignment from %s" % file_calib_discri)
        df_calib_discri = pd.read_csv(file_calib_discri)
        df_calib_discri.sort_values(by='channel', inplace=True)

        for channel in df_calib_discri.channel:
            dac_calib_value = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'calib_DAC_local'].iloc[0])
            tempo.asic.ch(channel).set.calibDACT1(dac_calib_value)

        aligned_discri_threshold = round(df_calib_discri.expected_aligned_pedestal.mean())

    else:
        print("No pedestal alignment found !")
        exit(0)

    # BIAS SIPM
    print("Turning ON the HV : 22Na radioactive source should be REMOVED")
    hv_voltage = 45
    hv = setup_hv(config)
    hv.set_voltage_modulating_ramp(hv_voltage, 33)
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    print(tempo.hv.save_periodically_SiPM_HV())

    thres_scan_df = pd.DataFrame()
    thres_scan_df_filename = local_output_dir + "B%d_trigger_counting_threshold_scan_HV_%.1f.csv" % (config['board'][0], hv_voltage)

    TL_list = range(aligned_discri_threshold-30, aligned_discri_threshold+100, 1)
    tempo.asic.ch.all().disable.all_discri()

    plt.figure(figsize=(14, 8))

    # tempo.asic.common.set.dacTL(183)
    # tempo.IO.OUT4_select.digit_probe()
    # tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()

    for inDAC in [0, 255]:
        tempo.asic.ch.all().set.inDac(inDAC)
        for channel in injected_channels_ASIC:
            tempo.asic.ch(channel).enable.TL()
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, None)
            df_tmp['inDAC'] = inDAC
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(thres_scan_df_filename, index=False)
            tempo.asic.ch(channel).disable.TL()

            plt.plot(df_tmp.TL_dac, df_tmp.TL_freq, label='ch %d dac %d'%(channel, inDAC))

    plt.grid()
    plt.yscale('log')
    plt.show()


        # plt.figure(figsize=(14, 8))
        #
        # gain = 'TL'
        # not_nan_selection = ~(thres_scan_df.loc[:, gain + '_dac'].isna())
        # for ci, channel in enumerate(config['enable_TL_ASIC_ch'][0]):
        #     selection = thres_scan_df.channel == channel
        #     thres_dac = thres_scan_df.loc[selection & not_nan_selection, gain + '_dac']
        #     counts = thres_scan_df.loc[selection & not_nan_selection, gain + '_freq']
        #     plt.plot(thres_dac, counts, label='ch%d HV %d' % (channel, hv_voltage), marker='+')
        #              # color = ax_list[ci][0].get_color())
        # plt.grid()
        # plt.legend()
        # plt.xlabel('Global threshold [dac]')
        # plt.ylabel('Trigger frequency')
        # plt.title("Trigger frequency counting rising edges")
        # plt.tight_layout()
        # plt.savefig(plot_folder + 'trigger_frequency_vs_threshold_HV_%.1f_inDAC_%d.png'%(hv_voltage, inDAC))
        # plt.close()

    # plt.show()
    pass

def align_SiPM_gain_with_inDAC():

    config = {'CAEN_serial_number_to_board': {'AL04WEE3A': 1, 'AI05VLCGA': 2}, 'SiPM_breakdown':33,
              'CAEN_serial_number': [],
              'save_folder': [],
              'tempo_dig_ck': [], 'enable_TL_ASIC_ch': [], 'injected_channel_SiPM': [], 'tdc_injected': [],
              'power_cluster': [],
              'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
              'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
              'probed_channel': [], 'current_time': [], 'log': [], 'start_time': 0, 'coincidence_rate': 0,
              'temperature_master': [], 'temperature_slave': [], 'patgain': [], 'dacTH': [], 'dacTL': [],
              'palgGain': [], 'tauLG': []}

    local_output_dir = "../output/Damavan/threshold_scan/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)



    injected_channels_ASIC = list(range(64))
    tempo = temporoc3(config)
    tempo = setup_temporoc([tempo], config, injected_channels_ASIC)

    hv_voltage = 45
    hv = setup_hv(config)

    common_align_SiPM_gain_with_inDAC(tempo, config, hv, hv_voltage, local_output_dir)

    # patgain = 63
    # config['patgain'] = []
    # # injected_channels_ASIC = [8]
    # # config['enable_TL_ASIC_ch'] = [injected_channels_ASIC]
    # # tempo.asic.ch.all().disable.all_discri()
    #
    # for channel in injected_channels_ASIC:
    #     # Time PA gain
    #     tempo.asic.ch(channel).set.patGain(patgain)
    #     print('patgain', tempo.asic.ch(channel).get.patGain())
    #     config['patgain'].append(patgain)
    #
    #     tempo.asic.ch(channel).enable.cmd_test()
    #     tempo.asic.ch(channel).disable.use_ctest()
    #     tempo.asic.ch(channel).set.patComp(0)
    #
    #     tempo.asic.ch(channel).enable.TL()
    #     tempo.asic.ch(channel).disable.TH()
    #     tempo.asic.ch(channel).disable.TQ()




    file_calib_inDAC = "../config/TEMPOROC/B%d_calib_inDAC.csv" % 2
    if os.path.exists(file_calib_inDAC):
        print("Using SiPM gain alignment from %s" % file_calib_inDAC)
        df_calib_inDAC = pd.read_csv(file_calib_inDAC)
        df_calib_inDAC.sort_values(by='channel', inplace=True)

        for channel in df_calib_inDAC.channel:
            inDAC_value = int(df_calib_inDAC.loc[df_calib_inDAC.channel == channel, 'inDAC_calib'].iloc[0])
            tempo.asic.ch(channel).set.inDac(inDAC_value)
    else:
        print("No SiPM gain alignment file found !")
        exit(0)



    thres_scan_df = pd.DataFrame()
    thres_scan_df_filename = local_output_dir + "B%d_trigger_counting_threshold_scan_HV_%.1f.csv" % (config['board'][0], hv_voltage)

    TL_list = range(aligned_discri_threshold-30, aligned_discri_threshold+100, 1)
    tempo.asic.ch.all().disable.all_discri()

    plt.figure(figsize=(14, 8))

    for channel in injected_channels_ASIC:
        tempo.asic.ch(channel).enable.TL()
        df_tmp = tempo.common_threshold_scan(int(channel), TL_list, None)
        inDAC_value = df_calib_inDAC.loc[df_calib_inDAC.channel == channel, 'inDAC_calib'].iloc[0]
        df_tmp['inDAC'] = inDAC_value
        thres_scan_df = pd.concat([thres_scan_df, df_tmp])
        thres_scan_df.to_csv(thres_scan_df_filename, index=False)
        tempo.asic.ch(channel).disable.TL()

        plt.plot(df_tmp.TL_dac, df_tmp.TL_freq, label='ch %d dac %d'%(channel, inDAC_value))

    plt.grid()
    plt.yscale('log')
    plt.show()




if __name__ == '__main__':
    pass
    # threshold_scan()
    # acquire_22Na_spectrum()
    # align_SiPM_gain_with_inDAC()