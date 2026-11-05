import time

from analyse.common_data_decoding import build_dataframe_from_file
from src.common_setup import setup_temporoc, load_config, reset_FPGA_FIFO_and_tempo_digital, acquire_data_multi_boards
from src.temporoc3 import temporoc3
from src.tools import tektronix_AFG
from src.utils import find_new_folder_index, update_config_dict, save_config_file


def common_setup_for_external_pulser_tests(board, asic_id, injected_channel, Cinj_F):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/B%d_TPR%d/ext_pulser/" % (board, asic_id)
    find_new_folder_index(local_output_dir, config)

    tempo = temporoc3(config)

    print(
        "Make sure an external pulser is connected to injected input : either IN_CTEST or directly a given channel (one channel at a time !)")

    setup_temporoc([tempo], config)
    config['test'] = ["charge scan with external pulser"]

    # Optional config for this test
    tempo.asic.ch.all().disable.all_discri()
    # tempo.asic.ch.all().disable.front_end()
    # tempo.asic.ch(injected_channel).enable.charge()
    tempo.asic.ch(injected_channel).enable.front_end()
    tempo.asic.ch(injected_channel).enable.TH()
    tempo.asic.ch(injected_channel).enable.TL()
    tempo.asic.ch(injected_channel).select.trigTH.internal()
    tempo.asic.ch(injected_channel).select.trigTL.internal()

    # Time PA gain
    tempo.asic.ch(injected_channel).set.patGain(8)
    tempo.asic.ch(injected_channel).set.patComp(3)

    # Time Trigger and Threshold settings
    tempo.asic.common.set.dacTH(350)
    tempo.asic.common.set.dacTL(300)
    tempo.asic.common.set.dacQ(1023)

    # Shaper and Peak Detector setting
    tempo.asic.ch(injected_channel).enable.pdetHG()
    tempo.asic.ch(injected_channel).enable.pdetLG()
    tempo.asic.common.select.trigger.local_time_high()
    tempo.asic.ch(injected_channel).set.tauHG(1)
    tempo.asic.ch(injected_channel).set.pahgGain(1)
    tempo.asic.ch(injected_channel).set.tauLG(1)
    tempo.asic.ch(injected_channel).set.palgGain(15)
    tempo.asic.interface.dis.slow_adc_mux()
    tempo.asic.common.set.event_window_length(0)
    tempo.asic.common.set.shaper_delay_length(0)

    # Analog probe
    # tempo.asic.interface.en.analog_probe()
    # tempo.asic.ch(injected_channel).select.analogProbe.paHG()
    # tempo.asic.ch(injected_channel).select.analogProbe.shH()
    tempo.asic.ch.all().select.analogProbe.off()

    # useless : used only to probe pdet outside the ASIC through OTA
    # tempo.asic.interface.en.LG_pdet_MUX_output()
    # tempo.asic.interface.en.HG_pdet_MUX_output()

    # tempo.asic.common.probeDig.channel(channel).TrigT_H()
    # tempo.asic.common.probeDig.channel(channel).TH()
    # tempo.asic.common.probeDig.channel(channel).TrigT_H_RS()
    # tempo.asic.common.probeDig.channel(injected_channel).TrigT_L_RS()
    # tempo.asic.common.probeDig.channel(channel).HOLD_delayed()
    # tempo.asic.common.probeDig.cluster(cluster).rstnADC()
    # tempo.asic.common.probeDig.cluster(cluster).rstnLatchInt()
    # tempo.asic.common.probeDig.cluster(cluster).end_delayH()
    # tempo.asic.common.probeDig.cluster(cluster).convDoneADCLG()

    # tempo.fpga.set.conv_syst_ASIC(1)
    tempo.asic.interface.en.Nor_TrigT_H_RS()
    tempo.asic.interface.en.Nor_TrigT_L_RS()
    # tempo.fpga.OUT2_select.ser_clk(0)

    # tempo.asic.interface.en.digital_probe()
    # tempo.asic.common.probeDig.channel(injected_channel).TrigT_H_RS()
    # tempo.fpga.OUT2_select.digit_probe()

    tempo.board_config['tdc_injected'] = [['low', 'high']]
    tempo.board_config['injected_channel'] = [[injected_channel]]
    tempo.board_config['enable_TL_ASIC_ch'] = [[injected_channel]]

    tempo.board_config['cinj_pF'] = int(Cinj_F * 1e12)

    clusters_list = [0, 1, 2, 3]
    tempo.board_config['power_cluster'] = [clusters_list]
    update_config_dict(tempo.board_config, clusters_list)
    save_config_file(config)

    reset_FPGA_FIFO_and_tempo_digital([tempo])  # Only ONCE at startup

    return tempo, config

