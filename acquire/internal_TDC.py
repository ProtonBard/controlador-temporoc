import os
from typing import Literal

from alive_progress import alive_bar
from termcolor import colored

from analyse.common_data_decoding import is_data_mergeable
from src.temporoc3 import *
from analyse.common_analysis_TDC import *
import pickle
import yaml
import json
from src.common_setup import *
from src.tools import tektronix_AFG

output_dir = '../output/tdc_scan/internal/'

# using external trigger only!

def enable_one_TDC(tempo, whichTDC):
    if whichTDC=='low':
        pass
    elif whichTDC=='high':
        pass


def tdc_scan_10ps_step(tdc_enabled, tdc_channel_ext_trigger_enabled_list, channel_enabled_list):
    probed_channel = tdc_channel_ext_trigger_enabled_list[0] # first one
    N = 100
    hitFreq = 40

    subfolder = "TDC%dof%dch_%dChAnalogEnabled/"%(tdc_enabled, len(tdc_channel_ext_trigger_enabled_list), len(channel_enabled_list))
    output_folder = output_dir + "/tdc/10ps_step/"+subfolder

    # find unique acquistion number
    previous_acquisitions = glob.glob(output_folder+"/*/")  # (int([x[0] for x in os.walk(dir)][-1][-1]))
    if not previous_acquisitions:
        i = int(os.path.basename(previous_acquisitions[-1]))+1
    else:
        i=0
    output_folder += "/%d/raw/"%i
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print("Power on for both VDDD and VDDA")
    tempo = temporoc3(b'LI_', 3, "../config/temporoc2_hw_default_SC.csv")
    tempo.init_board()
    tempo.asic.interface.select.dig_modeRO.low_high_tdc()

    # disable analog (does not affect discri) for all channels except listed
    tempo.asic.ch.all_except(channel_enabled_list).disable.charge()
    tempo.asic.ch.all_except(channel_enabled_list).disable.timing()

    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacQ(1023)

    # should be there by default
    # tempo.asic.common.en.latch()
    # tempo.asic.interface.dis.Forced_ValEvt()

    tempo.asic.interface.en.digital_probe()

    # debug: check if reset cluster works from analog instead of digital
    # tempo.asic.common.en.bypassResetMgmt()

    # channel wise configuration
    for channel in tdc_channel_ext_trigger_enabled_list:
        if tdc_enabled==1:
            tempo.asic.ch(channel).enable.TL()
            tempo.asic.ch(channel).select.trigTL.external()
        elif tdc_enabled==2:
            tempo.asic.ch(channel).enable.TH()
            tempo.asic.ch(channel).select.trigTH.external()
        elif tdc_enabled==12:
            tempo.asic.ch(channel).enable.TL()
            tempo.asic.ch(channel).enable.TH()
            tempo.asic.ch(channel).select.trigTL.external()
            tempo.asic.ch(channel).select.trigTH.external()
        else:
            print("tdc_enabled value not understood")

    # cluster wise configuration
    cluster_enabled_list = np.unique(np.array(tdc_channel_ext_trigger_enabled_list)//16)
    tempo.deserializer.reset_fifo_for_all_cluster()
    tempo.asic.interface.dis.ClkDataRO_clusters_except(cluster_enabled_list)

    # DEBUG exclusive
    probed_cluster = probed_channel//16
    # check latch trigger output
    tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()

    # check latch see external trigger at its input
    # tempo.asic.common.probeDig.channel(probed_channel).TL()  # auto disable previous probe

    # check RstnLatchInt is not hold at zero during TDC conversion
    # tempo.asic.common.probeDig.cluster(probed_cluster).rstnLatchInt()

    # check TDC is not under reset
    # tempo.asic.common.probeDig.channel(probed_channel).rstn_TDC()

    # check digital is not under reset
    # tempo.asic.common.probeDig.cluster(probed_cluster).reset()

    # MASTER board send a pulse on IOFPGA1, then SMA cable,
    # then split with RF splitter to temporoc ext_trigger (be careful jumper JU13)
    # and to scope (trigger)

    # ACQUISITION
    for delay in range(2 ** 11):
        tempo.fpga.set.delay_ext_trigger(delay)
        tempo.pulse_ext_trigger_sync(N, hitFreq)

        # FPGA FIFO needs to wait until TDC datavalid flag is raised, error signal if exceeds 10 clocks cycles
        temperature = 0

        for cluster in cluster_enabled_list:
            start_time = time.perf_counter()
            while events_recorded := tempo.deserializer.get_number_of_bytes_in_fifo(cluster) < N:
                if time.perf_counter() - start_time > 10:
                    print("Only %d events are in fifo %d" % (events_recorded, cluster))
                    break
                time.sleep(0.1)
            csv_file = "/cluster_%d_N_%d_hitFreq_%d_delay_%d_temp_%d.csv" % (
                cluster, N, hitFreq, delay, temperature)
            tempo.deserializer.extract_data(N, cluster, output_folder + csv_file)  # todo expected or actual number of events ?

    build_unique_dataframe_from_clusters(output_folder)
    tempo.close()

def measure_testbench_jitter_with_FPGA_pulser():
    channel = 1

    output_folder = output_dir+"/delaybox_step/"

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print("Power on for both VDDD and VDDA")
    tempo = temporoc3(config)
    tempo.init_board()

    # disable analog & discri for all channels
    tempo.asic.ch.all().disable.charge()
    tempo.asic.ch.all().disable.timing()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacQ(1023)
    tempo.asic.interface.dis.ClkDataRO_cluster([1, 2, 3])

    # should be there by default
    # tempo.asic.common.en.latch()
    # tempo.asic.interface.dis.Forced_ValEvt()

    N = 100
    freq = tempo.fpga.pulser.get_frequency_in_Hz()
    board = int(tempo.dev.device.getDeviceInfo()['serial'][4:-1])
    VDDD = 1.3 if board==1 else 1.2
    options = "B%d_hit_%d_Hz_N_%d" % (board, freq, N)

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()
    # tempo.FPGA.pulser.disable()
    tempo.fpga.pulser.set_sync_mode()
    # tempo.FPGA.pulser.set_async_feedthrough_mode()
    tempo.fpga.pulser.set_nb_impulsions(N)
    tempo.fpga.pulser.set_frequency_in_Hz(78125) # not higher otherwise

    # debug: check if reset cluster works from analog instead of digital
    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT7_select.digit_probe()
    tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
    # tempo.asic.common.probeDig.cluster(0).rstnLatchInt()
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT1.en_ck320()
    # tempo.asic.common.en.bypassResetMgmt()

    tempo.asic.interface.select.dig_modeRO.low_high_tdc()
    # tempo.asic.interface.select.dig_modeRO.full_adc_tdc()
    # tempo.asic.interface.select.dig_modeRO.hg_adc_high_tdc()
    # tempo.asic.interface.select.dig_modeRO.lg_adc_low_tdc()
    # tempo.asic.interface.select.dig_modeRO.lg_adc_high_tdc()
    # tempo.asic.interface.select.dig_modeRO.lg_adc()
    # tempo.asic.interface.select.dig_modeRO.hg_adc()
    # tempo.asic.interface.select.dig_modeRO.hg_lg_adc()
    # tempo.asic.interface.select.dig_modeRO.high_tdc()
    # tempo.asic.interface.select.dig_modeRO.low_tdc()
    # tempo.asic.interface.select.dig_modeRO.hg_adc_low_tdc()
    # tempo.asic.interface.select.dig_modeRO.lg_adc_high_tdc()
    # tempo.asic.interface.select.dig_modeRO.hit()

    tempo.asic.ch(channel).select.trigTL.external()
    tempo.asic.ch(channel).select.trigTH.external()
    tempo.asic.ch(channel).enable.TH()
    tempo.asic.ch(channel).enable.TL()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()

    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.conv_syst_ASIC(0)

    # tempo.asic.interface.en.TDC_passthrough()
    delay = 1500 // (10 * 4)  # arbitrary value but insure constant constant value between acquisition
    # shift by 1.5 ns to have the TDC carac centered
    tempo.fpga.set.delay_ext_trigger(delay)

    while 1:
        tempo.fpga.pulser.launch()
    # connect on scope IO5 and IO0 : measure jitter on time difference
    tempo.close()

    pass


def measure_testbench_jitter_with_external_pulser():
    channel = 1

    print("Power on for both VDDD and VDDA")
    tempo = temporoc3(config)
    tempo.init_board()

    # disable analog & discri for all channels
    tempo.asic.ch.all().disable.charge()
    tempo.asic.ch.all().disable.timing()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacQ(1023)
    tempo.asic.interface.dis.ClkDataRO_cluster([1, 2, 3])

    # should be there by default
    # tempo.asic.common.en.latch()
    # tempo.asic.interface.dis.Forced_ValEvt()

    # debug: check if reset cluster works from analog instead of digital
    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT7_select.digit_probe()
    tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT1.en_ck320()
    # tempo.asic.common.en.bypassResetMgmt()

    tempo.asic.interface.select.dig_modeRO.low_tdc()

    tempo.asic.ch(channel).select.trigTL.external()
    tempo.asic.ch(channel).select.trigTH.external()
    tempo.asic.ch(channel).enable.TH()
    tempo.asic.ch(channel).enable.TL()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()

    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.conv_syst_ASIC(0)

    # tempo.asic.interface.en.TDC_passthrough()
    delay = 1500 // (10 * 4)  # arbitrary value but insure constant constant value between acquisition
    # shift by 1.5 ns to have the TDC carac centered
    tempo.fpga.set.delay_ext_trigger(delay)

    # while 1:
    #     tempo.FPGA.pulser.launch()

    # connect on scope IO5 and IO0 : measure jitter on time difference
    tempo.close()

    pass



# 1. TDC scan with sync hit delayed by 10 ps step for measuring absolute LSB
def tdc_scan_delaybox_step(serial_startswith, tempo_dig_ck_freq = 80):

    config = {'save_folder': [], 'tempo_dig_ck': [],
              'enable_TL_ASIC_ch': [], 'injected_channel_SiPM': [],
              'step': 0, 'restart_from_last_step': False,
              'staircase_acq_time': 300e-3,
              'tdc_injected': [], 'power_cluster': [],
              'VDDD': [], 'board': [], 'total_nb_events_expected': 0, 'nb_trigger': [], 'readout_mode': [],
              'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
              'probed_channel': [], 'current_time': [], 'log': [], 'start_time': 0,
              'patgain': [], 'dacTH': [], 'dacTL': [],
              'palgGain': [], 'tauLG': []}

    config.update({'hit_freq': [], 'pulser_type': [], 'delay':[]})

    ##### SETUP #####
    tempo = temporoc3(serial_startswith=serial_startswith)
    print("Connecting board %d" % tempo.board)

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()
    tempo.fpga.pulser.set_sync_mode()
    tempo.fpga.pulser.set_frequency_in_Hz(78125)  # not higher otherwise temporoc has not enough time to TX data
    tempo.fpga.pulser.release_resetn_latch()
    tempo.fpga.pulser.sync_enable_forever()

    freq = tempo.fpga.pulser.get_frequency_in_Hz()
    config['hit_freq'].append(freq)
    config['pulser_type'].append('FPGA')
    config['tempo_dig_ck'].append(tempo_dig_ck_freq)
    print('hit freq set to ', config['hit_freq'])
    print("Don't forget to plug jumper JU13 for FPGA pulser (left position)")

    tempo.deserializer.filter.disable.coincidence_inter_asic()
    tempo.fpga.select.foreign_eof.off()

    # Select temporoc digital clock
    tempo.fpga.set.PLL_as_clock_source()

    # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

    # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()

    tempo.pll.flash("../config/PLL/Si5345_11%s_ck_%dMHz-Registers.txt" % ('master', tempo_dig_ck_freq),
                    tempo_dig_clock=tempo_dig_ck_freq)
    # PLL outputs
    # 0 : FPGA clock : 80M
    # 3 : FPGA clock : 80M # What is the impact of the clock duty cycle deformation passing through the FPGA ?)
    # 6 : TEMPOROC digital : 80M
    # 7 : external hit resync CK : 320M
    # 8 : standalone TDC ck : OFF

    tempo.reset_power_check_correct_clock_init()

    tempo.asic.ch.all().disable.charge()
    tempo.asic.ch.all().disable.timing()
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacQ(1023)
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.dis.hyst_TL()

    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()
    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.conv_syst_ASIC(0)
    tempo.correct_default_HW_SC()


    local_output_dir = "../output/tdc_scan/internal/delaybox_step/dig_ck_%d_MHz/B%d/"%(tempo_dig_ck_freq, tempo.board)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    injected_channels_ASIC = list(range(64))
    # injected_channels_ASIC = [7, 23, 40, 48, 60]
    # injected_channels_ASIC = [43]

    for injected_channel in injected_channels_ASIC:
        tempo.asic.ch(injected_channel).select.trigTL.external()
        # tempo.asic.ch(injected_channel).select.trigTH.external()
        tempo.asic.ch(injected_channel).enable.TL()
        # tempo.asic.ch(injected_channel).enable.TH()

    config['enable_TL_ASIC_ch'].append(injected_channels_ASIC)

    print("injected channels: ", np.sort(injected_channels_ASIC))
    clusters_list = np.unique(np.array(injected_channels_ASIC) // 16).tolist()
    update_config_dict(config, clusters_list)
    config['power_cluster'].append(clusters_list)
    config['tdc_injected'].append(['low'])
    # config['tdc_injected'].append(['low', 'high'])

    print("injected clusters ", clusters_list)
    probed_channel = config['enable_TL_ASIC_ch'][-1]
    tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()

    nb_trigger = 16
    tempo.asic.interface.set.nb_trigger(nb_trigger)
    config['nb_trigger'].append(nb_trigger)

    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)

    # delay box should be inhibited because Temporoc internal digital
    tempo.asic.interface.en.Inh_rstOnDlyH()
    tempo.asic.interface.en.Inh_rstOnDlyL()

    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT4_select.digit_probe()
    # tempo.IO.OUT2_select.clk_320() # can check on scope that ck and trigger are never in phase1
    tempo.fpga.OUT2_select.pulse_tdc()

    readout_mode_list = ['full_adc_tdc']  # ['low_high_tdc']  # ['low_tdc'] #  # ,'lg_adc_low_tdc', 'hg_adc_low_tdc']
    config['readout_mode'].append(readout_mode_list)
    tempo.asic.interface.select.dig_modeRO(readout_mode_list[0])
    # print(tempo.asic.interface.select.dig_modeRO.RO_str)

    # deserialiser_time = tempo.asic.interface.select.dig_modeRO.RObit_count+50
    deserialiser_time = 2100
    tempo.deserializer.set_time(deserialiser_time)
    config['deserialiser_time'] = deserialiser_time

    config['sync_cluster'] = (tempo.dev.i2c.read_register(66, 5) & (1 << 5)) >> 5
    print("sync_cluster ", config['sync_cluster'])
    tempo.fpga.reset.tpr_digital()
    time.sleep(0.1)
    tempo.save_ASIC_and_FPGA_config(config)

    delay_list = np.arange(0, 100, 1)  # 2**10  2**10
    # with alive_bar(len(delay_list), force_tty=True) as bar:
    if 1:
        for delay in delay_list:
            tempo.fpga.set.delay_ext_trigger(delay)
            tempo.deserializer.reset_fifo_for_all_cluster()
            csv_file_list = [local_output_dir + "B%d_cluster_%d_delay_%d.csv" % (tempo.board, cluster, delay) for cluster in
                             config['power_cluster'][0]]
            events_extracted_list = tempo.deserializer.extract_all(csv_file_list, tempo.board_config)
            config['delay'].append(int(delay)) # otherwise yaml can not save numpy.int32 ...
            config['total_nb_events_expected'] += min(events_extracted_list)
    tempo.save_ASIC_and_FPGA_config(config)
    tempo.close()
    pass

    # for ci in range(4):
    #     if bytes_count[ci]!=0:
    #         print("either fifo reset is not working OR continuous pulse sequence")
    #     assert bytes_count[ci] == 0
    # # tempo.reset_fifo_for_cluster(0)
    # # bytes_count = tempo.deserializer.get_number_of_bytes_in_fifo(0)
    # # assert bytes_count == 0
    # tempo.fpga.reset.latch()
    #
    # # print("Number of bytes in fifo %d" % tempo.deserializer.get_number_of_bytes_in_fifo(cluster))
    # tempo.FPGA.pulser.launch()
    # time.sleep(0.005) # time to receive events
    #
    # a = tempo.deserializer.get_number_of_bytes_in_all_FIFO()
    # # tempo.asic.interface.set.nb_trigger(nb_trigger)
    # for cluster in np.unique(config['power_cluster']).tolist(): # tolist to convert from numpy.int32 to int
    #     bytes_count = tempo.deserialiser_get_number_of_bytes_in_fifo(cluster)
    #     if bytes_count == 0:
    #         time.sleep(0.005)
    #         bytes_count = tempo.deserialiser_get_number_of_bytes_in_fifo(cluster)
    #         if bytes_count == 0:
    #             print("Cluster %d abnormally empty !"%cluster)
    #
    #     local_filepath = filepath+'cluster_%d_delay%d.csv'%(cluster, delay)
    #
    #     iter = 0
    #     while bytes_count > 0:
    #         iter += 1
    #         events_asked = round(bytes_count / expected_bytes_per_event)
    #         tempo.deserializer.extract_data(events_asked, cluster, local_filepath, verbose=True)
    #         bytes_count = tempo.deserialiser_get_number_of_bytes_in_fifo(cluster)
    #
    #         if bytes_count > 0:
    #             print("Not expected bytes left in fifo: %d" % bytes_count)
    #             if iter==10:
    #                 print('cluster', cluster, 'delay', delay)
    #                 print("Check if FPGA pulser is indeed used on jumper JU13 (far away from ext_trig SMA)\nContinuous data streaming from the ASIC whereas expecting a fixed number of frames.")
    #                 exit()

# 2. TDC scan with random hit for measuring non-linearities
def tdc_scan_code_density(board):
    tempo_dig_clock_freq = 80
    config = {'board': [board], 'config_B%d'%board: {'board': board, 'mode': 'master'}}
    # config['config_B%d'%board] = {'tempo_dig_ck': 80}

    # pulser = 'external'
    # Use external pulser at a random frequency


    # 'save_folder': [],
    #           'enable_TL_ASIC_ch': [], 'injected_channel_SiPM': [],
    #           'step': 0, 'restart_from_last_step': False,
    #           'staircase_acq_time': 300e-3,
    #           'tdc_injected': [], 'power_cluster': [],
    #           'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
    #           'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
    #           'probed_channel': [], 'current_time': [], 'log': [], 'start_time': 0,
    #           'patgain': [], 'dacTH': [], 'dacTL': [],
    #           'palgGain': [], 'tauLG': []}

    config.update({'hit_freq': [], 'pulser_type': []})

    tempo = temporoc3(config)
    tempo.connect_ASIC()
    print("Connecting board %d" % tempo.board)

    local_output_dir = "../output/tdc_scan/internal/code_density/dig_ck_%d_MHz/B%d/"%(tempo_dig_clock_freq, tempo.board)
    find_new_folder_index(local_output_dir, config)

    setup_tdc_scan_code_density(tempo, config, tempo_dig_clock_freq)

    acquire_tdc_scan_code_density(tempo, config, required_events=100)

    tempo.save_ASIC_and_FPGA_config(config)

    tempo.close()


def setup_tdc_scan_code_density(tempo:temporoc3, config, tempo_dig_clock_freq=320, pulser='FPGA',
                                force_flash_PLL=True):
    config['source'] = 'ext_trigger'
    config['random_phase'] = True
    config['test'] = "Code density test with ext trigger using asynchronous test pulse injection generated by the FPGA"

    tempo.deserializer.filter.disable.coincidence_inter_asic()
    tempo.fpga.select.foreign_eof.off()

    board = config['board'][0]
    board_config = config['config_B%d'%board]
    FPGA_PLL = board_config['FPGA_PLL']

    if FPGA_PLL:
        # Select temporoc digital clock
        tempo.fpga.set.FPGA_as_clock_source()

    else:
        # Select temporoc digital clock
        tempo.fpga.set.PLL_as_clock_source()

        # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
        tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

        # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
        tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()

        FPGA_hit_freq = tempo.pll.configure_PLL_dig_ck_for_code_density(tempo_dig_clock_freq, force_flash_PLL=force_flash_PLL)

    tempo.board_config['tempo_dig_ck'] = tempo_dig_clock_freq

    tempo.reset_power_check_correct_clock_init(FPGA_PLL)

    tempo.board_config['pulser_type'] = pulser
    if pulser=='external':
        print("Connect TEKTRO AFG pulser OUT0 to ext trigger SMA")
        ext_pulser = tektronix_AFG()
        external_hit_freq = ext_pulser.ext_trigger(1506810)
        ext_pulser.continuous_mode()
        ext_pulser.enable_output()

        tempo.fpga.pulser.mask_on_ext_trigger()
        tempo.fpga.pulser.mask_on_IO0()
        tempo.fpga.pulser.disable()
        tempo.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset
        print("Don't forget to plug jumper JU13 for external pulser SMA input (right position)")

        tempo.board_config['hit_freq'] = external_hit_freq

        tempo.object_to_close_at_the_end.append(ext_pulser)

    elif pulser=='FPGA':
        # TEST SIGNAL: Setup FPGA pulser
        tempo.fpga.pulser.unmask_on_IO0()
        tempo.fpga.pulser.unmask_on_ext_trigger()
        # tempo.FPGA.pulser.set_async_feedthrough_mode()

        # hit derived from mother clock (PLL out0) should NOT be in phase with temporoc digital clock
        # use sync mode in order to produce short enough pulses so there is no consecutive triggers in a row
        tempo.fpga.pulser.set_sync_mode()
        tempo.fpga.pulser.sync_enable_forever()
        pulser_divider = 50
        pulser_divider = 150
        tempo.fpga.pulser.set_divider(pulser_divider)
        tempo.board_config['pulser_divider'] = pulser_divider
        # tempo.FPGA.pulser.set_nb_impulsions(N)
        # tempo.FPGA.pulser.set_frequency_in_Hz(1.25e6)
        # freq = tempo.FPGA.pulser.get_frequency_in_Hz()
        # tempo.FPGA.pulser.disable()

        delay = 0
        tempo.fpga.set.delay_ext_trigger(delay)
        tempo.board_config['delay_FPGA_pulser'] = delay
        print("Don't forget to plug jumper JU13 for FPGA pulser (left position)")

        if not FPGA_PLL:  # if external pll forwarding test pulse through DFF
            tempo.board_config['hit_freq'] = FPGA_hit_freq/pulser_divider

    else:
        print('Pulser mode %s not allowed'%pulser)
        exit()

    tempo.init_ASIC()

    tempo.fpga.pulser.release_resetn_latch()  # required, even if not using FPGA pulser

    # enable_TL_ASIC_ch = list(range(64))
    # clusters_list = np.unique(np.array(enable_TL_ASIC_ch) // 16).tolist()
    enable_TL_ASIC_ch = [1]
    clusters_list = [0]
    # clusters_list = [0,1,2,3]
    tempo.asic.ch.all().disable.all_discri()
    # tempo.asic.ch.all().select.trigTL.internal()
    # tempo.asic.ch.all().select.trigTH.internal()

    for injected_channel in enable_TL_ASIC_ch:
        tempo.asic.ch(injected_channel).select.trigTL.external()
        tempo.asic.ch(injected_channel).select.trigTH.external()
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

    ### debug
    tempo.asic.common.probeDig.channel(1).rstn_TDC()
    tempo.asic.common.probeDig.cluster(0).selectADCHG()
    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT4_select.digit_probe()


    # tempo.IO.OUT2_select.clk_320() # can check on scope that ck and trigger are never in phase1
    # tempo.fpga.OUT2_select.pulse_tdc()
    # tempo.fpga.OUT4_select.ser_time_cpt_sampled(0)
    tempo.fpga.OUT4_select.ser_clk(2)
    tempo.fpga.OUT2_select.ser_data(2)

    tempo.asic.interface.en.trigT_L_RS_mux()
    tempo.asic.interface.en.trigT_H_RS_mux()
    tempo.asic.interface.en.trigQ_RS_mux()

    # tempo.IO.IO5.en_ck40M()
    # tempo.IO.IO1.en_ck320()
    # tempo.asic.common.en.bypassResetMgmt()

    # deserialiser_time = tempo.asic.interface.select.dig_modeRO.RObit_count+50
    deserialiser_time = 0 #2100
    tempo.deserializer.set_time(deserialiser_time)
    tempo.board_config['deserialiser_time'] = deserialiser_time

    tempo.save_ASIC_and_FPGA_config(config)

def acquire_tdc_scan_code_density(tempo: temporoc3, config, required_events=200000, suffix='', force_reset=True):

    expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count / 8 + 18
    # #bytes = 1+1+1+asic frame+1+4+1+6+1= marker+frame length+marker+asic frame+marker+checksum+marker+time(32-bit ovf counter)+marker+ 48-bit mimic counter (at 320 MHz)+marker
    # # bytes = asic frame + 18
    fifo_max_number_events = round(2**15 / expected_bytes_per_event)
    number_acquistions = round(required_events / fifo_max_number_events)

    tempo.fpga.set.resetn_digital_ASIC(0)
    tempo.deserializer.reset_fifo_for_all_cluster()
    tempo.fpga.set.resetn_digital_ASIC(1)
    # tempo.fpga.reset.tpr_digital()

    # time.sleep(0.1)
    csv_file_list = [config['save_folder'] + "B%d_cluster_%d%s.csv" % (tempo.board, cluster, suffix) for cluster in tempo.board_config['power_cluster'][0]]

    # tempo.fpga.OUT2_select.digit_probe()
    # tempo.asic.common.probeDig.channel(3 * 16 + 0).TrigT_H()

    tempo.fpga.pulser.unmask_on_ext_trigger()
    # tempo.fpga.pulser.unmask_on_IO0()
    config['total_nb_events_expected'] = 0

    # tempo.asic.interface.en.tdc_ck()
    # tempo.asic.interface.dis.tdc_ck()
    #
    # tempo.asic.interface.en.tdc_trigger()
    # tempo.asic.interface.dis.tdc_trigger()
    #
    # tempo.asic.interface.en.sel_trigger_high()
    # tempo.asic.interface.dis.sel_trigger_high()

    # print("read register bit 7 "+bin(tempo.asic.i2c.read_register(0, 7)))
    # tempo.asic.ch.all().enable.tdcL()
    # tempo.asic.ch.all().disable.tdcL()
    # print("read register bit 7 "+bin(tempo.asic.i2c.read_register(0, 7)))

    # print("read register bit 7 "+bin(tempo.asic.i2c.read_register(65, 9)))
    # tempo.asic.common.dis.sel_tdc_rising_edge()
    # print("read register bit 7 "+bin(tempo.asic.i2c.read_register(65, 9)))
    board = config['board'][0]
    board_config = config['config_B%d'%board]
    if 'hit_freq' in board_config.keys():
        time_to_fill_fifo = fifo_max_number_events/board_config['hit_freq']
        print("Expected time to fill FIFO is %.2f ms with %d events " % (time_to_fill_fifo * 1e3, fifo_max_number_events))
    else:
        time_to_fill_fifo = 0

    # INITIALISATION
    if force_reset:
        # check Temporoc counters were reset to the same value initial value, for the first iteration
        reset_required = 0
        time.sleep(time_to_fill_fifo)
        temporoc_cluster_counters_aligned = True
        while temporoc_cluster_counters_aligned:

            events_extracted_list = tempo.deserializer.extract_all(csv_file_list, tempo.board_config)
            config['total_nb_events_expected'] += min(events_extracted_list)

            temporoc_cluster_counters_aligned = False

            # if is_data_mergeable(config):
            #     temporoc_cluster_counters_aligned=False
            # elif events_extracted_list==[0,0,0,0]:
            #     print("no events")
            # else:
            #     print("Will reset again Temporoc to ensure counters in each cluster have similar initial value")
            #     tempo.fpga.set.resetn_digital_ASIC(0)
            #     tempo.deserializer.reset_fifo_for_all_cluster()
            #     tempo.fpga.set.resetn_digital_ASIC(1)
            #
            #     for bi, board in enumerate(config['board']):
            #         files = glob.glob(config['save_folder'] + '/B%d_' % board + '*' + '%s.csv'%suffix)
            #         for file in files:
            #             os.remove(file)
            #     reset_required += 1
        print("Temporoc nb reset required to sync cluster counters: ", reset_required)
        config['init_reset_required'] = reset_required

    # NORMAL REGIME
    for i in range(number_acquistions-1):
        time.sleep(time_to_fill_fifo)

        events_extracted_list = tempo.deserializer.extract_all(csv_file_list, tempo.board_config)
        config['total_nb_events_expected'] += min(events_extracted_list)



    tempo.fpga.pulser.mask_on_ext_trigger()

    pass



# 3. TDC scan with async hit
def tdc_scan_custom_step(board):
    config = {'board': [board], 'config_B%d'%board: {'board': board, 'mode': 'master', 'tempo_dig_ck':80}}

    tempo = temporoc3(config)
    tempo.connect_ASIC()
    print("Connecting board %d" % tempo.board)

    local_output_dir = output_dir + "/custom_step/dig_ck_%d_MHz/" % tempo.board_config['tempo_dig_ck']
    find_new_folder_index(local_output_dir, config)

    setup_tdc_scan_custom_step(tempo, config)
    acquire_tdc_scan_custom_step(tempo, config)


def setup_tdc_scan_custom_step(tempo, config):
    config['source'] = 'ext_trigger'
    config['random_phase'] = True
    config['test'] = "Custom step"
    board_config = config['config_B%d' % config['board'][0]]
    board_config['tempo_dig_ck'] = 80

    board_config.update({'tdc_injected': [['low']], 'deserialiser_time': 0})
    config.update({'ck_cycles_in_between_2_hits': [], 'expected_step': [], 'current_step': [],
                   'hit_freq': [], 'pulser_type': [], 'PLL_config_file': []})

    ##### SETUP #####
    injected_channels_ASIC = list(range(64))
    # injected_channels_ASIC = [43, 42, 41]
    injected_channels_ASIC = [20, 31, 32, 43]

    (PLL_config_file, expected_step,
     ck_cycles_in_between_2_hits, hit_frequency, FPGA_divider, tempo_dig_clock_from_PLL_config) = select_PLL_config_file(config)

    tempo.deserializer.filter.disable.coincidence_inter_asic()
    tempo.fpga.select.foreign_eof.off()

    # Select temporoc digital clock
    tempo.fpga.set.PLL_as_clock_source()

    # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

    # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()


    tempo.pll.flash("../config/PLL/" + PLL_config_file, tempo_dig_clock=tempo_dig_clock_from_PLL_config)

    tempo.reset_power_check_correct_clock_init()
    tempo.correct_default_HW_SC()

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()

    freq_offset_added_to = 'hit' if tempo_dig_clock_from_PLL_config == (tempo_dig_clock_from_PLL_config*1e6) else 'tdc_ck'
    if freq_offset_added_to == 'tdc_ck': # vary temporoc digital & tdc clock frequency
        tempo.fpga.pulser.set_sync_mode()
        tempo.fpga.pulser.sync_enable_forever()
        tempo.fpga.pulser.set_frequency_in_Hz(hit_frequency)
        tempo.fpga.pulser.disable_resetn_latch()
        tempo.fpga.pulser.launch()
        pass

    elif freq_offset_added_to == 'hit':
        if FPGA_divider == 2:
            tempo.fpga.pulser.set_async_feedthrough_mode()
        else:
            tempo.fpga.pulser.set_sync_mode()
            tempo.fpga.pulser.sync_enable_forever()
            tempo.fpga.pulser.set_divider(FPGA_divider)

        pass

    delay = 0
    tempo.fpga.set.delay_ext_trigger(delay)
    config['delay_FPGA_pulser'] = delay
    print("Don't forget to plug jumper JU13 for FPGA pulser (left position)")

    # MANDATORY :
    tempo.fpga.pulser.release_resetn_latch()  # required, even if not using FPGA pulser
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()
    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.set.conv_syst_ASIC(0)


    config['pulser_type'] = 'FPGA'

    # delay box should be inhibited because Temporoc internal digital
    tempo.asic.interface.en.Inh_rstOnDlyH()
    tempo.asic.interface.en.Inh_rstOnDlyL()

    nb_trigger = 1
    tempo.asic.interface.set.nb_trigger(nb_trigger)
    tempo.board_config['nb_trigger'] = nb_trigger

    # SiPM_channels_list = [8, 54]
    # channels_list = get_ASIC_ch(SiPM_channels_list)
    # channels_list = [25, 34]
    tempo.asic.ch.all().disable.front_end()

    for injected_channel in injected_channels_ASIC:
        tempo.asic.ch(injected_channel).select.trigTL.external()
        # tempo.asic.ch(injected_channel).select.trigTH.external()
        # tempo.asic.ch(injected_channel).enable.TH()
        tempo.asic.ch(injected_channel).enable.TL()

    tempo.board_config['enable_TL_ASIC_ch'] = [injected_channels_ASIC]
    print("injected channels: ", np.sort(injected_channels_ASIC))
    clusters_list = np.unique(np.array(injected_channels_ASIC) // 16).tolist()
    update_config_dict(tempo.board_config, clusters_list)
    tempo.board_config['power_cluster'] = clusters_list
    print("power clusters ", clusters_list)
    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)

    probed_channel = tempo.board_config['enable_TL_ASIC_ch'][0][-1]
    probed_cluster = probed_channel//16
    tempo.asic.ch.all_except(tempo.board_config['enable_TL_ASIC_ch'][0]).disable.all_discri()

    tempo.asic.interface.en.digital_probe()
    tempo.fpga.OUT2_select.digit_probe()
    tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()

    # tempo.IO.OUT2_select.pulse_tdc()
    tempo.fpga.OUT4_select.ser_clk(probed_cluster)
    tempo.fpga.OUT2_select.time_cpt_sampled(probed_cluster)




    tempo.asic.interface.select.dig_modeRO(config['config_B%d'%config['board'][0]]['readout_mode'])
    print(tempo.asic.interface.select.dig_modeRO.RO_str)

    for cluster in range(4):
        config['total_nb_events_expected_cluster%d'%cluster] = 0

    tempo.deserializer.set_time(tempo.board_config['deserialiser_time'])
    tempo.deserializer.filter.disable.charge()
    tempo.deserializer.filter.disable.coincidence_inter_cluster()

    tempo.save_ASIC_and_FPGA_config(config)

def acquire_tdc_scan_custom_step(tempo:temporoc3, config):

    reset_FPGA_FIFO_and_tempo_digital([tempo])

    number_times_fifo_empty = 40
    expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count / 8 + 9  # + 9 bytes including 32 bits ovf counter
    fifo_max_number_events = round(2**15 / expected_bytes_per_event)

    acquire_data_multi_boards(number_times_fifo_empty*fifo_max_number_events, config, [tempo])



def select_PLL_config_file(config):
    board = config['board'][0]
    tdc_ck = config['config_B%d'%board]['tempo_dig_ck']

    if tdc_ck == 80:
        # Method BEST
        PLL_config_file = "Si5345_32_hit_and_CK_80000080_Hz_tdc_ck_80000000_Hz_step_5ps-Registers.txt"
        expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(200e3, 5e-12, tdc_clock_freq=80e6, hit_given_by='best')

        # PLL_config_file = "Si5345_32_hit_and_CK_80000160_Hz_tdc_ck_80000000_Hz_step_10ps-Registers.txt"
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(200e3, 10e-12, tdc_clock_freq=80e6, hit_given_by='best')

        # PLL_config_file = "Si5345_32_hit_and_CK_80000800.008_Hz_tdc_ck_80000000_Hz_step_50ps-Registers.txt"
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(200e3, 50e-12, tdc_clock_freq=80e6, hit_given_by='best')

        # Method PLL
        # PLL_config_file = "Si5345_33_hit_and_CK_400000.4_Hz_tdc_ck_80000000_Hz_step_5ps-Registers.txt"
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = (
        #     frequency_planner(200e3, 5e-12, tdc_clock_freq=80e6, hit_given_by='PLL'))


        # Method FPGA
        # PLL_config_file = ""
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = (
        #     frequency_planner(200e3, 5e-12, tdc_clock_freq=80e6, hit_given_by='FPGA'))
        pass

    elif tdc_ck == 320:
        PLL_config_file = "Si5345_5_hit_1250003_Hz_CK_2500006_Hz_step_2ps.txt"
        # PLL outputs
        # 0 : FPGA clock : 1 250 003 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 320M
        # 7 : external hit : 2 500 006 Hz
        # 8 : standalone TDC ck : 320M

        PLL_config_file = "Si5345_6_hit_8000256_Hz_CK_16000512_Hz_step_4ps.txt"
        # PLL outputs
        # 0 : FPGA clock : 8000256 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 320M
        # 7 : external hit : 16000512 Hz
        # 8 : standalone TDC ck : 320M
        tempo_dig_clock = 320e6

        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(200e3, 100e-12, tdc_clock_freq=tdc_ck, hit_given_by='PLL')
        # PLL_config_file = "Si5345_24_hit_and_CK_400008.00016_Hz_tdc_ck_320000000_Hz_step_100ps-Registers.txt"
        # external_hit_freq = float(re.findall("(?<=hit_and_CK_)[0-9]+[.]?[0-9]+", PLL_config_file)[0]) / 2

        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(50e3, 100e-12, tdc_clock_freq=tdc_ck, hit_given_by='FPGA')
        # PLL_config_file = "Si5345_25_hit_and_CK_80000000_Hz_tdc_ck_320001599.1_Hz_step_100ps-Registers.txt"
        # external_hit_freq = 50e3

        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(400e3, 100e-12, tdc_clock_freq=tdc_ck, hit_given_by='FPGA')
        # PLL_config_file = "Si5345_26_hit_and_CK_80000000_Hz_tdc_ck_320012799.488_Hz_step_100ps-Registers.txt"
        # external_hit_freq = 400e3

        expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(400e3, 5e-12,
                                                                                      tdc_clock_freq=tdc_ck,
                                                                                      hit_given_by='FPGA')
        PLL_config_file = "Si5345_27_hit_400000_Hz_tdc_ck_320000639.1_Hz_step_5ps-Registers.txt"

    elif tdc_ck == 40:
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(1.25e6, 40e-12, tdc_clock=40e6)
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(50e3, 1e-9, tdc_clock_freq=40e6, hit_given_by='PLL')
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(50e3, 500e-12, tdc_clock_freq=40e6, hit_given_by='FPGA')
        # expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(50e3, 10e-12, tdc_clock_freq=tdc_ck, hit_given_by='FPGA')

        PLL_config_file = "Si5345_15_hit_1250062_Hz_CK_2500125_Hz_step_39.99800ps-Registers.txt"
        # PLL outputs
        # 0 : FPGA clock : 1250062 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 40M
        # 7 : external hit : 2500125 Hz
        # 8 : standalone TDC ck : OFF
        tempo_dig_clock = 40
        external_hit_freq = 2500125

        PLL_config_file = "Si5345_16_hit_100000.4_Hz_CK_200000.8_Hz_step_40.00ps-Registers.txt"
        # PLL outputs
        # 0 : FPGA clock : 100000.4 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 40M
        # 7 : external hit : 200000.8 Hz
        # 8 : standalone TDC ck : OFF
        tempo_dig_clock = 40
        external_hit_freq = 100000.4

        PLL_config_file = "Si5345_17_hit_50000.1_Hz_CK_100000.2_Hz_step_40.00ps-Registers.txt"
        # PLL outputs
        # 0 : FPGA clock : 50000.1 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 40M
        # 7 : external hit : 100000.2 Hz
        # 8 : standalone TDC ck : OFF
        tempo_dig_clock = 40
        external_hit_freq = 50000.1

        PLL_config_file = "Si5345_18_hit_49999.75_Hz_CK_99999.50_Hz_step_100.00ps-Registers.txt"
        # PLL outputs
        # 0 : FPGA clock : 49999.75 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 40M
        # 7 : external hit : 99999.50 Hz
        # 8 : standalone TDC ck : OFF
        tempo_dig_clock = 40
        external_hit_freq = 49999.75

        PLL_config_file = "Si5345_19_hit_50000.6_Hz_CK_100001.2_Hz_step_240ps-Registers.txt"
        # PLL outputs
        # 0 : FPGA clock : 50000.6 Hz
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 40M
        # 7 : external hit : 100001.2 Hz
        # 8 : standalone TDC ck : OFF
        tempo_dig_clock = 40
        external_hit_freq = 50000.6

        PLL_config_file = "Si5345_20_hit_50002.00008_Hz_CK_100004.00016_Hz_step_800ps-Registers.txt"
        tempo_dig_clock = 40
        external_hit_freq = 50002.00008

        PLL_config_file = "Si5345_21_hit_and_CK_100005.00025_Hz_step_1000ps-Registers.txt"
        tempo_dig_clock = 40
        external_hit_freq = 100005.00025 / 2

        PLL_config_file = "Si5345_22_hit_80000000_Hz_tdc_ck_40000999.975_Hz_step_500ps-Registers.txt"
        external_hit_freq = 50e3

        PLL_config_file = "Si5345_23_hit_and_CK_80000000_Hz_tdc_ck_40000019.1_Hz_step_10ps-Registers.txt"
        external_hit_freq = 50e3

        PLL_config_file = "Si5345_28_hit_and_CK_80000000_Hz_tdc_ck_40000004_Hz_step_10ps-Registers.txt"
        expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider = frequency_planner(10e3, 10e-12,
                                                                                      tdc_clock_freq=tdc_ck * 1e6,
                                                                                      hit_given_by='FPGA')
        pass

    else:
        print("Code not implemented for tdc_ck %d !"%tdc_ck)


    if 'hit_and_CK_' in PLL_config_file:
        external_hit_freq = hit_frequency
    else:
        external_hit_freq = float(re.findall("(?<=hit_)[0-9]+[.]?[0-9]+", PLL_config_file)[0])
    if 'tdc_ck' in PLL_config_file:
        tempo_dig_clock = float(re.findall("(?<=tdc_ck_)[0-9]+[.]?[0-9]+", PLL_config_file)[0])
    else:
        tempo_dig_clock = config['tempo_dig_ck']*1e6
    config['hit_freq'].append(external_hit_freq)    # from PLL config
    config['expected_step'].append(expected_step)
    config['current_step'].append(find_step(external_hit_freq, tempo_dig_clock))
    config['ck_cycles_in_between_2_hits'].append(ck_cycles_in_between_2_hits)
    config['PLL_config_file'].append(PLL_config_file)

    return PLL_config_file, expected_step, ck_cycles_in_between_2_hits, hit_frequency, divider, tempo_dig_clock



if __name__ == '__main__':
    # test frame pattern 3-
    # for i in range(16):
    #     tempo.asic.common.probeDig.channel(0).TrigT_L_RS()
    #     print("Channels 0 to " + str(i) + " enabled.")
    #     tempo.asic.ch(i).select.trigTL.external()
    #     tempo.asic.ch(i).enable.TL()
    #     tempo.asic.interface.set.nb_trigger(2 * (i+1))
    #     tempo.FPGA.pulser.set_nb_impulsions(1)
    #     tempo.FPGA.pulser.launch()
    #     time.sleep(1)
    #     tempo.asic.interface.set.nb_trigger((2 * (i+1)) + 1)
    #     tempo.FPGA.pulser.launch()
    #     time.sleep(1)


    # tdc_scan_delaybox_step()
    # equivalent to :
    # tdc_scan_10ps_step(1, [0], None)                      # TDC low - channel 0 ext trigger ON - no analog at all
    # tdc_scan_10ps_step(1, [0], [0])                       # TDC low - channel 0 ext trigger ON - analog ch0
    # tdc_scan_10ps_step(12, [0], [0])                      # TDC low & high - channel 0 ext trigger ON - analog ch0
    # tdc_scan_10ps_step(12, [i for i in range(16)], None)    # TDC low & high - cluster 0 ext trigger ON - no analog at all
    # tdc_scan_10ps_step(12, [i for i in range(16)], [i for i in range(16)])    # TDC low & high - cluster 0 ext trigger ON - analog cluster 0 ON
    # tdc_scan_10ps_step(12, [i for i in range(64)], [])
    # tdc_scan_10ps_step(12, [i for i in range(64)], [i for i in range(64)])

    # measure_testbench_jitter_with_FPGA_pulser()
    # measure_testbench_jitter_with_external_pulser()
    # tdc_scan_delaybox_step(serial_startswith=b'TP2_01')
    # tdc_scan_code_density(6)
    tdc_scan_custom_step(4)
    # expected_step, ck_cycles_in_between_2_hits, hit_frequency = frequency_planner(200e3, 50e-12, tdc_clock_freq=80e6, hit_given_by='best')
    pass