import argparse
from alive_progress import alive_bar
import yaml

from src.common_setup import *
from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *


def acquire_22Na_spectrum(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}


    # config = {'CAEN_serial_number': [], 'save_folder': [], 'tempo_dig_ck': [],
    #           'enable_TL_ASIC_ch': [], 'injected_channel_SiPM': [],
    #           'step': -1, 'restart_from_last_step': False,
    #           'tdc_injected': [], 'power_cluster': [],
    #           'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
    #           'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [],
    #           'probed_channel': [], 'current_time': [], 'log': [], 'start_time': 0,
    #           'patgain': [], 'dacTH': [], 'dacTL': [],
    #           'palgGain': [], 'tauLG': []}

    config.update({'SiPM_model': "Hamamatsu_S13361_6597",
                   'SiPM_breakdown': {'Hamamatsu_S13361_6597': 52.5, 'Broadcom_S4N44P164M': 33},
                   'target_hv_voltage': 56,
                   'CAEN_serial_number_to_board': {'AL04WEE3A': 1, 'AI05VLCGA': 2}})

    # config.update({'SiPM_model':"Broadcom_S4N44P164M",
    #                 'SiPM_breakdown':{'Hamamatsu_S13361_6597': 53, 'Broadcom_S4N44P164M': 33},
    #                 'target_hv_voltage': 45,
    #                 'CAEN_serial_number_to_board': {'AL04WEE3A': 1, 'AI05VLCGA': 2}})
    # SiPM_channels_list = [letter + str(number) for letter in ['A', 'B', 'C', 'D'] for number in range(1, 9)]
    # SiPM_channels_list += [letter + str(number) for letter in ['E', 'F', 'G', 'H'] for number in range(1, 9)]

    local_output_dir = "../output/Hamamatsu/22Na_spectra_TOT/"
    # local_output_dir = "../output/Broadcom/22Na_spectra/"

    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    # SiPM_channels_list = list(range(1, 62))
    # SiPM_channels_list = [24]
    # config['injected_channel_SiPM'].append(SiPM_channels_list)
    # injected_channels_ASIC = get_ASIC_ch(SiPM_channels_list, config['SiPM_model'])

    # injected_channels_ASIC.remove(16)
    # injected_channels_ASIC.remove(32)
    # injected_channels_ASIC.remove(48)
    # injected_channels_ASIC = list(range(64))
    # injected_channels_ASIC = list(range(32, 47))
    # injected_channels_ASIC = [32, 33, 34]
    injected_channels_ASIC = [43]
    tempo = temporoc3(config)
    setup_temporoc_special_TOT(tempo, config, injected_channels_ASIC, tempo_dig_ck_freq=320)

    calib_discri_file = '../config/TEMPOROC/B%d_calib_discri_staircase.csv' % (config['board'][0])
    if not os.path.exists(calib_discri_file):
        print("Aligning discri threshold : new measurement required")
        df_calib_discri = align_thresholds_with_staircase(tempo, config, injected_channels_ASIC)

    else:
        df_calib_discri = pd.read_csv(calib_discri_file)
        print("Aligning discri thresholds for %d channels : using channelwise correction %s" % (len(df_calib_discri), calib_discri_file))

        # apply correction
        for channel in df_calib_discri.channel:
            calib_DAC_local_TL = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'calib_DAC_local_TL'].iloc[0])
            calib_DAC_local_TH = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'calib_DAC_local_TH'].iloc[0])
            tempo.asic.ch(channel).set.calibDACT1(calib_DAC_local_TL)
            tempo.asic.ch(channel).set.calibDACT2(calib_DAC_local_TH)

    TL_pedestal = df_calib_discri.expected_aligned_pedestal_TL
    TH_pedestal = df_calib_discri.expected_aligned_pedestal_TH

    # TL_pedestal = round(np.mean(df_calib_discri.expected_aligned_pedestal_TL))
    # TH_pedestal = round(np.mean(df_calib_discri.expected_aligned_pedestal_TH))
    # tempo.asic.common.dis.latch()

    # for channel in injected_channels_ASIC:
    #     tempo.asic.ch(channel).disable.TL()
        # tempo.asic.ch(channel).disable.TH()

    # BIAS SIPM
    tempo.hv.connect()
    tempo.hv.set_voltage_modulating_ramp(config['target_hv_voltage'], config['SiPM_breakdown'][config['SiPM_model']])
    # hv = setup_hv(config, serial_number=list(config['CAEN_serial_number_to_board'].keys())[
    #     list(config['CAEN_serial_number_to_board'].values()).index(config['board'][0])])
    time.sleep(2)
    print(tempo.hv.measure_SiPM_HV())
    time.sleep(1)
    print(tempo.hv.measure_SiPM_HV())
    print(tempo.hv.save_periodically_SiPM_HV())

    ## SAVE SPECTRUM
    print("Acquiring data : radioactive source spectrum")
    print("Sweeping TH threshold on the overshoot")
    events_received = 0
    Nevents = 10000

    tempo.asic.interface.en.Nor_TrigT_H_RS()
    tempo.asic.common.set.dacTH(150)
    tempo.asic.common.set.dacTL(1023)
    # tempo.IO.OUT7_select.or_trig_h_rs() # C3
    tempo.fpga.OUT4_select.or_trig_l_rs() # C4
    tempo.asic.common.dis.tpr_latch()
    tempo.fpga.OUT7_select.digit_probe()
    tempo.asic.common.probeDig.channel(injected_channels_ASIC[0]).TrigT_H_RS()
    tempo.asic.ch(injected_channels_ASIC[0]).set.patComp(1)

    pass
    # dacTH_list = range(round(np.mean(TH_pedestal))-5, 0, -10)
    ch_TH_pedestal = int(df_calib_discri.loc[df_calib_discri.channel==injected_channels_ASIC[0], 'expected_aligned_pedestal_TH'].iloc[0])
    dacTH_list = range(ch_TH_pedestal-50, 0, -10)
    dacTH_list = [0]

    for dacTH in dacTH_list:
        print('dacTH = ', dacTH)
        tempo.asic.common.set.dacTH(dacTH)
        config['dacTH'].append(dacTH)
        tempo.fpga.reset.tpr_digital()
        tempo.deserializer.reset_fifo_for_all_cluster()
        time.sleep(0.1)

        csv_file_list = [local_output_dir + "B%d_cluster_%d_22Na_dacTH_%d.csv" % (tempo.board, cluster, dacTH) for cluster in range(4)]
        with alive_bar(Nevents, force_tty=True) as bar:  # your expected total
            while events_received < Nevents:
                time.sleep(0.5)
                events_extracted_list = tempo.deserializer.extract_all(csv_file_list, config)
                events_received_min = min(events_extracted_list)
                events_received += events_received_min
                if events_received_min > 0:
                    bar(events_received_min)

    tempo.save_ASIC_and_FPGA_config(config)

    tempo.close()
    print("Done")

    pass