def acquire_with_external_pulser(board, asic_id, injected_channel, Cinj_F):

    use_external_pulser=True
    # use_external_pulser=False
    if use_external_pulser:
        ext_pulser = tektronix_AFG()
        ext_pulser.analog_injection()
        ext_pulser.burst_mode()
        ext_pulser.enable_output()
    else:
        ext_pulser = None

    tempo, config = common_setup_for_external_pulser_tests(board, asic_id, injected_channel, Cinj_F)

    # for Vinj in range(50, 5000, 50):
    #     Qinj_pC = Vinj / 10 * Cinj_F * 1e9
    #     suffix = '_Qinj_%.2fpC' % Qinj_pC
    #     pulse_and_acquire(tempo, config, use_external_pulser, ext_pulser, suffix, Vinj)


    # Vinj = 1000 # 10 pC with 100 pF injection capacitor
    # for shaper_preamplifier in range(1, 16):
    #     suffix = '_PAsh_%d' % shaper_preamplifier
    #     tempo.asic.ch.all().set.pahgGain(shaper_preamplifier)
    #     tempo.asic.ch.all().set.palgGain(shaper_preamplifier)
    #     pulse_and_acquire(tempo, config, use_external_pulser, ext_pulser, suffix, Vinj)


    Vinj = 50 # 0.5 pC with 100 pF injection capacitor
    for shaper_delay in [0, 8, 16, 24, 31]:
        suffix = '_shaper_delay_%d' % shaper_delay
        tempo.asic.common.set.shaper_delay_length(shaper_delay)
        pulse_and_acquire(tempo, config, use_external_pulser, ext_pulser, suffix, Vinj)

    if use_external_pulser:
        ext_pulser.close()

    tempo.close()


def pulse_and_acquire(tempo, config, use_external_pulser, ext_pulser, suffix, Vinj):

    # charge injection with async external pulser through a cap of 100 pF with 20 dB attenuator (/10)
    # Qinj = 10 pC = 100 mV * 100 pF
    if use_external_pulser:
        ext_pulser.set_voltage_amplitude(Vinj)

    else:
        print("change the injected voltage to %d mV." % Vinj)
        pass

    reset_FPGA_FIFO_and_tempo_digital([tempo])
    bytes_in_fifo = tempo.deserializer.get_number_of_bytes_in_all_FIFO()
    if bytes_in_fifo != (0,0,0,0):
        print(bytes_in_fifo)

    if use_external_pulser:
        ext_pulser.trigger()
    else:
        print("Inject !")


    csv_file_list = [config['save_folder'] + "B%d_cluster_%d%s.csv" % (tempo.board, cluster, suffix) for cluster in
                     tempo.board_config['power_cluster'][0]]
    # while 1:
    time.sleep(0.6)
    events_extracted_list = tempo.deserializer.extract_all(csv_file_list, tempo.board_config)
    print(events_extracted_list)


