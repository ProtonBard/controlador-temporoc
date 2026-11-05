import pandas as pd

from acquire.basic import *
from acquire.coincidence_ext_trigger import *
from acquire.energy_spectrum_multi_ch import board_config_example
from acquire.internal_TDC import *
from acquire.uniformize_ch_reponse import *
from src.common_setup import *
from src.temporoc3 import *
import src.tools as tools

def common(board, asic_id, measure, force_index):

    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config) #, simu=True)

    local_output_dir = "../output/B%d_TPR%d/serial_test/%s/" % (board, asic_id, measure)
    find_new_folder_index(local_output_dir, config, forced_index=force_index)

    setup_temporoc([tempo], config, ext_trigger=True)

    return tempo, config


def DC_measurement(board, asic_id, force_index=None):
    
    visaController = tools.visaController(16)
    visaController.setup_DC_voltage()

    tempo, config = common(board, asic_id, 'DC_measurement', force_index)

    print("Connect Keithley Multimeter to JTAG.")
    print("Unplug jumpers on both VDDD and VDDA that short shunt resistor")
    print("So ASIC power consumption is measured")

    # JTAG footprint on evaluation board v1        #
    #       |     J3
    #       |   \\\\\\\\\
    #       |   \\20 19\\       -> 20 = Ctest SMA   19=GND
    #       |   \\18 17\\       -> 18 = VthQ        17=GND
    #       |   \\16 15\\       -> 16 = Vth1        15=GND
    #       |   \\14 13\\       -> 14 = analog probe (not SMA!) 13=GND
    #       |   \\12 11\\                                               -> 12 = GND     11=Vbg   (already routed)
    #       |   \\10  9\\                                               -> 10 = GND     9=temp   (already routed) (erroneous Vref_1V label on PCB)
    #       |   \\8   7\\                                               -> 8  = GND     7=Vbias1V(already routed)
    #       |   \\6   5\\                                               -> 6 = GND      5= X     (not connected )
    #       |   \\4   3\\                                               -> 4 = 1V2A     3=1V2AF  (already routed)
    #       |   \\2   1\\                                               -> 2 = 1V2D     1=1V2DF  (already routed)
    #       |   \\\\\\\\\   JTAG connector
    #       |
    #       | PCB edge       SMA analog probe    SMA Ctest
    #       |__________________________


    # Testpoints already router on evaluati board v1 PCB
    # measure_power_consumption(tempo, config, visaController, method='serial_test')
    # measure_BG(tempo, config, visaController, method='serial_test')

    # Testpoints should be manually connected
    # measure_channel_DC_levels(tempo, config, visaController, method='serial_test')
    # measure_Vth1Q_dac_range(tempo, config, visaController, method="serial_test")
    measure_inputDAC_dac_range(tempo, config, visaController, method="serial_test")
    # exit()
    print("Finished DC measurements for board B%d ! :)" % board)
    tempo.close()

def discri_alignement(board, asic_id, force_index=None):
    tempo, config = common(board, asic_id, 'discri_alignement', force_index)

    # SCURVES
    tempo.reset_power_check_correct_clock_init()
    tempo.init_ASIC()
    TL_efficiency_50_after_calib, TH_efficiency_50_after_calib = align_thresholds_with_scurve_align(tempo, config, display=False)
    print("Finished discriminator TL & TH alignment for board B%d ! :)" % board)
    tempo.close()


def ctest_injection(board, asic_id, force_index=None, file_calib_discri=None):
    tempo, config = common(board, asic_id, 'ctest_injection', force_index)
    scurve_with_injection(tempo, config, file_calib_discri=file_calib_discri)
    tempo.close()