def setup_temporoc_special_TOT(tempo, config, injected_channels_ASIC, tempo_dig_ck_freq=40, test=False, debug=False):

    print("Connecting board %d"%tempo.board)

    tempo.deserializer.filter.disable.coincidence_inter_asic()
    tempo.fpga.select.foreign_eof.off()


    if test:
        # TEST SIGNAL : Setup FPGA pulser
        tempo.fpga.pulser.unmask_on_IO0()
        tempo.fpga.pulser.mask_on_ext_trigger()
        tempo.fpga.pulser.set_sync_mode()

        tempo.fpga.pulser.sync_disable_forever()
        # tempo.FPGA.pulser.sync_enable_forever()
    else:
        tempo.fpga.pulser.mask_on_ext_trigger()
        tempo.fpga.pulser.mask_on_IO0()
        tempo.fpga.pulser.disable()
        tempo.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset


    # Select temporoc digital clock
    tempo.fpga.set.PLL_as_clock_source()

    # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

    # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()


    tempo.pll.flash("../config/PLL/Si5345_11%s_ck_%dMHz-Registers.txt" % (tempo.mode, tempo_dig_ck_freq),
                    tempo_dig_clock=tempo_dig_ck_freq)
    # PLL outputs
    # 0 : FPGA clock : 80M
    # 3 : FPGA clock : 80M # What is the impact of the clock duty cycle deformation passing through the FPGA ?)
    # 6 : TEMPOROC digital : 80M
    # 7 : external hit resync CK : 320M
    # 8 : standalone TDC ck : OFF

    # Expected PLL inputs
    # IN0 : 100M from cristal if MASTER


    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_sync_ext_trigger()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_40M_dig_ck()  # for internal ADC so no cross talk on MUX
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_80M_dig_ck()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_160M_dig_ck()

    # tempo_dig_ck.append(tempo_dig_ck_freq)

    tempo.reset_power_check_correct_clock_init()

    # save_temperature(tempo, config)

    readout_mode = 'full_adc_tdc'  # ,'lg_adc_low_tdc', 'hg_adc_low_tdc']   #, 'low_high_tdc', 'low_tdc', ]:
    config['readout_mode'].append(readout_mode)
    tempo.asic.interface.select.dig_modeRO(readout_mode)

    deserialiser_time = tempo.asic.interface.select.dig_modeRO.RObit_count+50
    deserialiser_time = 2100
    tempo.deserializer.set_time(deserialiser_time)
    config['deserialiser_time'] = deserialiser_time

    if test:
        hit_freq_Hz = 25000
        tempo.fpga.pulser.set_frequency_in_Hz(hit_freq_Hz)  # not higher otherwise temporoc has not enough time to TX data
        tempo.fpga.pulser.release_resetn_latch()
        expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count / 8 + 7
        N_per_iter = round(16230 * 2 / expected_bytes_per_event)  # todo FIFO size check
        # N_per_iter = 1
        tempo.fpga.pulser.set_nb_impulsions(N_per_iter)

    tempo.correct_default_HW_SC()
    

    clusters_list = np.unique(np.array(injected_channels_ASIC) // 16).tolist()
    src.utils.update_config_dict(config, clusters_list)
    tempo.asic.ch.all_except(injected_channels_ASIC).disable.front_end_except_pdet()
    # tempo.asic.ch.all_except(channels_list).disable.front_end()
    tempo.asic.ch.all().select.Zin.high()

    patgain = 4
    tauLG = 4
    palgGain = 8

    tempo.asic.ch.all().set.inDac(128)

    for channel in injected_channels_ASIC:
        # Time PA gain
        tempo.asic.ch(channel).set.patGain(patgain)
        config['patgain'].append(patgain)

        tempo.asic.ch(channel).set.patComp(0)
        tempo.asic.ch(channel).set.inDac(0)

        # Shaper and Peak Detector setting
        # tempo.asic.ch(channel).enable.pdetHG()
        # tempo.asic.ch(channel).enable.pdetLG()

        tempo.asic.ch(channel).set.tauHG(4)   # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.pahgGain(0)
        tempo.asic.ch(channel).set.tauLG(tauLG)
        tempo.asic.ch(channel).set.palgGain(palgGain)

        config['tauLG'].append(tauLG)
        config['palgGain'].append(palgGain)

        if test:
            tempo.asic.ch(channel).select.trigTL.external()
            # tempo.asic.ch(channel).select.trigTH.external()

        # tempo.asic.ch(channel).disable.TH()
        tempo.asic.ch(channel).disable.TQ()

    print("injected channels: ",np.sort(injected_channels_ASIC))
    config['enable_TL_ASIC_ch'].append(injected_channels_ASIC)
    # config['tdc_injected'].append(['low'])
    config['tdc_injected'].append(['low', 'high'])
    config['power_cluster'].append(clusters_list)
    print("injected clusters ", clusters_list)
    probed_channel = config['enable_TL_ASIC_ch'][-1][-1]
    config['probed_channel'].append(probed_channel)

    if debug: #probed_channel is not None:
        print("probed_channel : ", probed_channel)
        # tempo.fpga.set.hit_register_channel(probed_channel)
        tempo.asic.ch(probed_channel).select.analogProbe.shH()
        print("SH HG probe enabled")
        tempo.asic.common.probeDig.channel(probed_channel).TrigT_L()

    tempo.asic.common.set.delay_pdet(2 ** 8 - 1)
    # tempo.asic.common.select.trigger.local_time_low()
    # tempo.asic.common.select.trigger.local_time_high()

    tempo.asic.common.select.trigger.global_ASIC()  # to launch all peak detector with ch0 low trigger
    tempo.asic.interface.select.global_trigger.ORTL()
    # tempo.asic.interface.select.global_trigger.ORTH()
    # tempo.asic.interface.select.global_trigger.ORTQ()
    # tempo.asic.interface.en.sync_cluster() # cluster specific = 1
    # tempo.asic.interface.dis.sync_cluster() # alls clusters = default = 0
    config['sync_cluster'] = 0
    print("sync_cluster ",(tempo.dev.i2c.read_register(66, 5)&(1<<5))>>5)

    nb_trigger = 16 # at least 1 frame for multichannel injections
    # nb_trigger = 24
    # nb_trigger = 31
    tempo.asic.interface.set.nb_trigger(nb_trigger)  # cluster valid
    config['nb_trigger'].append(nb_trigger)

    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)
    # tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

    # Digital readout enable and Force conversion settings
    tempo.fpga.set.ro_enable_ASIC(1)

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

    # tempo.IO.OUT4_select.coincidence()


    # tempo.IO.IO8_select.ser_clk(probed_cluster)
    # tempo.IO.IO8_select.ser_data(probed_cluster)
    tempo.asic.interface.en.digital_probe()

    # useless : used only to probe pdet outside the ASIC through OTA
    # if debug:
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



if __name__ == '__main__':
    acquire_22Na_spectrum()