def acquire_pdet_with_int_ADC_inCtest(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)
    tempo.init_board()
    tempo.correct_default_HW_SC()

    local_output_dir = "../output/charge_scan/in_ctest/raw/"

    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

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

    
    Cinj = 1.5e-12
    local_filepath = local_output_dir + "%d_B%d_Cinj_%dpF.csv" % (new_file_index, board, Cinj*1e12)
    df_filepath = local_output_dir + "%d_B%d_Cinj_%dpF_all.csv" % (new_file_index, board, Cinj*1e12)

    # tempo.asic.ch.all().disable.all_discri()
    # tempo.asic.ch.all().disable.front_end()
    # tempo.asic.ch.all_except(63).disable.use_ctest()
    tempo.asic.ch.all().disable.TH()

    # tempo.asic.ch(channel).enable.charge()
    # tempo.asic.ch(channel).enable.TH()
    # tempo.asic.ch(channel).enable.TL()
    tempo.asic.ch.all().select.trigTH.internal()
    tempo.asic.ch.all().select.trigTL.internal()
    channels_list = [47, 46]
    tempo.asic.ch.group(channels_list).enable.cmd_test()
    tempo.asic.ch.all_except(channels_list).disable.front_end()
    # tempo.asic.ch.group(channels_list).enable.use_ctest()

    for channel in channels_list:
        # Time PA gain
        tempo.asic.ch(channel).set.patGain(1)
        tempo.asic.ch(channel).set.patComp(3)

        tempo.asic.ch(channel).set.tauHG(1)
        tempo.asic.ch(channel).set.pahgGain(15)
        tempo.asic.ch(channel).set.tauLG(1)
        tempo.asic.ch(channel).set.palgGain(15)

    #Time Trigger and Threshold settings
    tempo.asic.bias.discri.TL.enable()
    tempo.asic.bias.discri.TH.enable()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.set.dacTH(1023) #199)
    tempo.asic.common.set.dacTL(220)
    tempo.asic.common.set.dacQ(1023)

    tempo.asic.interface.set.nb_trigger(31) # cluster valid

    tempo.asic.interface.dis.sync_cluster()  # not required : only if Cluster specific data conversion

    #Digital readout enable and Force conversion settings
    tempo.fpga.set.ro_enable_ASIC(1)


    tempo.asic.interface.en.Inh_rstOnDlyH()  # mask end delay H for digital
    tempo.asic.interface.en.Inh_rstOnDlyL()

    # Val event and Trigger latch enabled
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()

    # Shaper and Peak Detector setting
    tempo.asic.common.set.delay_pdet(2**8-1)
    tempo.asic.common.select.trigger.local_time_low()
    tempo.asic.bias.pdbuf.enable()
    tempo.asic.bias.sh.HG.enable()
    tempo.asic.bias.sh.LG.enable()


    # Analog probe
    tempo.asic.interface.en.analog_probe()
    #tempo.asic.ch(channel).select.analogProbe.paHG()
    tempo.asic.ch(channel).select.analogProbe.shH()
    #tempo.asic.ch.all().select.analogProbe.off()

    # Digital probe
    # tempo.IO.IO7_select.ser0_data()
    tempo.fpga.OUT7_select.ser_clk(0)
    tempo.fpga.OUT8_select.digit_probe()
    tempo.asic.interface.en.digital_probe()

    # useless : used only to probe pdet outside the ASIC through OTA
    # tempo.asic.interface.en.LG_pdet_MUX_output()
    # tempo.asic.interface.en.HG_pdet_MUX_output()


    #tempo.asic.common.probeDig.channel(channel).TrigT_H()
    #tempo.asic.common.probeDig.channel(channel).TH()
    #tempo.asic.common.probeDig.channel(channel).TrigT_H_RS()
    # tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
    tempo.asic.common.probeDig.channel(channel).TrigT_L()
    #tempo.asic.common.probeDig.channel(channel).HOLD_delayed()
    #tempo.asic.common.probeDig.cluster(cluster).rstnADC()
    # tempo.asic.common.probeDig.cluster(cluster).rstnLatchInt()
    # tempo.asic.common.probeDig.cluster(cluster).end_delayH()
    # tempo.asic.common.probeDig.cluster(cluster).convDoneADCLG()


    # readout mode
    #tempo.asic.interface.select.dig_modeRO.hg_adc()
    #tempo.asic.interface.select.dig_modeRO.lg_adc()
    # tempo.asic.interface.select.dig_modeRO.hg_lg_adc()
    #tempo.asic.interface.select.dig_modeRO.hg_adc_high_tdc()
    #tempo.asic.interface.select.dig_modeRO.lg_adc_high_tdc()
    # tempo.asic.interface.select.dig_modeRO.lg_adc_low_tdc()
    # tempo.asic.interface.select.dig_modeRO.hit() # when in mode hit, digital does not wait for any event to stream data out of cluster = continuous mode
    tempo.asic.interface.select.dig_modeRO.full_adc_tdc()

    automatic_external_pulser= False
    if automatic_external_pulser:
        ext_pulser = tektronix_AFG()
        ext_pulser.analog_injection()
        ext_pulser.burst_mode()
    df = pd.DataFrame()

    cluster = 0
    for Vinj in [800, 1000, 1200]:# range(100, 1000, 100):
        if automatic_external_pulser:
            ext_pulser.set_voltage_amplitude(Vinj)
        else:
            print("Change external pulser output voltage to %d mV"%Vinj)
            pass
        tempo.deserializer.reset_fifo_for_all_cluster()

        # charge injection with async external pulser through a cap of 100 pF
        # Qinj = 10 pC = 100 mV * 100 pF

        if automatic_external_pulser:
            ext_pulser.trigger()
        else:
            print("Trigger external pulser %d mV"%Vinj)
            pass

        time.sleep(0.05)
        bytes_count = tempo.deserializer.get_number_of_bytes_in_fifo(cluster)
        expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count//8
        events_asked = bytes_count // expected_bytes_per_event

        status = tempo.deserializer.extract_data(events_asked, cluster, local_filepath) #, verbose=True)

        df_tmp = build_dataframe_from_file(local_filepath)
        df_tmp['Vinj_mV'] = Vinj  # -20dB attenuator
        df_tmp['Qinj_pC'] = Vinj*Cinj*1e9
        df_tmp['iter'] = df_tmp.index
        df = pd.concat([df, df_tmp])

        os.remove(local_filepath)

        bytes_count = tempo.deserializer.get_number_of_bytes_in_fifo(cluster)
        if bytes_count>0:
            print("Not expected bytes left in FIFO: %d" % bytes_count)

    df.to_csv(df_filepath, index=False)
    tempo.close()

    pass