def TDC_code_density(board, asic_id, force_index=None):
    tempo, config = common(board, asic_id, 'TDC_code_density', force_index)


    print('Digital RO tests')
    # TDC jitter with digital RO with external trigger
    # ADC pedestal
    setup_tdc_scan_code_density(tempo, config)

    # config['config_B%d' % board].update(board_config_example)
    # load_config([tempo], config)
    # tempo.asic.common.en.TQ()
    # tempo.asic.interface.dis.trigger_charge_inh() # take into account TQ
    # use_calib_time_discri(tempo)
    # tempo.asic.common.set.dacTL(200)
    # tempo.asic.common.set.dacTH(200)
    # tempo.asic.ch.all().enable.all_discri()
    # tempo.asic.ch.all().select.trigTL.internal()
    # tempo.asic.ch.all().select.trigTH.internal()

    # tempo.fpga.set.conv_syst_ASIC(1)
    # tempo.board_config['power_cluster']= [[0,1,2,3]]
    # tempo.board_config.update({"frame_count_cluster%d" % ci: [0] for ci in range(4)})
    # tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    # CAN not remove ONLY clocks
    # with firmware using a single 320 MHz clock from PLL if deserialization works in FPGA without cluster clocks
    # tempo.asic.common.dis.latch()

    # patch to get all frames
    tempo.asic.common.en.FallingEdgeDetectorL()
    # transform the latch into a falling edge detector
    tempo.asic.common.en.TL_polarity()
    # reverse the polarity of the discri in order to get a TOA in the end
    tempo.asic.common.en.FallingEdgeDetectorH()

    # tempo.asic.common.en.TH_polarity() # uncomment to get


    acquire_tdc_scan_code_density(tempo, config, required_events=1000)

    tempo.close()



def emulate_random_pulses_injection(board, asic_id, force_index=None):

    tempo, config = common(board, asic_id, 'TDC_code_density', force_index)

    print('emulate_random_pulses_injection')
    # TDC jitter with digital RO with external trigger
    # ADC pedestal
    # setup_tdc_scan_code_density(tempo, config)

    enable_TL_ASIC_ch = list(range(64))
    # clusters_list = np.unique(np.array(enable_TL_ASIC_ch) // 16).tolist()
    # enable_TL_ASIC_ch = [1,2,15]
    # clusters_list = [0]
    clusters_list = [0,1,2,3]
    tempo.asic.ch.all().enable.all_discri()
    tempo.asic.ch.all().select.trigTL.internal()
    tempo.asic.ch.all().select.trigTH.internal()
    use_calib_time_discri(tempo)

    # for injected_channel in enable_TL_ASIC_ch:
    #     tempo.asic.ch(injected_channel).select.trigTL.external()
    #     tempo.asic.ch(injected_channel).select.trigTH.internal()
    #     tempo.asic.ch(injected_channel).enable.TH()
    #     tempo.asic.ch(injected_channel).enable.TL()
    tempo.board_config['enable_TL_ASIC_ch'] =  [enable_TL_ASIC_ch]
    # tempo.board_config['injected_channel'] = [enable_TL_ASIC_ch]

    print("enable_TL_ASIC_ch: ",np.sort(enable_TL_ASIC_ch))
    update_config_dict(config, clusters_list)
    tempo.board_config['power_cluster'] = [clusters_list]
    print("injected clusters ", clusters_list)
    # tempo.board_config['tdc_injected'] = [['low']]
    tempo.board_config['tdc_injected'] = [['low', 'high']]
    # tempo.board_config['tdc_injected'] = [['high']]

    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)
    update_config_dict(tempo.board_config, clusters_list)

    # tempo.asic.ch.all_except(config['injected_channel']).disable.all_discri()


    # Bug description:
    # A poor number of frames have matching CPT between clusters with purely random input signals.
    # (Async external trigger won't show bug as all externally triggered channels will trigger simultaneously although random)
    # For each latch reset, if there are as many discri HIGH (out of 16 among a cluster for a given gain, due to random events)
    # as nb_trigger, then the digital will serialize a new frame immediately after the previous (once window_delay_length as expired)
    # without TDC and without lsb_cpt but with updated trigger table. Occupies data bandwidth for nothing.

    # Hardware bug patch:
    tempo.asic.common.en.FallingEdgeDetectorL()
    tempo.asic.common.en.FallingEdgeDetectorH()
    # transform every trigger latch into a falling edge detector, thus the digital does not react on level any more but on falling edges
    # an edge forces the TDC to convert and the digital to update lsb cpt values (on TDC data valid)

    tempo.asic.common.en.TL_polarity()    # reverse the polarity of the discri in order to get a TOA in the end
    # tempo.asic.common.en.TH_polarity() # uncomment to get TOA2 instead of TOE2 for computing TOT = TOE2-TOA1

    # thresholds in pedestal
    tempo.asic.common.set.dacTL(105)
    tempo.asic.common.set.dacTH(200)


    tempo.save_ASIC_and_FPGA_config(config)

    ### debug
    # tempo.asic.common.probeDig.cluster(0).selectADCHG()
    tempo.asic.common.probeDig.channel(1).TrigT_H()
    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT6_select.digit_probe()
    tempo.fpga.OUT3_select.or_trig_h_rs()
    tempo.fpga.OUT2_select.or_trig_l_rs()

    tempo.fpga.set.resetn_digital_ASIC(0)
    tempo.deserializer.reset_fifo_for_all_cluster()
    tempo.fpga.set.resetn_digital_ASIC(1)

    # suffix = ''
    # csv_file_list = [config['save_folder'] + "B%d_cluster_%d%s.csv" % (tempo.board, cluster, suffix) for cluster in
    #                  tempo.board_config['power_cluster'][0]]
    # tempo.deserializer.extract_all(csv_file_list, tempo.board_config)
    acquire_data_multi_boards_safe(10000, config, [tempo])

    tempo.close()


