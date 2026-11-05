import src.utils
from src.temporoc3 import *
from analyse.common_analysis_TDC import *
from datetime import datetime

output_dir = '../output/SiPM_characterisation'


def SiPM_analog_probe(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    # config = {'save_folder': [],
    #         'tempo_dig_ck': [], 'enable_TL_ASIC_ch': [], 'injected_channel_SiPM':[], 'tdc_injected': [],
    #         'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
    #         'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [], 'hv_eff_current': [],
    #         'hv_eff_voltage': [], 'probed_channel': [], 'current_time':[], 'log':[],
    #           'patGain':[], 'patComp':[], 'hv_voltage':[], 'hv_current':[],
    #           'ro_enable':[], 'dig_clock':[], 'all_cluster_ck':[]}

    local_output_dir = "../"+output_dir+"/raw/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)
    tempo = temporoc3(config)


    print("Setup CAEN HV")
    tempo.hv.connect()

    tempo = setup_tempo(config)
    board = config['board'][0]
    thres_scan_df = pd.DataFrame()
    filepath_df_threshold_scan = local_output_dir + "B%d_threshold_scan.csv" % board

    hv_voltage_list = list(range(58, 65, 2))
    tempo.hv.set_voltage(hv_voltage_list[0])
    time.sleep(4)

    SiPM_channel_list = [19] #[1, 6, 12, 19, 40, 48, 55, 61]

    for hv_voltage in hv_voltage_list:
        tempo.hv.set_voltage(hv_voltage)
        time.sleep(2)
        i, v = tempo.hv.measure_SiPM_HV()
        print(i, v)

        for SiPM_channel in SiPM_channel_list:

            ASIC_channel_list = setup_channel(tempo, config, [SiPM_channel])

            for patGain in [1, 4, 16, 32, 63]: #[4]: #
                for patComp in [0,1]:# [0]: #
                    print('patGain, patComp', patGain, patComp)

                    for ASIC_channel in ASIC_channel_list:
                        tempo.asic.ch(ASIC_channel).set.patGain(patGain)
                        tempo.asic.ch(ASIC_channel).set.patComp(patComp)

                        # scurve
                        df_tmp = tempo.common_threshold_scan(int(ASIC_channel), range(150, 1023, 1), None, time_acq_window=5e-3) #, verbose=True)
                        df_tmp['patGain'] = patGain
                        df_tmp['patComp'] = patComp
                        df_tmp['hv_voltage'] = round(v)
                        df_tmp['hv_current'] = i
                        df_tmp['ASIC_channel'] = ASIC_channel
                        df_tmp['SiPM_channel'] = SiPM_channel
                        thres_scan_df = pd.concat([thres_scan_df, df_tmp])
                        thres_scan_df.to_csv(filepath_df_threshold_scan, index=False)

                    config['patGain'].append(patGain)
                    config['patComp'].append(patComp)
                    config['hv_voltage'].append(v)
                    config['hv_current'].append(i)
                    tempo.save_ASIC_and_FPGA_config(config)


    thres_scan_df.to_csv(filepath_df_threshold_scan, index=False)

def measure_SiPM_HV(hv, config, board_label=''):
    hv_eff_current, hv_eff_voltage = hv.get_IV()
    # print(hv_eff_current, hv_eff_voltage)

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")

    config['current_time'].append(current_time)
    config['hv_eff_current'+board_label].append(hv_eff_current)
    config['hv_eff_voltage'+board_label].append(hv_eff_voltage)
    return hv_eff_current, hv_eff_voltage


def setup_channel(tempo, config, SiPM_channels_list):

    config['injected_channel_SiPM'] = SiPM_channels_list
    channels_list = get_ASIC_ch(SiPM_channels_list, config['SiPM_model'])
    clusters_list = np.unique(np.array(channels_list) // 16).tolist()
    src.utils.update_config_dict(config, clusters_list)
    # tempo.asic.ch.all_except(channels_list).disable.front_end_except_pdet()
    tempo.asic.ch.all_except(channels_list).disable.front_end()
    # tempo.asic.ch.group(channels_list).enable.front_end()

    for channel in channels_list:
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

    print(np.sort(channels_list), "injected channels")
    config['enable_TL_ASIC_ch'].append(channels_list)
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

    return channels_list

def setup_tempo(config):

    print("Connecting Temporoc")
    tempo = temporoc3(config)

    # raise device.FtdInterfaceError("test", tempo.dev)

    tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_sync_ext_trigger()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_40M_dig_ck()  # for internal ADC so no cross talk on MUX
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_80M_dig_ck()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_160M_dig_ck()

    tempo_dig_ck.append(tempo_dig_ck_freq)
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
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

    # Digital readout enable and Force conversion settings
    tempo.fpga.set.ro_enable_ASIC(1)
    # tempo.fpga.set.ro_enable_ASIC(0)
    tempo.asic.common.en.bypassResetMgmt()

    tempo.asic.interface.en.Inh_rstOnDlyH()  # mask end delay H for digital
    tempo.asic.interface.en.Inh_rstOnDlyL()

    # Val event and Trigger latch enabled
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()

    # Time Trigger and Threshold settings
    tempo.asic.bias.discri.TL.enable()
    tempo.asic.bias.discri.TH.enable()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacQ(1023)

    # Analog probe
    tempo.asic.interface.en.analog_probe()

    # Digital probe
    probed_cluster = None #config['enable_TL_ASIC_ch'][-1] // 16
    print('probed_cluster : ', probed_cluster)
    # tempo.IO.IO7_select.ser_data(probed_cluster)
    tempo.fpga.OUT7_select.digit_probe()
    # tempo.IO.IO7_select.pulse_tdc()
    # tempo.IO.OUT4_select.ser_clk(probed_cluster)
    tempo.fpga.OUT4_select.trig_t_l_rs_mux()

    # tempo.IO.OUT4_select.or_trig_q()
    # tempo.IO.OUT7_select.or_trig_q_rs()
    # tempo.IO.OUT4_select.ser_clk(probed_cluster)
    # tempo.IO.OUT4_select.ser_data(probed_cluster)
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
    tempo.asic.interface.en.trigQ_RS_mux()

    # tempo.asic.common.probeDig.channel(channel).TrigT_H()
    # tempo.asic.common.probeDig.channel(channel).TH()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L()
    # tempo.asic.common.probeDig.channel(channel).HOLD_delayed()
    # tempo.asic.common.probeDig.cluster(cluster).rstnADC()
    # tempo.asic.common.probeDig.cluster(cluster).rstnLatchInt()
    # tempo.asic.common.probeDig.cluster(cluster).end_delayH()
    # tempo.asic.common.probeDig.cluster(cluster).convDoneADCLG()

    readout_mode = 'full_adc_tdc'  # ,'lg_adc_low_tdc', 'hg_adc_low_tdc']   #, 'low_high_tdc', 'low_tdc', ]:
    config['readout_mode'].append(readout_mode)
    tempo.asic.interface.select.dig_modeRO(readout_mode)

    tempo.save_ASIC_and_FPGA_config(config)

    # print("Disabling all cluster clks")
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.fpga.select.ck_from_FPGA_to_ASIC.off()
    tempo.fpga.set.ro_enable_ASIC(0)

    config['ro_enable'].append(0)
    config['dig_clock'].append(0)
    config['all_cluster_ck'].append(0)
    return tempo


    # filepath_df_scurve = local_output_dir + "B%d_scurve.csv"% board
    # filepath_df_estimated_threshold = local_output_dir + "B%d_estimated_threshold.csv"% board


    # if os.path.exists(filepath_df_estimated_threshold):
    #     expected_threshold_df = pd.read_csv(filepath_df_estimated_threshold)
    # else:
    #     expected_threshold_df, fast_scurve_df = tempo.find_approximately_threshold_for_all_channels()
    #     fast_scurve_df.to_csv(filepath_df_scurve, index=False)
    #     expected_threshold_df.to_csv(filepath_df_estimated_threshold, index=False)
    #
    # if os.path.exists(filepath_df_threshold_scan):
    #     thres_scan_df = pd.read_csv(filepath_df_threshold_scan)
    #     # find channels left to sweep : where pedestal has not been found
    #     # channel_list_swept_not_null = thres_scan_df.loc[thres_scan_df.groupby('channel').TL_count.transform(lambda x: x.sum()==0), 'channel'].unique().tolist()
    #     channel_list_swept_not_null = thres_scan_df.groupby('channel').filter(lambda x: (x.TL_count.sum()!=0) & (x.TH_count.sum()!=0)).channel.unique()
    #     channel_list = set(channel_list_swept_not_null) ^ set(range(64))  # complementary list
    #     if 'acquisition_time_ms' not in thres_scan_df.columns:
    #         thres_scan_df['acquisition_time_ms'] = 2e-3 # default
    #     pass
    # else:
    #     thres_scan_df = pd.DataFrame()
    #     channel_list = range(64)
    #
    # channel_list = [62]
    #
    # # coarse step
    # print("Channels to explore with coarse step ", channel_list)
    # offset = 10
    # for channel in channel_list:
    #     TL = expected_threshold_df.loc[expected_threshold_df.channel == channel, 'low_thres_dac'].iloc[0] - offset
    #     TH = expected_threshold_df.loc[expected_threshold_df.channel == channel, 'high_thres_dac'].iloc[0] - offset
    #     df_tmp = tempo.common_threshold_scan(channel, thres_range_start_from_center(TL, 30,5), thres_range_start_from_center(TH, 30 ,5))
    #     thres_scan_df = pd.concat([thres_scan_df, df_tmp])
    #     thres_scan_df.to_csv(filepath_df_threshold_scan, index=False)
    #
    # # finest step
    # channel_list = np.unique(thres_scan_df.channel)
    # channel_list = [62]
    #
    # print("Channels to explore with fine step ", channel_list)
    # for channel in channel_list:
    #     selection = thres_scan_df.channel == channel
    #     TL = int(thres_scan_df.loc[selection, 'TL_dac'][thres_scan_df.loc[selection, 'TL_count'].idxmax()])
    #     TH = int(thres_scan_df.loc[selection, 'TH_dac'][thres_scan_df.loc[selection, 'TH_count'].idxmax()])
    #
    #     # find threshold left to sweep:
    #     TL_list_left = thres_range(TL, 10, 1)
    #     TH_list_left = thres_range(TH, 10, 1)
    #
    #     # # remove already scanned values
    #     # TL_list_left -= set(thres_scan_df.loc[selection, 'TL_dac'])
    #     # TH_list_left -= set(thres_scan_df.loc[selection, 'TH_dac'])
    #
    #     df_tmp = tempo.common_threshold_scan(int(channel), TL_list_left, TH_list_left, time_acq_window=10e-3)
    #     thres_scan_df = pd.concat([thres_scan_df, df_tmp])
    #     thres_scan_df.to_csv(filepath_df_threshold_scan, index=False)
    #
    # thres_scan_df.to_csv(filepath_df_threshold_scan, index=False)




    # regular data acquisition

    # tempo.deserializer.reset_fifo_for_all_cluster()
    # for cluster in range(4):
    #     config['total_nb_events_expected_cluster%d'%cluster] = 0
    # tempo.fpga.reset.digital()
    # tempo.deserializer.reset_fifo_for_all_cluster()
    # time.sleep(0.2)
    #
    # events_in_coincidence_so_far = 0
    # local_filepath_list = [local_output_dir + "B%d_VDDD_%.2fV_cluster_%d.csv" % (board, cluster) for cluster in clusters_list]
    #
    # if 1:
    #     while events_received < Nevents:
    #         events_asked_list = []
    #         for ci, cluster in enumerate(clusters_list):  # tolist to convert from numpy.int32 to int
    #             bytes_count = tempo.deserializer.get_number_of_bytes_in_fifo(cluster)
    #             # print(bytes_count)
    #             expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count/8 + 7
    #             events_asked = round(bytes_count / expected_bytes_per_event)
    #             events_asked_list.append(events_asked)
    #
    #             # close fifo before reading, so new events don't come meanwhile emptying
    #             pipe_ctrl = tempo.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
    #             tempo.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, pipe_ctrl | 1)
    #
    #             tempo.deserializer.extract_data(events_asked, cluster, local_filepath_list[ci], config)  # , verbose=True)
    #
    #             # reopen fifo for next round
    #             tempo.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, pipe_ctrl & 0b1111_1110)
    #
    #             config['total_nb_events_expected_cluster%d'%cluster] += events_asked
    #
    #
    #
    #         time.sleep(0.2)




    pass


if __name__ == "__main__":
    SiPM_analog_probe(1)