def acquire_pdet_with_int_ADC_2channels_with_external_ADC(board, automatic_external_pulser=True):

    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    lin_attenuation = 10     # -20dB attenuator
    # lin_attenuation = 1     # NO attenuator

    # 1 cycle per injection on external pulser
    # enable 2 channels on the pulser with simultaneous injection

    tempo = temporoc3(config)
    tempo.fpga.set.power_on_ASIC(1)
    tempo.fpga.reset.all_temporoc()
    pass

    tempo_dig_ck_freq = tempo.pll.configure_PLL_40M_dig_ck()
    # tempo_dig_ck_freq = tempo.pll.configure_PLL_160M_dig_ck()
    # tempo_dig_ck_freq = tempo.pll.configure_PLL_80M_dig_ck()

    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()

    tempo.reset_power_check_correct_clock_init()

    tempo.correct_default_HW_SC()

    if automatic_external_pulser:
        print("Connect TEKTRO AFG pulser :"
              "\tOUT CH 0/1 to a channel input 0/1"
              "\tOUT TRIG to scope"
              "\tIN TRIG from IO0 FPGA = FPGA pulser")
        ext_pulser = tektronix_AFG()
        ext_pulser.analog_injection()
        ext_pulser.burst_mode(cycles=1)
        ext_pulser.enable_output()


    if (tempo_dig_ck_freq == 40) | (tempo_dig_ck_freq == 80):
        print("Use dedicated fw : top_2024_07_03_18_01_40_MHz.bit")
    elif (tempo_dig_ck_freq == 160) | (tempo_dig_ck_freq == 320):
        print("fw at 320 MHz should work")

    local_output_dir = "../output/charge_scan/dual_ch/raw/"
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    
    Cinj = 100e-12
    local_filepath = local_output_dir + "%d_B%d_Cinj_%dpF.csv" % (new_index, board, Cinj*1e12)
    df_filepath = local_output_dir + "%d_B%d_Cinj_%dpF_all.csv" % (new_index, board, Cinj*1e12)
    df_filepath2 = local_output_dir + "%d_B%d_Cinj_%dpF_all.feather" % (new_index, board, Cinj*1e12)

    channels_list = [62] # [62, 63] # [31, 1] #      [0, 1] #     [31,32] #
    clusters_list = np.unique(np.array(channels_list)//16).tolist()
    probed_channel = 62

    tempo.asic.ch.all_except(channels_list).disable.front_end_except_pdet()
    # tempo.asic.ch.all_except(channels_list).disable.front_end()

    # need to have an odd number of channels triggering otherwise the digital does not reset the trigger latch

    if len(channels_list) > 1:
        tempo.asic.ch(channels_list[0]).disable.all_discri()

    # tempo.asic.ch.all_except(probed_channel).disable.all_discri()

    for channel in channels_list:
        # Time PA gain
        tempo.asic.ch(channel).set.patGain(8)
        tempo.asic.ch(channel).set.patComp(0)

        # Shaper and Peak Detector setting
        # tempo.asic.ch(channel).enable.pdetHG()
        # tempo.asic.ch(channel).enable.pdetLG()

        # tempo.asic.ch(channel).set.tauHG(1)
        # tempo.asic.ch(channel).set.pahgGain(10)
        # tempo.asic.ch(channel).set.tauLG(1)
        # tempo.asic.ch(channel).set.palgGain(10)
        tempo.asic.ch(channel).set.tauHG(4) # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.pahgGain(4)
        tempo.asic.ch(channel).set.tauLG(4) # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.palgGain(4)

        # tempo.asic.ch(channel).disable.TL()
        tempo.asic.ch(channel).disable.TQ()

    tempo.fpga.set.hit_register_channel(probed_channel)
    tempo.asic.ch(probed_channel).select.analogProbe.shH()
    tempo.asic.common.probeDig.channel(probed_channel).TrigT_H_RS()


    tempo.asic.common.set.delay_pdet(2 ** 8 - 1)
    # tempo.asic.common.select.trigger.local_time_low()
    # tempo.asic.common.select.trigger.local_time_high()

    tempo.asic.common.select.trigger.global_ASIC() # to launch all peak detector with ch0 low trigger
    tempo.asic.interface.select.global_trigger.ORTH()

    # tempo.asic.bias.pdbuf.enable()
    # tempo.asic.bias.sh.HG.enable()
    # tempo.asic.bias.sh.LG.enable()

    tempo.asic.interface.set.nb_trigger(31) # cluster valid

    # tempo.asic.interface.en.sync_cluster()  # not required : only if Cluster specific data conversion
    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)

    #Digital readout enable and Force conversion settings
    tempo.fpga.set.ro_enable_ASIC(1)

    tempo.asic.interface.en.Inh_rstOnDlyH()  # mask end delay H for digital
    tempo.asic.interface.en.Inh_rstOnDlyL()

    # Val event and Trigger latch enabled
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()

    #Time Trigger and Threshold settings
    tempo.asic.bias.discri.TL.enable()
    tempo.asic.bias.discri.TH.enable()
    tempo.asic.common.dis.hyst_TH()
    tempo.asic.common.dis.hyst_TL()
    tempo.asic.common.set.dacTH(350)
    tempo.asic.common.set.dacTL(500)
    tempo.asic.common.set.dacQ(1023)

    # Analog probe
    tempo.asic.interface.en.analog_probe()

    # Digital probe
    cluster = clusters_list[0]
    # tempo.IO.IO7_select.ser_data(cluster)
    tempo.fpga.OUT7_select.ser_clk(cluster)
    # tempo.IO.IO7_select.pulse_tdc()
    tempo.fpga.OUT8_select.digit_probe()
    # tempo.IO.IO8_select.ser_data(cluster)
    # tempo.IO.IO8_select.ser_clk(cluster)
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

    #tempo.asic.common.probeDig.channel(channel).TrigT_H()
    #tempo.asic.common.probeDig.channel(channel).TH()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L()
    #tempo.asic.common.probeDig.channel(channel).HOLD_delayed()
    #tempo.asic.common.probeDig.cluster(cluster).rstnADC()
    # tempo.asic.common.probeDig.cluster(cluster).rstnLatchInt()
    # tempo.asic.common.probeDig.cluster(cluster).end_delayH()
    # tempo.asic.common.probeDig.cluster(cluster).convDoneADCLG()

    config = {'enable_TL_ASIC_ch': [], 'tdc_injected': [],
              'VDDD': [], 'board': [], 'hit_freq': [], 'nb_trigger': [], 'readout_mode': [],
              'iter': [], 'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': []}

    readout_mode = 'full_adc_tdc' #,'lg_adc_low_tdc', 'hg_adc_low_tdc']   #, 'low_high_tdc', 'low_tdc', ]:
    config['readout_mode'].append(readout_mode)
    tempo.asic.interface.select.dig_modeRO(readout_mode)

    df = pd.DataFrame()

    tempo.external_ADC.set_delay_before_trigger(50)
    tempo.external_ADC.select_trigger.pulse_tdc()

    # Setup FPGA pulser that triggers the external pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.mask_on_ext_trigger()
    tempo.fpga.pulser.set_sync_mode()
    # tempo.FPGA.pulser.set_async_feedthrough_mode()
    tempo.fpga.pulser.set_nb_impulsions(1)
    tempo.fpga.pulser.set_frequency_in_Hz(100e3)

    tempo.save_ASIC_and_FPGA_config(config)

    # config_file = local_output_dir+ '%d_config.yaml'%(new_file_index)
    # with open(config_file, 'w') as outfile:
    #     yaml.dump(config, outfile, default_flow_style=False, Dumper=VerboseSafeDumper)
    # outfile.close()

    for Vinj in range(100, 1001, 100): #[100, 500, 1000]:#
        if automatic_external_pulser:
            ext_pulser.set_voltage_amplitude(Vinj)
        else:
            print("Change external pulser output voltage to %d mV"%Vinj)
            pass

        # charge injection with async external pulser through a cap of 100 pF
        # Qinj = 10 pC = 100 mV / 10 * 100 pF

        for iter in range(20):
            tempo.deserializer.reset_fifo_for_all_cluster()
            tempo.fpga.pulser.launch() # one shot for nothing because FIFO in FPGA never sees first one

            if automatic_external_pulser:
                # ext_pulser.trigger()
                tempo.fpga.pulser.launch()
            else:
                print("Trigger external pulser %d mV"%Vinj)
                pass

            external_adc_lg = tempo.external_ADC.read_LG()
            external_adc_hg = tempo.external_ADC.read_HG()
            time.sleep(0.05)

            bytes_count = tempo.deserializer.get_number_of_bytes_in_all_FIFO()
            expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count//8
            events_asked = bytes_count[cluster] // expected_bytes_per_event

            status = tempo.deserializer.extract_data(events_asked, cluster, local_filepath)

            df_tmp = build_dataframe_from_file(local_filepath)

            df_tmp['Vinj_mV'] = Vinj/lin_attenuation
            df_tmp['Qinj_pC'] = Vinj/lin_attenuation*Cinj*1e9

            df_tmp['iter'] = iter + df_tmp.index


            df_tmp['pdet_LG_ch%d'%probed_channel] = external_adc_lg
            df_tmp['pdet_HG_ch%d'%probed_channel] = external_adc_hg

            df = pd.concat([df, df_tmp])
            df.to_feather(df_filepath2)
            os.remove(local_filepath)

            bytes_count = tempo.deserializer.get_number_of_bytes_in_fifo(cluster)
            if bytes_count>0:
                print("Not expected bytes left in FIFO: %d" % bytes_count)

    df.to_csv(df_filepath, index=False)


    ext_pulser.close()
    tempo.close()

    pass