def TOT_sweep(board, asic_id, force_index=None):

    ext_pulser = tektronix_AFG()

    tempo, config = common(board, asic_id, 'TDC_code_density', force_index)

    print('TOT sweep')
    # TDC jitter with digital RO with external trigger
    # ADC pedestal
    # setup_tdc_scan_code_density(tempo, config)

    # enable_TL_ASIC_ch = list(range(64))
    # clusters_list = np.unique(np.array(enable_TL_ASIC_ch) // 16).tolist()
    enable_TL_ASIC_ch = [1,2,15]
    # clusters_list = [0]
    clusters_list = [0,1,2,3]
    tempo.asic.ch.all().disable.all_discri()
    # tempo.asic.ch.all().select.trigTL.internal()
    # tempo.asic.ch.all().select.trigTH.internal()

    for injected_channel in enable_TL_ASIC_ch:
        tempo.asic.ch(injected_channel).select.trigTL.external()
        tempo.asic.ch(injected_channel).select.trigTH.internal()
        tempo.asic.ch(injected_channel).enable.TH()
        tempo.asic.ch(injected_channel).enable.TL()
    tempo.board_config['enable_TL_ASIC_ch'] =  [enable_TL_ASIC_ch]
    # tempo.board_config['injected_channel'] = [enable_TL_ASIC_ch]

    print("enable_TL_ASIC_ch: ",np.sort(enable_TL_ASIC_ch))
    update_config_dict(config, clusters_list)
    tempo.board_config['power_cluster'] = [clusters_list]
    print("injected clusters ", clusters_list)
    # tempo.board_config['tdc_injected'] = [['low']]
    tempo.board_config['tdc_injected'] = [['low', 'high']]
    # tempo.board_config['tdc_injected'] = [['high']]

    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)
    update_config_dict(tempo.board_config, clusters_list)

    # tempo.asic.ch.all_except(config['injected_channel']).disable.all_discri()


    tempo.save_ASIC_and_FPGA_config(config)

    # patch to get all frames
    tempo.asic.common.en.FallingEdgeDetectorL()
    # transform the latch into a falling edge detector

    tempo.asic.common.en.TL_polarity()
    # reverse the polarity of the discri in order to get a TOA in the end

    tempo.asic.common.en.FallingEdgeDetectorH()
    tempo.asic.common.set.dacTL(400)
    tempo.asic.common.set.dacTH(400)
    # tempo.asic.common.en.TH_polarity() # uncomment to get

    ext_pulser.ext_trigger_TOT_sweep()
    ext_pulser.enable_output()

    ### debug
    tempo.asic.common.probeDig.channel(1).TrigT_H()
    # tempo.asic.common.probeDig.cluster(0).selectADCHG()
    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT6_select.digit_probe()

    tempo.fpga.OUT3_select.or_trig_h_rs()
    tempo.fpga.OUT2_select.or_trig_l_rs()

    for width in range(4,200,10):
        suffix = '_nsWidth_%d' % width

        tempo.fpga.set.resetn_digital_ASIC(0)
        tempo.deserializer.reset_fifo_for_all_cluster()
        tempo.fpga.set.resetn_digital_ASIC(1)
        ext_pulser.AFG.query("SOURce1:PULSe:WIDTh %dns;*OPC?" % width)
        time.sleep(0.01)
        ext_pulser.trigger()
        time.sleep(0.01)
        csv_file_list = [config['save_folder'] + "B%d_cluster_%d%s.csv" % (tempo.board, cluster, suffix) for cluster in
                         tempo.board_config['power_cluster'][0]]
        tempo.deserializer.extract_all(csv_file_list, tempo.board_config)


    ext_pulser.close()

    tempo.close()


