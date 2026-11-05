import argparse
from alive_progress import alive_bar
import yaml

from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *


def acquire_hit_map(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    # config = {'tempo_dig_ck': [], 'enable_TL_ASIC_ch': [], 'tdc_injected': [], 'power_cluster': [],
    #           'VDDD': [], 'board': [], 'total_nb_events_expected': [], 'nb_trigger': [], 'readout_mode': [],
    #           'FPGA': [], 'fw_version_major': [], 'fw_version_minor': [], 'fw_hash': [], 'hv_eff_current': [],
    #           'hv_eff_voltage': [], 'probed_channel':[]}

    print("Setup CAEN HV")
    tempo = temporoc3(config)
    hv_voltage = 56
    tempo.hv.connect()
    tempo.hv.set_voltage(hv_voltage)
    # hv.set_enHV(1)
    # hv.set_enHV(1)
    time.sleep(1.5)
    hv_eff_current, hv_eff_voltage = tempo.hv.get_IV()
    print(hv_eff_current, hv_eff_voltage)

    config['hv_eff_current'].append(hv_eff_current)
    config['hv_eff_voltage'].append(hv_eff_voltage)

    print("Connecting Temporoc")
    tempo.fpga.set.power_on_ASIC(1)
    tempo.fpga.reset.all_temporoc()
    pass

    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_sync_ext_trigger()
    tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_40M_dig_ck()  # for internal ADC so no cross talk on MUX
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_80M_dig_ck()
    # tempo_dig_ck_freq, external_hit = tempo.pll.configure_PLL_160M_dig_ck()

    tempo_dig_ck.append(tempo_dig_ck_freq)

    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()

    tempo.reset_power_check_correct_clock_init()

    tempo.correct_default_HW_SC()

    if (tempo_dig_ck_freq == 40) | (tempo_dig_ck_freq == 80):
        print("Use dedicated fw : top_2024_07_03_18_01_40_MHz.bit")
    elif (tempo_dig_ck_freq == 160) | (tempo_dig_ck_freq == 320):
        print("fw at 320 MHz should work")

    local_output_dir = "../output/Na22_spectra/raw/"

    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    
    local_filepath = local_output_dir + "%d_B%d.csv" % (new_index, board)

    channels_list = list(range(64))
    clusters_list = np.unique(np.array(channels_list) // 16).tolist()
    probed_channel = 61
    config['probed_channel'].append(probed_channel)

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

        tempo.asic.ch(channel).set.tauHG(4)  # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.pahgGain(15)
        tempo.asic.ch(channel).set.tauLG(4)  # 4 x 20 ns = 80 ns
        tempo.asic.ch(channel).set.palgGain(1)

        # tempo.asic.ch(channel).disable.TL()
        tempo.asic.ch(channel).disable.TQ()

    config['enable_TL_ASIC_ch'].append(channels_list)
    config['tdc_injected'].append(['low', 'high'])
    config['power_cluster'].append(clusters_list)

    tempo.fpga.set.hit_register_channel(probed_channel)
    tempo.asic.ch(probed_channel).select.analogProbe.shL()
    tempo.asic.common.probeDig.channel(probed_channel).TrigT_H_RS()

    tempo.asic.common.set.delay_pdet(2 ** 8 - 1)
    # tempo.asic.common.select.trigger.local_time_low()
    # tempo.asic.common.select.trigger.local_time_high()

    tempo.asic.common.select.trigger.global_ASIC()  # to launch all peak detector with ch0 low trigger
    # tempo.asic.interface.select.global_trigger.ORTL()
    tempo.asic.interface.select.global_trigger.ORTH()

    # tempo.asic.bias.pdbuf.enable()
    # tempo.asic.bias.sh.HG.enable()
    # tempo.asic.bias.sh.LG.enable()

    nb_trigger = 31
    tempo.asic.interface.set.nb_trigger(nb_trigger)  # cluster valid
    config['nb_trigger'].append(nb_trigger)

    # tempo.asic.interface.en.sync_cluster()  # not required : only if Cluster specific data conversion
    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)

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
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacQ(1023)

    # Analog probe
    tempo.asic.interface.en.analog_probe()

    # Digital probe
    cluster = clusters_list[0]
    # tempo.IO.IO7_select.ser_data(cluster)
    tempo.fpga.OUT7_select.ser_clk(cluster)
    # tempo.IO.IO7_select.pulse_tdc()
    tempo.fpga.OUT8_select.digit_probe()
    # tempo.IO.IO8_select.ser_clk(cluster)
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

    events_received = 0
    config['total_nb_events_expected'] = 0
    tempo.deserializer.reset_fifo_for_all_cluster()

    tempo.save_ASIC_and_FPGA_config(config)



    while events_received < 1e6:
        time.sleep(0.5)
        bytes_count = tempo.deserializer.get_number_of_bytes_in_all_FIFO()
        expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count // 8
        events_extracted = bytes_count[cluster] // expected_bytes_per_event

        status = tempo.deserializer.extract_data(events_extracted, cluster, local_filepath, verbose=False)
        events_received += events_extracted
        config['total_nb_events_expected'] += events_extracted



    tempo.close()

    pass



if __name__ == '__main__':

    acquire_hit_map(1e6)