#NB:
# On analog power supply : adc, TDC, PA, pdetector, shaper, bg, SC, inDAC, discri_a
# On digital power supply : d_discri, digital pur, d_pad

### Identification ASIC
# mesure de la résistance de 10 kOhm entre reserved et GND


# Let the digital handle the resets (ok for low frequency / high voltage only)
# tempo.get_conv_syst()
# tempo.dev.i2c.read_register(channel, 0)
# print(bin(tempo.dev.i2c.read_register(channel, 0)))


# tempo.asic.ch(channel).enable.inDac()
# tempo.asic.ch(channel).get.inDac()
# print(bin(tempo.dev.i2c.read_register(channel, 65)))
# print("probe ",(tempo.dev.i2c.read_register(67, 3)))

# # check if other channels are triggering
# for i in range(64):
#     print(i)
#     tempo.asic.common.probeDig.channel(i).TrigT_L_RS()
#     time.sleep(1)

# # check if several probe at the same time : all good
# for i in range(12,20):
#     print(tempo.dev.i2c.read_register(65,i))
# print(tempo.dev.i2c.read_register(1,66))

# tempo.asic.interface.en.HG_pdet_MUX_output()
# tempo.asic.interface.en.trigT_H_mux()
#tempo.asic.interface.en.Nor_TrigT_Q()
#tempo.asic.interface.en.Nor_TrigQ_RS()




if __name__ == '__main__':
    # acquire_pdet_with_int_ADC()
    # acquire_pdet_with_int_ADC_inCtest()
    # acquire_pdet_with_int_ADC_2channels()

    # acquire_pdet_with_int_ADC_2channels_with_external_ADC()
    # board_asic = (4, 104)
    board_asic = (6, 108)
    acquire_with_external_pulser(*board_asic, 1, 100e-12)