def explore_mimic_time_counter_offset(board, asic_id, force_index=None):
    tempo, config = common(board, asic_id, 'mimic_time_counter_offsetS', force_index)

    print('Measure offset for mimic time counter as a function of the readout mode')
    setup_tdc_scan_code_density(tempo, config)

    ROmode_list = []
    conf_list = []
    adc_mux_list = []
    event_window_length_list = []
    shaper_delay_length_list = []

    # used for debug
    # tempo.asic.interface.select.dig_modeRO(1)
    # # tempo.fpga.OUT2_select.ser_clk(0)
    # tempo.fpga.OUT3_select.ser_data(0)
    # tempo.asic.interface.en.Nor_TrigT_L_RS()
    # tempo.asic.interface.en.Nor_TrigT_H_RS()
    # tempo.asic.interface.en.digital_probe()
    # tempo.asic.common.set.event_window_length(63)
    # tempo.asic.interface.set.nb_trigger(1)
    # tempo.fpga.OUT4_select.ser_time_cpt_sampled(0)
    # tempo.fpga.pulser.set_divider(500)
    #
    # tempo.fpga.OUT2_select.digit_probe()
    # tempo.asic.common.probeDig.channel(2).TrigT_L_RS()
    # print(tempo.asic.common.probeDig.digital_probe)
    # # tempo.asic.common.probeDig.channel(2).off()
    # tempo.asic.common.probeDig.cluster(0).rstn_latch_int()
    # print(tempo.asic.common.probeDig.digital_probe)
    #
    # tempo.asic.common.set.event_window_length(63)
    # tempo.asic.common.set.shaper_delay_length(31)
    # tempo.fpga.reset.tpr_digital()

    acquire_tdc_scan_code_density(tempo, config, required_events=10000, suffix='_conf%d' % 1, force_reset=False)

    conf = 0

    tempo.asic.interface.select.dig_modeRO('fuller')
    tempo.asic.interface.en.slow_adc_mux()  # default is fast, try with slow readout
    acquire_tdc_scan_code_density(tempo, config, required_events=10000, suffix='_conf%d' % conf)
    conf_list.append(conf)
    ROmode_list.append(31)
    adc_mux_list.append('slow')
    event_window_length_list.append(63)
    shaper_delay_length_list.append(31)
    conf += 1

    tempo.asic.interface.dis.slow_adc_mux()  # default is fast
    for ROmode in range(32):
        tempo.asic.interface.select.dig_modeRO(ROmode)

        acquire_tdc_scan_code_density(tempo, config, required_events=10000, suffix='_conf%d' % conf, force_reset=False)

        conf_list.append(conf)
        ROmode_list.append(ROmode)
        adc_mux_list.append('fast')
        event_window_length_list.append(63)
        shaper_delay_length_list.append(31)
        conf += 1

    tempo.asic.interface.select.dig_modeRO('fuller')
    tempo.asic.interface.en.slow_adc_mux()  # default is fast, try with slow readout
    acquire_tdc_scan_code_density(tempo, config, required_events=10000, suffix='_conf%d' % conf, force_reset=False)
    conf_list.append(conf)
    ROmode_list.append(31)
    adc_mux_list.append('slow')
    event_window_length_list.append(63)
    shaper_delay_length_list.append(31)
    conf += 1


    tempo.asic.interface.select.dig_modeRO('lg_adc_low_tdc')
    tempo.asic.interface.en.slow_adc_mux()  # default is fast, try with slow readout
    acquire_tdc_scan_code_density(tempo, config, required_events=10000, suffix='_conf%d' % conf, force_reset=False)
    conf_list.append(conf)
    ROmode_list.append(0b00101)
    adc_mux_list.append('slow')
    event_window_length_list.append(63)
    shaper_delay_length_list.append(31)
    conf += 1


    tempo.asic.interface.select.dig_modeRO('fuller')
    tempo.asic.interface.dis.slow_adc_mux()  # default is fast
    for event_window_length in [0, 10, 32]:
        tempo.asic.common.set.event_window_length(event_window_length)
        acquire_tdc_scan_code_density(tempo, config, required_events=10000, suffix='_conf%d' % conf, force_reset=False)
        conf_list.append(conf)
        ROmode_list.append(31)
        adc_mux_list.append('fast')
        event_window_length_list.append(event_window_length)
        shaper_delay_length_list.append(31)
        conf += 1

    try:
        pd.DataFrame({'conf':conf_list,
                      'ROmode':ROmode_list,
                      'adc_mux':adc_mux_list,
                      'event_window_length':event_window_length_list}).to_csv(config['save_folder']+"conf.csv", index=False)
    except:
        pass

    tempo.close()

def TDC_scan_custom_step(board, asic_id, force_index=None):
    tempo, config = common(board, asic_id, 'TDC_scan_custom_step', force_index)

    setup_tdc_scan_custom_step(tempo, config)
    acquire_tdc_scan_custom_step(tempo, config)
    print("Finished tdc_scan_custom_step for board B%d ! :)" % board)
    tempo.close()


def perform_all_testplans(board, asic_id, force_index=None):

    tempo, config = common(board, asic_id, '', force_index)
    # todo
    print("Finished serial tests for board B%d ! :)" % board)
    tempo.close()


def scurve_with_injection(tempo: temporoc3, config, file_calib_discri=None):
    # injection should be done channel per channel, otherwise all 50 ohm resistors are seen in parallel from the ctest injection
    # too long to be a serial test on temporoc2
    # + metal track is very thin inside ASIC, thus 10 ohm resistor between ctest injection point in each channel will not reveal channel input connexion issues

    print("Connect 40 dB attenuation + 1 nF injection capacitor in serie between FPGA IO3 and CTEST ASIC input")

    board = tempo.board
    gain_list = ['TL', 'TH']
    save_folder = config['save_folder'] + '../scurve/'
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    if file_calib_discri is None:
        file_calib_discri = save_folder+"B%d_calib_discri.csv" % board
    file_scurve = save_folder+"B%d_trigger_effiency_threshold_scan.csv" %board

    figname = "4_inject_dacLocal_channelwise"
    print("Applying channel-wise discriminator calibration. Sweeping with fine step while injecting charge.")
    acquisition_time_ns = 500

    # tempo.asic.interface.en.digital_probe()
    # tempo.asic.common.probeDig.channel(0).

    # ALIGN THRESHOLDS
    need_to_perform_new_measure = True
    if os.path.exists(file_scurve):
        df0 = pd.read_csv(file_scurve)
        df0 = df0.loc[df0['step'] == 4]
        if len(df0)>0:
            need_to_perform_new_measure = False

    df_calib_discri = pd.read_csv(file_calib_discri)

    if need_to_perform_new_measure:
        tempo.setup_scurve_all_ch(gain_list)
        IbCalibDAC = tempo.asic.bias.calibDac.Ib.get()
        print("Configuration: IbCalibDAC = %d" % IbCalibDAC)

        tempo.setup_scurve_for_injection()

        for channel in range(64):
            if 'TL' in gain_list:
                dac_calib_value = int(
                    df_calib_discri.loc[df_calib_discri.channel == channel, 'TL_calib_DAC_local'].iloc[0])
                tempo.asic.ch(channel).set.calibDACT1(dac_calib_value)
                tempo.asic.ch(channel).set.calibDACT2(dac_calib_value)
            if 'TH' in gain_list:
                dac_calib_value = int(
                    df_calib_discri.loc[df_calib_discri.channel == channel, 'TH_calib_DAC_local'].iloc[0])
                tempo.asic.ch(channel).set.calibDACT2(dac_calib_value)

        # VERIFY THRESHOLD CALIBRATION
        if 'TL' in gain_list:
            DAC_global_min = int(df_calib_discri['TL_expected_DAC_global'].min())
        if 'TH' in gain_list:
            DAC_global_min = int(df_calib_discri['TH_expected_DAC_global'].min())
        if ('TL' in gain_list) and ('TH' in gain_list):
            DAC_global_min = int(min(int(df_calib_discri['TL_expected_DAC_global'].min()),
                                     df_calib_discri['TH_expected_DAC_global'].min()))

        DAC_global_max = 1023
        # DAC_global_max = 250
        if (DAC_global_min - 10) < 0:
            DAC_global_min = 10
        df0 = tempo.get_scurve_all_ch(range(DAC_global_min - 10, DAC_global_max + 5, 1), acquisition_time_ns=acquisition_time_ns)
        # df0 = tempo.get_scurve_all_ch(range(0, DAC_global_max + 5, 10), acquisition_time_ns=acquisition_time_ns)

        if 'TL' in gain_list:
            dac_calib_dict = {ch: df_calib_discri['TL_calib_DAC_local'][ch] for ch in range(64)}
            df0['calibDacTL'] = df0.channel.map(dac_calib_dict)
        if 'TH' in gain_list:
            dac_calib_dict = {ch: df_calib_discri['TH_calib_DAC_local'][ch] for ch in range(64)}
            df0['calibDacTH'] = df0.channel.map(dac_calib_dict)

        df0['step'] = 4
        if os.path.exists(file_scurve):
            df0 = pd.concat([pd.read_csv(file_scurve), df0], ignore_index=True)
        df0.to_csv(file_scurve, index=False)


    TL_efficiency_50_injection, TH_efficiency_50_injection, noise_injection = analyse_scurve(df0, save_folder,
                                                                                                   figname, board, dac_step=10)

    plt.figure(figsize=(13, 7))
    for gain in gain_list:
        plt.plot(range(64), df_calib_discri[gain + '_efficiency_50_after_calib'], marker='o', label='Pedestal '+gain, linestyle="--")
    plt.plot(range(64), TL_efficiency_50_injection, marker='o', color='tab:blue', label='Injection TL')
    plt.plot(range(64), TH_efficiency_50_injection, marker='o', color='tab:orange', label='Injection TH')

    plt.xlabel('Channel')
    plt.ylabel('Global thresholds [dac]')
    plt.title(f'Thresholds for discriminator')
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_folder + "Pedestal_vs_injection_thresholds.png")

    plt.show()
    plt.close()

def emulate_serial_test(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    # root_folder = "//192.168.2.149/temporoc/temoroc_sw/output/"
    root_folder = "Y:/temporoc_sw/output/"

    local_output_dir = root_folder + "../output/serial_test/B%d/" % board
    find_new_folder_index(local_output_dir, config, forced_index=12)

    tempo = temporoc3(config, simu=True)

    align_thresholds_with_scurve_align(tempo, config, display=False, just_rerun_analysis=True)

if __name__ == '__main__':


    # board_asic_id = (5, 2)
    # board_asic_id = (6, 108)
    # board_asic_id = (10, 61)
    # board_asic_id = (2, 180)
    board_asic_id = (4, 104)
    # board_asic_id = (7,37)
    # TDC_code_density(*board_asic_id)
    # DC_measurement(*board_asic_id)
    # explore_mimic_time_counter_offset(*board_asic_id)

    emulate_random_pulses_injection(*board_asic_id)

    # emulate_serial_test(4)

    # serial_test(5, ctest_injection=True, file_calib_discri = "../output/serial_test/B5/19/scurve/B5_calib_discri.csv") #, force_index=27)
    # serial_test(6, ctest_injection=True, file_calib_discri = "../output/serial_test/B6/0/scurve/B6_calib_discri.csv")
    #, discri_alignement=True, digitalRO_check=True)
    # serial_test(board, asic_id, digitalRO_check=True, force_flash_PLL=False)
    # serial_test(board, asic_id, digitalRO_check=True, force_flash_PLL=False)
    # serial_test(board, asic_id, digitalRO_check=True, force_flash_PLL=False)
    # serial_test(board, asic_id, tdc_scan_custom_step=True)

    # serial_test(4, discri_alignement=True)
    # serial_test(4, ctest_injection=True, file_calib_discri = "../output/serial_test/B4/15/scurve/B4_calib_discri.csv", force_index=15)

    # test_real_coincidence_without_SiPM_dual_board_but_ext_trigger(4, 6, local_output_dir = "../output/serial_test/coincidence_ext_trig/")
    # serial_test(3, digitalRO_check=True)



