import inspect
import sys
from datetime import datetime
from typing import List

from alive_progress import alive_bar
from scipy.signal import argrelextrema, argrelmin
import matplotlib.pyplot as plt
import pandas as pd
from win32comext.taskscheduler.taskscheduler import TASK_LAST_WEEK

import src.CONSTANTS
from src.temporoc3 import *
from analyse.common_analysis import *
from src.tools import *
from src.utils import *
import uiroc.device as device
import ftd2xx

# former setup_temporoc_coincidence

def setup_temporoc(tempo_list:List[temporoc3],
                   config,
                   ext_trigger=False,
                   ext_trigger_init_side='master',
                   forever_pulser=True,
                   tempo_dig_ck_freq=320,
                   laser=False,
                   probed_channel=None,
                   force_flash_PLL=False):

    # tempo_list should always be master then slave (to allow PLL master clock to lock prior slave PLL)
    # If list contains >2 temporoc instances, then it assumes you want
    # to synchronize boards together sharing clocks for coincidence event detection (through SMA coaxial)

    # external trigger can be provided to the ASIC(s) by one FPGA
    # pulse sequence is either synchronous or asynchronous to the ASIC clock
    # pulse sequence is either finite or forever
    # to operate an external laser, the PLL + FPGA can output a trigger

    for tempo in tempo_list:
        tempo.connect_ASIC()
        print("Connecting "+tempo.mode+" as board %d"%tempo.board)

        # tempo.fpga.test_read_write_FPGA_reg()
        tempo.fpga.reset.all_temporoc()

        # get fw version identifier & check
        tempo.get_firmware_name(config)

        tempo.board_config['tempo_dig_ck'] = tempo_dig_ck_freq
        tempo.deserializer.dig_clock_freq = tempo_dig_ck_freq

        FPGA_PLL = tempo.board_config['FPGA_PLL']

        ####  Setup for coincidence (at least 2 ASICs)
        if len(tempo_list)>=2:

            # Mutual to every board:
            tempo.deserializer.filter.enable.coincidence_inter_asic()
            # tempo.deserializer.filter.disable.coincidence_inter_asic()

            # Receive distant trigger (= End Of Frame)
            tempo.fpga.select.foreign_eof.input_clk1()
            # tempo.fpga.select.foreign_eof.input_clk2()

            # Share local trigger (= End Of Frame) to distant
            tempo.fpga.OUT3_select.eof_local()

            # Output coincidence flag to IO for scope debug
            tempo.fpga.OUT4_select.coincidence()

        else:
            # Setup for single ASIC
            tempo.deserializer.filter.disable.coincidence_inter_asic()
            tempo.fpga.select.foreign_eof.off()


        if ext_trigger & (tempo.mode == ext_trigger_init_side):

            # TEST SIGNAL : Setup FPGA pulser
            tempo.fpga.pulser.mask_on_IO0()
            print("Don't forget to connect SMA on IO0 to ext trigger on SLAVE & MASTER !")
            tempo.fpga.pulser.mask_on_ext_trigger()
            tempo.fpga.pulser.set_sync_mode()

            if forever_pulser:
                tempo.fpga.pulser.sync_enable_forever()
                pulser_divider = 128
                tempo.board_config['pulser_divider'] = pulser_divider
                tempo.fpga.pulser.set_divider(pulser_divider)
            else:
                tempo.fpga.pulser.sync_disable_forever()

        else:
            tempo.fpga.pulser.mask_on_ext_trigger()
            tempo.fpga.pulser.mask_on_IO0()
            tempo.fpga.pulser.disable()
            tempo.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset

        if tempo.mode == 'master':

            # Output clock to slave
            tempo.fpga.OUT7_select.ck_from_PLL_OUT3()

            # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
            tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

            # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
            # tempo.fpga.select.ck_towards_FPGA.ck_from_PLL_OUT3()  # not needed !

            # Output reset to slave
            tempo.fpga.OUT2_select.tpr_rstn_local()

            # Use a splitter also for the reset in order for the reset to arrive at both ASIC simultaneously
            # tempo.fpga.enable_foreign_reset_enable()

            ####  Setup for coincidence (at least 2 ASICs)
            if len(tempo_list) >= 2:
                # Output reset to slave
                # tempo.fpga.OUT2_select.tpr_rstn_local()

                # Use a splitter also for the reset in order for the reset to arrive at both ASIC simultaneously
                tempo.fpga.enable_foreign_reset_enable()
            else:
                # tempo.fpga.OUT2_select.off()

                # Not to be sensitive by mistake on a SMA connected on IO8
                tempo.fpga.disable_foreign_reset_enable()
                print("disable_foreign_reset_enable")


            # tempo.fpga.OUT4_select.ck_from_PLL()

        elif tempo.mode == 'slave':

            # Select temporoc digital clock
            # tempo.clock.fpga.set.FPGA_as_clock_source()
            tempo.fpga.set.PLL_as_clock_source()
            if FPGA_PLL:
                print("Can not provide 320 MHz clock from PLL")
                exit(0)

            # Transmit temporoc digital clock from master to slave PLL
            tempo.fpga.select.ck_from_FPGA_to_PLL.input_clk2()
            # tempo.fpga.select.ck_towards_PLL.input_clk1()

            # Transmit temporoc digital clock from master to slave CK MUX
            # tempo.FPGA_IO.select.ck_towards_FPGA.input_clk2()
            # tempo.FPGA_IO.select.ck_towards_FPGA.input_clk1()

            # check on scope if clock indeed receives : fpga alters ck duty cycle and add delay !!
            # tempo.IO.OUT4_select.input_clk2()
            # tempo.IO.OUT4_select.clk_from_PLL()
            # tempo.fpga.OUT4_select.ck_towards_PLL()

            # tempo..FPGA_IO.select.ck_towards_PLL.get_config()
            # tempo.FPGA_IO.select.ck_towards_FPGA.get_config()
            # switch off the PLL todo ?

            # IO FPGA 8 fixed to receive tpr_resetn from MASTER (or the other way around) in firmware
            tempo.fpga.enable_foreign_reset_enable()

        else:
            print("Unknown mode : either MASTER or SLAVE")


        # while 1:
        #     tempo.pll.flashtest()
        if FPGA_PLL:
            # Select temporoc digital clock
            tempo.fpga.set.FPGA_as_clock_source()
            tempo.fpga.select.ck_from_FPGA_to_ASIC.clk_320()

            if ext_trigger:
                print("Not possible to send to external trigger without using external PLL")
                exit(0)
            elif laser:
                print("Not possible to send to external trigger for laser without using external PLL")
                exit(0)
            else:
                print("Will use FPGA PLL to provide 320 MHz clock to ASIC")

            tempo.pll.set_pll_rstb(0) # Don't bother
        else:
            # Select temporoc digital clock
            tempo.fpga.set.PLL_as_clock_source()
            tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
            # required to sync reset from FPGA to ASIC on the same clock phase as the clock provided to the ASIC by the PLL

            # # # debug PLL
            # tempo.fpga.OUT2_select.SPI_PLL_SCLK()
            # tempo.fpga.OUT3_select.SPI_PLL_CSb()
            # tempo.fpga.OUT4_select.SPI_PLL_MOSI()
            # tempo.fpga.OUT6_select.SPI_PLL_MISO()
            # tempo.fpga.OUT2_select.ck_from_PLL_OUT3()

            if ext_trigger:
                tempo.pll.flash("../config/PLL/Si5345_30%s_ck_%dMHz-Registers.txt" % (tempo.mode, tempo_dig_ck_freq),
                                tempo_dig_clock=tempo_dig_ck_freq, force_flash=force_flash_PLL)
                #             # PLL outputs
                #             # 0 : FPGA clock : 753 405*10
                #             # 3 : FPGA clock : 80M
                #             # 6 : TEMPOROC digital : 320M
                #             # 7 : external hit resync CK : =OUT0
                #             # 8 : standalone TDC ck : OFF

            elif laser:
                tempo.fpga.OUT6_select.ck_from_PLL_OUT3()
                print(
                    "FPGA IO6 should be connected to laser trigger in input \nand config as Ext Adj trigger, rising edge, Lvl 0 V")

                tempo.pll.flash("../config/PLL/Si5345_31-Registers.txt", tempo_dig_clock=tempo_dig_ck_freq, force_flash=force_flash_PLL)
                # PLL outputs
                # 0 : FPGA clock : 80M
                # 3 : FPGA clock : 100k
                # 6 : TEMPOROC digital : 320M
                # 7 : external hit : 320M
                # 8 : standalone TDC ck : OFF

            else:
                tempo.pll.flash("../config/PLL/Si5345_11%s_ck_%dMHz-Registers.txt" % (tempo.mode, tempo_dig_ck_freq),
                                tempo_dig_clock=tempo_dig_ck_freq, force_flash=force_flash_PLL)
                # PLL outputs
                # 0 : FPGA clock : 80M
                # 3 : FPGA clock : 320M for emulated coarse counter inside FPGA (mimic)
                # 6 : TEMPOROC digital : 320M
                # 7 : external hit resync CK : 40M (could be lower?)
                # 8 : standalone TDC ck : OFF


            # Expected PLL inputs
            # IN0 : 100M from cristal if ASIC = MASTER
            # IN0 : 80M from MASTER PLL if ASIC = SLAVE

        tempo.reset_power_check_correct_clock_init(FPGA_PLL)

        # DEBUG
        tempo.asic.i2c.check_all_register(config)

        if ext_trigger:
            tempo.board_config['ext_trigger'] = True

            if (tempo.mode == ext_trigger_init_side) and not forever_pulser:
                hit_freq_Hz = 25000
                tempo.fpga.pulser.set_frequency_in_Hz(
                    hit_freq_Hz)  # not higher otherwise temporoc has not enough time to TX data
                tempo.fpga.pulser.release_resetn_latch()
                expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count / 8 + 7
                N_per_iter = round(16230 * 2 / expected_bytes_per_event)
                # N_per_iter = 1
                tempo.fpga.pulser.set_nb_impulsions(N_per_iter)
        else:
            tempo.board_config['ext_trigger'] = False


        if probed_channel is not None:
            print("Probed_channel : ", probed_channel)
            tempo.fpga.set.hit_register_channel(probed_channel)
            tempo.asic.ch(probed_channel).select.analogProbe.shL()
            tempo.asic.common.probeDig.channel(probed_channel).TrigT_L()

        tempo.init_ASIC()


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

        tempo.save_ASIC_and_FPGA_config(config)

    return


def load_config(tempo_list, config):
    # Write SC configuration from board config file
    for tempo in tempo_list:

        enabled_ASIC_ch = tempo.board_config['enabled_ASIC_ch'][0]
        # print("enabled_ASIC_ch: ", np.sort(enabled_ASIC_ch))

        enable_TL_ASIC_ch = tempo.board_config['enable_TL_ASIC_ch'][0]
        print("enable_TL_ASIC_ch: ", np.sort(enable_TL_ASIC_ch))

        if 'SiPM_model' in tempo.board_config.keys():
            tempo.board_config['injected_channel_SiPM'] = [get_SiPM_ch(tempo.board_config['enable_TL_ASIC_ch'][0],
                                                                   tempo.board_config['SiPM_model'])]

        # tempo.board_config['injected_channel'] = tempo.board_config['enable_TL_ASIC_ch']
        if not tempo.board_config['ext_trigger']:
            tempo.board_config['injected_channel_SiPM'] = [get_SiPM_ch(tempo.board_config['enabled_ASIC_ch'][0],
                                                                  tempo.board_config['SiPM_model'])]

        tempo.asic.ch.all_except(enabled_ASIC_ch).disable.front_end_except_pdet()
        if 'patgain' in tempo.board_config.keys():
            tempo.asic.ch.group(enabled_ASIC_ch).set.patGain(tempo.board_config['patgain'])

        tempo.asic.ch.group(enabled_ASIC_ch).set.patComp(0) # Default well working value, tuning not needed.

        if 'palgGain' in tempo.board_config.keys():
            tempo.asic.ch.group(enabled_ASIC_ch).set.palgGain(tempo.board_config['palgGain'])

        if 'pahgGain' in tempo.board_config.keys():
            tempo.asic.ch.group(enabled_ASIC_ch).set.pahgGain(tempo.board_config['pahgGain'])

        if 'tauHG' in tempo.board_config.keys():
            tempo.asic.ch.group(enabled_ASIC_ch).set.tauHG(tempo.board_config['tauHG'])

        if 'tauLG' in tempo.board_config.keys():
            tempo.asic.ch.group(enabled_ASIC_ch).set.tauLG(tempo.board_config['tauLG'])

        tempo.asic.ch.all_except(enable_TL_ASIC_ch).disable.all_discri()
        # tempo.asic.ch.group(enable_TL_ASIC_ch).disable.all_discri()
        tempo.asic.ch.group(enable_TL_ASIC_ch).enable.TL()
        # tempo.asic.ch.group(enable_TL_ASIC_ch).enable.TH()
        tempo.asic.ch.group(enable_TL_ASIC_ch).enable.TQ()

        # tempo.asic.ch.all_except(channels_list).disable.front_end()

        if tempo.board_config['calib_time_discri']:
            use_calib_time_discri(tempo)

        if 'dacTL' in tempo.board_config.keys():
            tempo.asic.common.set.dacTL(tempo.board_config['dacTL'])

        if 'dacTH' in tempo.board_config.keys():
            tempo.asic.common.set.dacTH(tempo.board_config['dacTH'])

        if 'dacTQ' in tempo.board_config.keys():
            tempo.asic.common.set.dacQ(tempo.board_config['dacTQ'])

        ##### SiPM channel-wise gain ALIGNMENT #####"
        if tempo.board_config['calib_inDAC']:
            use_calib_inDAC(tempo)

        # if 'charge_filter' in tempo.board_config.keys():
        #     if tempo.board_config['charge_filter']:
        #         tempo.deserializer.filter.enable.charge()
        #         tempo.asic.ch.group(enable_TL_ASIC_ch).enable.TQ()
        #         tempo.asic.ch.all_except(enable_TL_ASIC_ch).disable.TQ()
        #         tempo.asic.interface.en.Nor_TrigQ_RS()  # for FPGA charge filter
        #     else:
        #         tempo.deserializer.filter.disable.charge()
        #         tempo.asic.ch.all().disable.TQ()
        #         tempo.asic.interface.dis.Nor_TrigQ_RS()  # for FPGA charge filter

        clusters_list = np.unique(np.array(enable_TL_ASIC_ch) // 16).tolist()
        tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)
        update_config_dict(tempo.board_config, clusters_list)
        tempo.board_config['power_cluster'] = [clusters_list]




    tempo_list[0].save_ASIC_and_FPGA_config(config)


def use_calib_time_discri(tempo:temporoc3, calib_time_discri_file=None):
    if not calib_time_discri_file:
        # calib_file = '../config/TEMPOROC/B%d_calib_TL_staircase.csv' % (tempo.board_config['board'])
        calib_time_discri_file = '../config/TEMPOROC/B%d_calib_discri.csv' % (tempo.board_config['board'])

    if not os.path.exists(calib_time_discri_file):
        print("File does not exists ! %s" % calib_time_discri_file)
        print("Aligning discri threshold : new measurement required")
        # print("file://"+os.path.abspath(inspect.getsourcefile(lambda: 0)).replace("\", "/")"+":"+str(sys._getframe(1).f_lineno)) #inspect.currentframe().f_back.f_lineno))
        # print("file:///tmp/file%20with%20space.txt:18:3")
        exit()
        # TL_efficiency_50_after_calib = align_thresholds_with_scurve(tempo, config, local_output_dir)
    else:
        df_calib_time_discri = pd.read_csv(calib_time_discri_file)
        IbCalibDAC = int(np.unique(df_calib_time_discri.IbCalibDAC))
        tempo.asic.bias.calibDac.Ib.set_4b(IbCalibDAC)
        print("Aligning discri thresholds : using channelwise correction : %s with IbCalibDAC %d" % (calib_time_discri_file, IbCalibDAC))

        col_gain_list = [col for col in df_calib_time_discri.columns if col.endswith('_calibDAC')]
        for col_gain in col_gain_list:
            for channel in np.unique(df_calib_time_discri.channel):
                dac_calib_value = int(df_calib_time_discri.loc[df_calib_time_discri.channel == channel, col_gain].iloc[0])
                tempo.asic.ch(int(channel)).set.calibDACTx(col_gain, dac_calib_value)

        print("Discri thresholds aligned on %.1f∓%.1f dac for 1 and %.1f∓%.1f for 2"%
              (df_calib_time_discri.T1_after_calib.mean(), df_calib_time_discri.T1_after_calib.std(),
               df_calib_time_discri.T2_after_calib.mean(), df_calib_time_discri.T2_after_calib.std()))

def use_calib_inDAC(tempo:temporoc3, calib_file=None):
    if not calib_file:
        calib_file = '../config/TEMPOROC/B%d_calib_inDAC.csv' % (tempo.board_config['board'])

    print("SiPM channel-wise gain ALIGNMENT")
    if not os.path.exists(calib_file):
        print("File does not exists ! %s"%calib_file)
        print("Run first align_SiPM_gain_with_inDAC()  from uniformize_ch_reponse.py")
        exit()
    else:
        print("Applying inDAC channel-wise correction from %s" % calib_file)
        df_calib_inDAC = pd.read_csv(calib_file)
        for channel in range(64):  # config['enable_TL_ASIC_ch'][0]:
            channel_inDac_correction = df_calib_inDAC.loc[df_calib_inDAC.channel == channel, 'inDAC_calib']
            inDAC_value = int(channel_inDac_correction.iloc[0])
            tempo.asic.ch(channel).set.inDac(inDAC_value)


def probe_channel(tempo:temporoc3, probed_ASIC_channel):
    assert isinstance(probed_ASIC_channel, int)

    print("probed_channel : ", probed_ASIC_channel)
    tempo.fpga.set.hit_register_channel(probed_ASIC_channel)
    tempo.asic.ch(probed_ASIC_channel).select.analogProbe.shL()
    print("SH LG probe enabled")
    tempo.asic.common.probeDig.channel(probed_ASIC_channel).TrigT_L()

    tempo.asic.interface.en.LG_pdet_MUX_output()
    tempo.asic.interface.en.HG_pdet_MUX_output()
    tempo.asic.interface.en.trigT_L_RS_mux()
    tempo.asic.interface.en.trigT_H_RS_mux()
    tempo.asic.interface.en.Nor_TrigQ()
    tempo.asic.interface.en.Nor_TrigQ_RS()
    tempo.asic.interface.en.Nor_TrigT_L_RS()
    tempo.asic.interface.en.Nor_TrigT_H_RS()
    tempo.asic.interface.en.analog_probe()
    tempo.asic.interface.en.digital_probe()

    tempo.fpga.OUT4_select.digit_probe()

    tempo.board_config['probed_channel'] = probed_ASIC_channel


def acquire_data_multi_boards_safe(Nevents, config, tempo_list: List[temporoc3], measure_label=''):
    # sanity check
    if tempo_list[0].mode != 'master':
        print("First instance of temporoc of the list should be the MASTER ! here %s"%(tempo_list[0].mode))
        exit()

    reset_FPGA_FIFO_and_tempo_digital(tempo_list) # Only ONCE at startup

    for missing_keys in ['log', 'start_time']:
        if missing_keys not in config.keys():
            config[missing_keys] = []

    # Auto-restart after USB crash/error
    while True:
        try:
            config['log'].append("Measurement starts at " + datetime.now().strftime("%H:%M:%S"))
            config['start_time'] = int(datetime.now().timestamp())
            acquire_data_multi_boards(Nevents, config, tempo_list, measure_label)

        except (device.FtdInterfaceError, ftd2xx.DeviceError) as e:
            print(e)
            config['log'].append("USB reboot at "+datetime.now().strftime("%H:%M:%S")+' : '+str(e))

            for tempo in tempo_list:
                tempo.dev.close()

            config_file = config['save_folder'] + 'config.yaml'
            with open(config_file, 'w') as outfile:
                yaml.dump(config, outfile, default_flow_style=False, Dumper=VerboseSafeDumper)
            outfile.close()

            time.sleep(1)
        else:
            break


def reset_FPGA_FIFO_and_tempo_digital(tempo_list: List[temporoc3]):

    if len(tempo_list) > 1:
        assert tempo_list[0].mode == 'master', 'First of tempo_list must be the master, then followed by slaves.'
        for i in range(1, len(tempo_list)):
            assert tempo_list[i].mode == 'slave', '%d should be a slave!'%i

    for tempo in tempo_list:
        tempo.deserializer.close()

    # reset FIFO and overflow counter on both side to make FPGA ready to receive events
    for tempo in tempo_list:
        tempo.deserializer.reset_then_leave_closed()

    # reset ASICs and de-flush deserialiser on both slave & master sides
    # propagate to slave only if foreign reset enabled and SMA cable connected !

    tempo_list[0].fpga.reset.tpr_digital() # ONLY MASTER needs to be reset !
    time.sleep(0.1) # wait for the reset to propagate

    for tempo in tempo_list:
        tempo.deserializer.open()



def acquire_data_multi_boards(Nevents, config, tempo_list: List[temporoc3], measure_label=''):
    """
    Readout FPGA FIFO (up to 4)    
    :param Nevents:  Target number of events to extract
    :param config: config view of temporoc object
    :param tempo_list: List of temporoc object : first is always the master
    :param measure_label: optional suffix for saving data
    :return: 
    """
    # cluster témoin
    control_cluster = config['config_B%d' % (tempo_list[-1].board)]['power_cluster'][0][-1]

    try:
        events_received = [0] * len(tempo_list)
        all_event_counts_equal_total = [0] * len(tempo_list)
        events_in_coincidence = 0
        init_start = time.perf_counter()
        # with alive_bar(Nevents, force_tty=True) as bar:  # your expected total for all clusters
        if 1 :
            while events_in_coincidence < Nevents:

                # Readout rate optimisation : delay USB queries until one control fifo is almost full
                # start = time.perf_counter()
                MSB_bytes_to_extract = 0
                iter = 0
                while MSB_bytes_to_extract < 120:  # 125<<8 = ~32kbytes max in FIFO
                    iter += 1
                    MSB_bytes_to_extract = tempo_list[-1].deserializer.get_MSB_number_of_bytes_in_fifo(control_cluster)
                    if iter>1e3:
                        print("FIFO%d of B%d is not receiving any events ! Check deserialiser status ! "%(control_cluster, tempo_list[-1].board))
                        tempo_list[-1].deserializer.get_status()
                        break
                    # time.sleep(0.01)
                # delay = time.perf_counter()-start
                # print("delay %d ms   MSB_bytes_to_extract = %d " % (delay * 1e3, MSB_bytes_to_extract))

                # # close fifo before reading, so new events don't come meanwhile emptying
                for tempo in tempo_list:
                    tempo.deserializer.close()

                for ti, tempo in enumerate(tempo_list):
                    if tempo.mode == '':
                        label_mode = ''
                    else:
                        label_mode = '_%s' % tempo.mode

                    injected_cluster = config['config_B%d'%tempo.board]['power_cluster'][0]
                    local_filepath_list = [config['save_folder'] + "B%d%s_cluster_%d%s.csv"% (tempo.board, label_mode, cluster, measure_label) for cluster in injected_cluster]

                    events_extracted_list = tempo.deserializer.extract_all_data(injected_cluster, local_filepath_list, config['config_B%d'%tempo.board])

                    # print("delay %d ms   events extracted = %d " % (delay * 1e3, events_extracted_list[-1]))

                    all_event_counts_equal = events_extracted_list.count(events_extracted_list[0]) == len(events_extracted_list)
                    all_event_counts_equal_total[ti] += int(all_event_counts_equal)

                    # PRINT RECEIVED EVENTS for each board
                    if len(events_extracted_list) > 0:
                        events_received[ti] += min(events_extracted_list)
                        endf = '\n' if ti == len(tempo_list) - 1 else '\t\t'

                        if min(events_extracted_list) > 0:
                            stop = time.perf_counter()
                            avg_rate = int(events_received[ti] / (stop - init_start))
                            print("B%d: %d (+%d, %d/s)" % (tempo.board,
                                events_received[ti], min(events_extracted_list), avg_rate), end=endf)
                            config['rate_Hz'] = avg_rate
                        else:
                            print("B%d seems strange: events received "%(tempo.board)+"for clusters "+str(injected_cluster)+"="+str(events_extracted_list))
                            print("Reset manually the board or review your config!")
                            exit()
                        # if all(v==0 for v in events_extracted_list):
                        #     print("B%d seems strange: not receiving any event! Reset manually the board or review your config!"%tempo.board)
                        #     exit()

                # COINCIDENCE SEARCH
                live_process = False
                if live_process:
                    files = glob.glob(config['save_folder'] + '/B*.csv')
                    exploitable_event_count, events_in_coincidence = fast_compute_coincidence_events(files, config, 0) # min(events_asked_count)

                    coincidence_rate = events_in_coincidence/(int(datetime.now().timestamp()) - config['start_time'])
                    config['coincidence_rate'] = coincidence_rate

                    print('slave : %d %% (%d)  master :  %d %% (%d)  coincidence: %.1f/s (%d)'% (
                        exploitable_event_count[0]/events_received[0]*100, exploitable_event_count[0],
                        exploitable_event_count[1]/events_received[1]*100, exploitable_event_count[1],
                        coincidence_rate, events_in_coincidence))
                else:
                    events_in_coincidence = min(events_received)

                # reopen fifo for next round
                for tempo in tempo_list:
                    tempo.deserializer.open()


                # save_config_file(config)
                # stop = time.perf_counter()
                # print("analysis : %d ms"%((stop - start) * 1e3))
    finally:
        save_config_file(config)


    print('Acquisition finished.')


def fast_compute_coincidence_events(files, config, skiprows):
    df = pd.DataFrame()
    coincidence_events_count = 0


    raw_event_count = 0
    exploitable_event_count = [0, 0]

    for fi, file in enumerate(files):
        if os.path.exists(file):
            cluster = re.findall("(?<=cluster_)[0-9]+", file)
            cluster = int(cluster[0]) if cluster else 0

            current_board = int(re.findall("(?<=\\\\B)[0-9]+", file)[0])
            board_index = [i for i, board in enumerate(config['board']) if config['board'][i] == current_board][0]
            injected_channel_list_for_this_board = config['enable_TL_ASIC_ch'][board_index]

            injected_channel_within_cluster = [ch for ch in injected_channel_list_for_this_board if ch//16==cluster]
            df_tmp = pd.read_csv(file, header=None, usecols=[0, 2, 3, 6 + 16 + (injected_channel_within_cluster[0] % 16)],
                                 names=['status', 'time', 'msb_cpt', 'tdc'], skiprows=skiprows,
                                 converters={"time": lambda x: int(x, 16), "msb_cpt": lambda x: int(x, 16), "tdc": lambda x: int(x, 16)})
            raw_event_count += len(df_tmp)
            df_tmp=df_tmp[(df_tmp.tdc!=0) & (df_tmp.status==0)]

            new_series_set = {'CPT': np.left_shift(df_tmp.time, 14) + np.left_shift(df_tmp.msb_cpt, 4)}
            df_tmp = pd.concat([df_tmp, pd.DataFrame(new_series_set)], axis=1)
            df_tmp = df_tmp.drop(labels='tdc', axis="columns")

            board = int(re.findall("(?<=B)[0-9]+", file)[0])
            index_exploitable_event_count = 0 if config['board_to_mode'][board]=='slave' else 1
            exploitable_event_count[index_exploitable_event_count] = len(df_tmp)

            if fi == 0:
                df = df_tmp
            else:
                df = df.merge(df_tmp, on='CPT', how='inner')
                pass

    coincidence_events_count = len(df)

    # return raw_event_count, coincidence_events_count
    return exploitable_event_count, coincidence_events_count


def align_thresholds_with_scurve_align_on_the_fly(tempo, config):
    # NB : Not super great !
    # idea : align progressively channels to minimise the number of dac values to explore !
    # BUT: poor estimation of the lsb over a gap of 5 dac values
    # lsb should be estimated over full DAC span instead !
    # thus not possible to align of the fly channel-wise the pedestal


    gain_list = ['TL']
    # scurves are to be done with a signal injection simultaneously of a given charge
    # scurve should not be performed without charge injection to detect the pedestal
    # pedestals should be aligned not on the envelopp but on the baseline (middle between the 2 pedestals)
    start = time.perf_counter()

    # FIND DAC ratio dac10b/dac6b by sweeping THRESHOLDS
    board = tempo.board
    tempo.setup_scurve_all_ch(gain_list)
    # print("ib_calibDAC should be 7 ", (tempo.dev.i2c.read_register(64, 2) & 0xf0) >> 4)
    # print("ib_calibDAC should be 7 ", (tempo.dev.i2c.read_register(64, 2) & 0xf0) >> 4)
    # print("ib_calibDAC should be 7 ", (tempo.dev.i2c.read_register(64, 2) & 0xf0) >> 4)

    df = pd.DataFrame()
    file_scurve = config['save_folder'] + "B%d_trigger_effiency_threshold_scan.csv" %board
    file_calib_discri = config['save_folder'] + "B%d_calib_TL.csv" % board
    plot_folder = config['save_folder'] + '../plot/'
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)


    file_DAC_ratio = "../config/TEMPOROC/B%d_DAC_ratio.csv"%board
    need_to_redo_DAC_ratio = True
    IbCalibDAC = tempo.asic.bias.calibDac.Ib.get()

    if os.path.exists(file_DAC_ratio):
        df_DAC_ratio = pd.read_csv(file_DAC_ratio)
        print("Using recorded data for IbCalibDAC = %d to estimate TL_DAC_ratio = DAC global / DAC local"%IbCalibDAC)
        df_DAC_ratio = df_DAC_ratio[df_DAC_ratio.IbCalibDAC==IbCalibDAC]

        if len(df_DAC_ratio) > 0:
            need_to_redo_DAC_ratio=False
            min_DAC_ratio = df_DAC_ratio.DAC_ratio.min()

    # DAC LOCAL to MIN
    calibDacLocal_min = 0
    tempo.asic.ch.all().set.calibDACT1(calibDacLocal_min)
    tempo.asic.ch.all().set.calibDACT2(calibDacLocal_min)
    time.sleep(0.1)
    df0 = tempo.get_scurve_all_ch(range(80, 1023, 10))  # large step
    figname = "0_dacLocal_%s" % calibDacLocal_min
    global_dac_min, global_dac_max, local_thresh_in_global_dacu_for_each_gain, channel_to_ignore_for_each_gain = analyse_poor_granularity_scurve(df0, plot_folder, figname, board, gain_list)
    print("Found coarse threshold position for all channels")

    # ALIGN THRESHOLDS
    file_hypothetic_DAC_ratio = "../config/TEMPOROC/DAC_ratio.csv"
    df_DAC_ratio = pd.read_csv(file_hypothetic_DAC_ratio)
    print("Using recorded data for IbCalibDAC = %d to estimate TL_DAC_ratio = DAC global / DAC local" % IbCalibDAC)
    df_DAC_ratio = df_DAC_ratio[df_DAC_ratio.IbCalibDAC == IbCalibDAC]
    # hypothetic_DAC_ratio = 0.55
    hypothetic_DAC_ratio = df_DAC_ratio.TL_DAC_ratio

    if 'TL' in gain_list:
        TL_eff_50 = local_thresh_in_global_dacu_for_each_gain[0]
        aligned_value = np.mean(TL_eff_50)
        dac_calib_half_range = 32
        TL_localDAC_0 = np.int32(dac_calib_half_range - (
                (np.array(TL_eff_50) - aligned_value) / hypothetic_DAC_ratio))
        TL_localDAC_0 = np.clip(TL_localDAC_0, 0, 63)  # saturate
    for channel in range(64):
        tempo.asic.ch(channel).set.calibDACT1(int(TL_localDAC_0[channel]))

    if need_to_redo_DAC_ratio:
        # small step
        df0 = tempo.get_scurve_all_ch(range(int(aligned_value)-5, 1024, 1))
        # df0 = tempo.get_scurve_all_ch(range(global_dac_min, global_dac_max + 5, 1))
        figname = "1_dacLocal_channelwise"
        TL_efficiency_50_calib_0, TH_efficiency_50_calib_0, noise_calib_0 = analyse_scurve(df0, plot_folder, figname, board, discri_list=gain_list)

        # df0['calibDacTL'] = calibDacLocal_min
        # df0['calibDacTH'] = calibDacLocal_min
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_scurve, index=False)

        print("Found fine threshold position for all channels to estimate DAC calib ratio for IbCalibDAC = %d"%IbCalibDAC)

        if 'TL' in gain_list:
            TL_eff_50 = local_thresh_in_global_dacu_for_each_gain[0]
            aligned_value = np.mean(TL_eff_50)
            # dac_calib_half_range = 32
            TL_localDAC_1 = np.int32(TL_localDAC_0 - (
                    (np.array(TL_eff_50) - aligned_value) / hypothetic_DAC_ratio))
            TL_localDAC_1 = np.clip(TL_localDAC_1, 0, 63)  # saturate

        offset_to_compute_DACratio = 5
        for channel in range(64):
            if abs(TL_localDAC_1[channel]-TL_localDAC_0[channel])<=offset_to_compute_DACratio:
                # make it different to allow DAC_ratio computation
                if TL_localDAC_1[channel]>=(64-offset_to_compute_DACratio):
                    TL_localDAC_1[channel] -= offset_to_compute_DACratio
                else:
                    TL_localDAC_1[channel] += offset_to_compute_DACratio
            tempo.asic.ch(channel).set.calibDACT1(int(TL_localDAC_1[channel]))

    # DAC LOCAL to MAX
    # calibDacLocal_max = 63
    # tempo.asic.ch.all().set.calibDacTL(calibDacLocal_max)
    # tempo.asic.ch.all().set.calibDacTH(calibDacLocal_max)
    # print("calibDacTL should be 32 ", tempo.dev.i2c.read_register(0, 5))
    time.sleep(0.1)
    # min_expected_offset = + int(calibDacLocal_max * min_DAC_ratio)
    df0 = tempo.get_scurve_all_ch(range(int(aligned_value)-10, 1023, 1))
    # df0 = tempo.get_scurve_all_ch(range(global_dac_min + min_expected_offset, 1023, 1))
    figname = "2_dacLocal_channelwise"
    TL_efficiency_50_calib_1, TH_efficiency_50_calib_1, noise_calib_1 = analyse_scurve(df0, plot_folder, figname, board, discri_list=gain_list)
    # df0['calibDacTL'] = calibDacLocal_max
    # df0['calibDacTH'] = calibDacLocal_max
    df = pd.concat([df, df0], ignore_index=True)
    df.to_csv(file_scurve, index=False)
    print("Found fine threshold position for all channels")

    if need_to_redo_DAC_ratio:
        # COMPUTE TL_DAC_ratio = 10b_DAC_global / 6b_DAC_local
        DAC_ratio_per_ch_for_one_IbCalibDAC = {}
        DAC_ratio_per_ch_for_one_IbCalibDAC['channel'] = list(range(64))
        DAC_ratio_per_ch_for_one_IbCalibDAC['IbCalibDAC'] = [IbCalibDAC] * 64

        plt.figure(figsize=(13, 7))

        if 'TL' in gain_list:
            TL_DAC_ratio = (np.array(TL_efficiency_50_calib_1) - np.array(TL_efficiency_50_calib_0)) / (TL_localDAC_1-TL_localDAC_0)

            DAC_ratio_per_ch_for_one_IbCalibDAC['TL_efficiency_50_calib_0'] = TL_efficiency_50_calib_0
            DAC_ratio_per_ch_for_one_IbCalibDAC['TL_efficiency_50_calib_1'] = TL_efficiency_50_calib_0
            DAC_ratio_per_ch_for_one_IbCalibDAC['TL_DAC_ratio'] = list(TL_DAC_ratio)
            yerr = abs(((noise_calib_0[0]**2+noise_calib_1[0]**2)**0.5) / (TL_localDAC_1-TL_localDAC_0))
            plt.errorbar(x=list(range(64)), y=TL_DAC_ratio, yerr=yerr, label='TL')

        if 'TH' in gain_list:
            TH_DAC_ratio = (np.array(TH_efficiency_50_calib_1) - np.array(TH_efficiency_50_calib_0)) / (TL_localDAC_1 - TL_localDAC_0)
            DAC_ratio_per_ch_for_one_IbCalibDAC['TH_efficiency_50_calib_0'] = TH_efficiency_50_calib_0
            DAC_ratio_per_ch_for_one_IbCalibDAC['TH_efficiency_50_calib_1'] = TH_efficiency_50_calib_1
            DAC_ratio_per_ch_for_one_IbCalibDAC['TH_DAC_ratio'] = list(TH_DAC_ratio)

            plt.plot(TH_DAC_ratio, label='TH')

        plt.plot(hypothetic_DAC_ratio, label='hypothetic TL')
        df_DACratio = pd.DataFrame(DAC_ratio_per_ch_for_one_IbCalibDAC)
        df_DACratio.to_csv(config['save_folder']+"B%d_DAC_ratio.csv"%board, index=False)

        plt.xlabel('Channel')
        plt.ylabel('DAC_ratio')
        plt.legend()
        plt.grid()
        plt.tight_layout()
        plt.savefig(plot_folder + "DAC_CALIB_ratio.png")
        plt.close()
    else:
        TL_DAC_ratio = df_DAC_ratio.TL_DAC_ratio

    # COMPUTE CALIB_6b_DAC
    res = {'channel': range(64)}

    if 'TL' in gain_list:
        median_TL_global_threshold = np.median(TL_efficiency_50_calib_1)
        TL_localDAC_2 = np.int32(TL_localDAC_1 + ((median_TL_global_threshold - np.array(TL_efficiency_50_calib_1)) / TL_DAC_ratio))
        TL_localDAC_2 = np.clip(TL_localDAC_2, 0, 63)  # saturate
        TL_expected_DAC_global = TL_efficiency_50_calib_1 + (TL_localDAC_2 - TL_localDAC_1) * TL_DAC_ratio
        res.update({
            'TL_DAC_ratio': TL_DAC_ratio,
            'TL_calib_DAC_local': TL_localDAC_2,
            'TL_expected_DAC_global': TL_expected_DAC_global})

        TL_efficiency_50_min_calibDAC =  TL_efficiency_50_calib_1 + (0 - TL_localDAC_1) * TL_DAC_ratio
        TL_efficiency_50_max_calibDAC = TL_efficiency_50_calib_1 + (63 - TL_localDAC_1) * TL_DAC_ratio

    # if 'TH' in gain_list:
    #     median_TH_global_threshold = np.median(TH_efficiency_50_max_calibDAC)
    #     TH_dac_calib = np.int32(dac_calib_half_range - (
    #                 (np.array(TH_efficiency_50_max_calibDAC) - median_TH_global_threshold) / TH_DAC_ratio))
    #     TH_dac_calib = np.clip(TH_dac_calib, 0, 63)  # saturate
    #     TH_expected_DAC_global = TH_efficiency_50_max_calibDAC + (TH_dac_calib - calibDacLocal_max) * TH_DAC_ratio
    #
    #     res.update({'TH_DAC_ratio': TH_DAC_ratio,
    #                 'TH_calib_DAC_local': TH_dac_calib,
    #                 'TH_expected_DAC_global': TH_expected_DAC_global
    #                 })
    df_calib_discri = pd.DataFrame(res)
    df_calib_discri.to_csv(file_calib_discri, index=False)
    print("Found required calibration for all channels")

    # ALIGN THRESHOLDS
    for channel in range(64):
        if 'TL' in gain_list:
            dac_calib_value = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'TL_calib_DAC_local'].iloc[0])
            tempo.asic.ch(channel).set.calibDACT1(dac_calib_value)
        if 'TH' in gain_list:
            dac_calib_value = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'TH_calib_DAC_local'].iloc[0])
            tempo.asic.ch(channel).set.calibDACT2(dac_calib_value)

    # TEST THRESHOLD CALIBRATION
    if 'TL' in gain_list:
        DAC_global_min = int(df_calib_discri['TL_expected_DAC_global'].min())
    if 'TH' in gain_list:
        DAC_global_min = int(df_calib_discri['TH_expected_DAC_global'].min())
    if ('TL' in gain_list) and ('TH' in gain_list):
        DAC_global_min = min(int(df_calib_discri['TL_expected_DAC_global'].min()), df_calib_discri['TH_expected_DAC_global'].min())

    # DAC_global_max = max(int(df_calib_discri['TL_expected_DAC_global'].max()), df_calib_discri['TH_expected_DAC_global'].max())
    DAC_global_max = 1023

    df0 = tempo.get_scurve_all_ch(range(DAC_global_min - 10, DAC_global_max + 5, 1))

    figname = "3_dacLocal_channelwise"
    TL_efficiency_50_after_calib, TH_efficiency_50_after_calib,noise_in_global_dacu_for_each_gain = analyse_scurve(df0, plot_folder, figname, board, discri_list=gain_list)
    if 'TL' in gain_list:
        dac_calib_dict = {ch:df_calib_discri['TL_calib_DAC_local'][ch] for ch in range(64)}
        df0['calibDacTL'] = df0.channel.map(dac_calib_dict)
        df_calib_discri['TL_efficiency_50_after_calib'] = TL_efficiency_50_after_calib
    if 'TH' in gain_list:
        dac_calib_dict = {ch:df_calib_discri['TH_calib_DAC_local'][ch] for ch in range(64)}
        df0['calibDacTH'] = df0.channel.map(dac_calib_dict)
        df_calib_discri['TH_efficiency_50_after_calib'] = TH_efficiency_50_after_calib
    df = pd.concat([df, df0], ignore_index=True)
    df.to_csv(file_scurve, index=False)

    print("Verifying threshold calibration")
    df_calib_discri.to_csv(file_calib_discri, index=False)

    print("align_thresholds_with_scurve  Elapsed time : %d seconds" % (time.perf_counter() - start))

    for gain in gain_list:
        plt.figure(figsize=(13, 7))
        plt.plot(TL_localDAC_0, marker='o', label='TL_localDAC_0')
        plt.plot(TL_localDAC_1, marker='o', label='TL_localDAC_1')
        plt.plot(df_calib_discri[gain+'_calib_DAC_local'], marker='o', label='final')
        plt.legend()
        plt.xlabel('Channel')
        plt.ylabel('calib_DAC_local')
        plt.title(f'Calibration for local threshold DAC for {gain} discriminator')
        plt.grid()
        plt.tight_layout()
        plt.savefig(plot_folder + f"calib_DAC_local_{gain}.png")

        plt.figure(figsize=(13, 7))
        if need_to_redo_DAC_ratio:
            plt.fill_between(range(64), eval(gain+'_efficiency_50_min_calibDAC'),
                             eval(gain+'_efficiency_50_max_calibDAC'), color='gold', label='Correction range')
        else:
            plt.fill_between(range(64), df_DAC_ratio[gain+'_efficiency_50_calibDacTL_0'],
                             df_DAC_ratio[gain+'_efficiency_50_calibDacTL_63'], color='gold', label='Correction range')
        plt.plot(range(64), eval(gain+'_expected_DAC_global'), marker='o', label='Expected thresholds')
        plt.plot(range(64), eval(gain+'_efficiency_50_after_calib'), marker='o', label='Measured thresholds')
        plt.xlabel('Channel')
        plt.ylabel('Global thresholds [dac]')
        plt.title(f'Thresholds for {gain} discriminator')
        plt.legend()
        plt.grid()
        plt.tight_layout()
        plt.savefig(plot_folder + gain+ "_thresholds.png")
        plt.show()

    return TL_efficiency_50_after_calib, TH_efficiency_50_after_calib

def compute_calibDAC(df_DAC_ratio_for_one_IbCalibDAC, df_calib_discri,
                     init_calibDAC_all_discri=32, current_Tx_all_discri=None):
    discri_list = [1, 2]

    res = {'channel': [], 'IbCalibDAC': []}
    for discri in discri_list:
        res.update({'T%d_calibDAC_min'%discri:[], 'T%d_calibDAC_max'%discri:[],
                   'T%d_DAC_ratio'%discri: [], 'T%d_calibDAC'%discri: [], 'T%d_expected'%discri:[],
                   'T%d_after_calib'%discri:[]})

    local_df_DAC_ratio = df_DAC_ratio_for_one_IbCalibDAC.sort_values("channel")

    # compute ideal threshold onto which both discris should be aligned
    # T1_calibDAC_max = local_df_DAC_ratio['T1_calibDac_63'].values
    # median_T1 = np.nanmedian(T1_calibDAC_max)

    for discri in discri_list:
        Tx_DAC_ratio = local_df_DAC_ratio['T%d_DAC_ratio' % discri].values  # .mean()
        Tx_calibDAC_max = local_df_DAC_ratio['T%d_calibDac_63' % discri].values
        Tx_calibDAC_min = local_df_DAC_ratio['T%d_calibDac_0' % discri].values
        if init_calibDAC_all_discri == 32:
            # measuring dispersion on both max & min ?
            current_Tx = Tx_calibDAC_max
            init_calibDAC_for_discri = 63
            offset_to_center = -32
            target_aligned_threshold = np.nanmedian(local_df_DAC_ratio['T1_calibDac_63'].tolist() + local_df_DAC_ratio['T2_calibDac_63'].tolist())

        else:
            current_Tx = current_Tx_all_discri[discri-1]
            init_calibDAC_for_discri = init_calibDAC_all_discri[discri-1]
            offset_to_center = 0
            target_aligned_threshold = np.nanmedian(current_Tx_all_discri)
            pass

        Tx_calibDAC_adjusted = init_calibDAC_for_discri + (target_aligned_threshold - current_Tx) / Tx_DAC_ratio
        Tx_calibDAC_adjusted = np.int32(np.round(np.nan_to_num(Tx_calibDAC_adjusted, nan=0)))
        Tx_calibDAC_adjusted = np.clip(Tx_calibDAC_adjusted+offset_to_center, 0, 63)  # saturate
        Tx_expected = current_Tx + (Tx_calibDAC_adjusted - init_calibDAC_for_discri) * Tx_DAC_ratio

        if init_calibDAC_all_discri != 32:
            pass

        res['T%d_DAC_ratio' % discri] += Tx_DAC_ratio.round(3).tolist()
        res['T%d_calibDAC' % discri] += Tx_calibDAC_adjusted.tolist()
        res['T%d_calibDAC_min' % discri] += Tx_calibDAC_min.round(1).tolist()
        res['T%d_calibDAC_max' % discri] += Tx_calibDAC_max.round(1).tolist()
        res['T%d_expected' % discri] += Tx_expected.round(1).tolist()
        res['T%d_after_calib' % discri] += [-1.0] * 64

    res['channel'] += local_df_DAC_ratio['channel'].tolist()
    res['IbCalibDAC'] += df_DAC_ratio_for_one_IbCalibDAC.IbCalibDAC.tolist()

    df_calib_discri = pd.concat([df_calib_discri, pd.DataFrame(res)])
    return df_calib_discri


def align_thresholds_with_scurve_following_IbcalibDAC_sweep(board, asic_id, ibCalibDAC_folder, forced_index=None):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/B%d_TPR%d/scurve/" % (board, asic_id)
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config, forced_index=forced_index)

    tempo = temporoc3(config)
    setup_temporoc([tempo], config)
    tempo.setup_scurve_all_ch()
    tempo.asic.common.set.bias_1V(11)  # Vbias_1V = 1V for B6

    iteration = 2
    file_scurve = local_output_dir+"B%d_trigger_effiency_threshold_scan.csv" %board
    file_calib_discri = [local_output_dir+"B%d_calib_discri_iter_%d.csv" % (board, i) for i in range(iteration)]
    file_DAC_ratio = ibCalibDAC_folder+"B%d_DAC_ratio.csv"%board #../config/TEMPOROC/

    df_DAC_ratio = pd.read_csv(file_DAC_ratio)

    # CHANNEL-WISE threshold DAC calibration
    discri_list = [1,2]
    IbCalibDAC_list = np.sort(np.unique(df_DAC_ratio.IbCalibDAC))[::-1]
    # IbCalibDAC_list = [7]
    df = pd.DataFrame()

    file_calib_discri_exist = [os.path.exists(file_calib_discri[i]) for i in range(iteration)]
    if any(file_calib_discri_exist):
        # last existing file in iteration order
        last_file_calib_discri = file_calib_discri[[i for bool, i in enumerate(file_calib_discri_exist) if bool][-1]]
        df_calib_discri = pd.read_csv(last_file_calib_discri)
    else:
        df_calib_discri = [pd.DataFrame()]*iteration
        print("calibDAC=channel-wise correction. Sweeping with fine step to check alignment. 1st iteration")

        for IbCalibDAC in IbCalibDAC_list:
            print("### Ib_calibDAC = %d " % IbCalibDAC)
            tempo.asic.bias.calibDac.Ib.set_4b(int(IbCalibDAC))

            for i in range(iteration):
                figname = "3_ibCalibDac_%d_iter_%d"%(IbCalibDAC, i)
                print("Iteration %d " % i, end='')

                # COMPUTE CALIB_6b_DAC CHANNEL-WISE calibration value
                df_DAC_ratio_for_one_IbCalibDAC = df_DAC_ratio[df_DAC_ratio.IbCalibDAC == IbCalibDAC]
                if i == 0:
                    df_calib_discri[i] = compute_calibDAC(df_DAC_ratio_for_one_IbCalibDAC, df_calib_discri[i])
                else:
                    selection = (df_calib_discri[i-1].IbCalibDAC == IbCalibDAC)
                    init_calibDAC_all_discri = [df_calib_discri[i-1].loc[selection, 'T%d_calibDAC' % discri].values for discri in discri_list]
                    current_Tx_all_discri = [df_calib_discri[i-1].loc[selection, 'T%d_after_calib' % discri].values for discri in discri_list]

                    df_calib_discri[i] = compute_calibDAC(df_DAC_ratio_for_one_IbCalibDAC, df_calib_discri[i],
                                                       init_calibDAC_all_discri=init_calibDAC_all_discri,
                                                          current_Tx_all_discri=current_Tx_all_discri)

                # ALIGN THRESHOLDS
                IbCalibDAC_selection = (df_calib_discri[i].IbCalibDAC == IbCalibDAC)
                for channel in range(64):
                    ch_selection = (df_calib_discri[i].channel == channel) & IbCalibDAC_selection
                    for discri in discri_list:
                        dac_calib_value = int(df_calib_discri[i].loc[ch_selection, 'T%d_calibDAC'%discri].iloc[0])
                        tempo.asic.ch(channel).set.calibDACTx(discri, dac_calib_value)
                time.sleep(0.1)

                # VERIFY THRESHOLD CALIBRATION
                DAC_global_min = df_calib_discri[i].loc[IbCalibDAC_selection, 'T1_expected'].min()
                DAC_global_min = min(DAC_global_min, df_calib_discri[i].loc[IbCalibDAC_selection, 'T2_expected'].min())
                DAC_global_min = int(DAC_global_min)-20
                # assert DAC_global_min > 0
                if DAC_global_min <= 0:
                    pass

                df0 = tempo.get_scurve_all_ch(range(DAC_global_min, 1024, 1), discri_list=discri_list)

                for discri in discri_list:
                    dac_calib_dict = {ch: df_calib_discri[i].loc[IbCalibDAC_selection,'T%d_calibDAC'%discri].iloc[ch] for ch in range(64)}
                    df0['T%d_calibDAC'%discri] = df0.channel.map(dac_calib_dict)
                df0['IbCalibDAC'] = IbCalibDAC
                df0['iter'] = i

                df = pd.concat([df, df0], ignore_index=True)
                df.to_csv(file_scurve, index=False)

                tmp = analyse_scurve(df0, local_output_dir, figname, board, discri_list=discri_list)

                selection = (df_calib_discri[i].IbCalibDAC==IbCalibDAC)
                for discri in discri_list:
                    df_calib_discri[i].loc[selection, 'T%d_after_calib'%discri] = np.round(tmp[discri-1],1)
                    df_calib_discri[i].loc[selection, 'T%d_noise_after_calib'%discri] = np.round(tmp[2][discri-1],1)

                df_calib_discri[i].to_csv(file_calib_discri[i], index=False)

        # the last iteration is the best aligned a priori
        df_calib_discri = df_calib_discri[-1]


        # # PLOT AVG NOISE
        # plt.figure(1, figsize=(13, 7))
        # for i, discri in enumerate(discri_list):
        #     plt.errorbar(range(64), y=(noise_min_calibDAC[i] + noise_max_calibDAC[i] + noise_after_calib[i]) / 3,
        #                  yerr=np.vstack((noise_min_calibDAC[i], noise_max_calibDAC[i], noise_after_calib[i])).std(axis=0), label=discri)
        #
        # plt.title(("B%d" % board) + " Noise from scurve fit computed from 3 measurements")
        # plt.grid(visible=True)
        # plt.xlabel("Channel")
        # plt.ylabel("Noise [global dac unit]")
        # plt.tight_layout()
        # plt.legend()
        # plt.savefig(save_folder + "noise_from_scurve.png")
        # # plt.show()
        # plt.close()
        #
        # plt.figure(0)
        # plt.close()

    # PLOT ALIGNED THRESHOLD
    plt.figure(1, figsize=(13, 7))
    plt.figure(3, figsize=(13, 7))
    plt.figure(4, figsize=(13, 7))

    ls_list=['solid', 'dashed']
    # colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    colors = plt.get_cmap("tab10")

    for i,discri in enumerate(['T1', 'T2']):
        for ci, IbCalibDAC in enumerate(IbCalibDAC_list):
            IbCalibDAC_selection = (df_calib_discri.IbCalibDAC == IbCalibDAC)
            local_df_calib_discri = df_calib_discri.loc[IbCalibDAC_selection,:].sort_values("channel")
            IbCalibDAC_selection_dac_ratio = (df_DAC_ratio.IbCalibDAC == IbCalibDAC)
            local_df_DAC_ratio = df_DAC_ratio.loc[IbCalibDAC_selection_dac_ratio,:].sort_values("channel")

            plt.figure(0, figsize=(13, 7))
            plt.plot(local_df_calib_discri['channel'], local_df_calib_discri[discri+'_calibDAC'], marker='o')
            plt.xlabel('Channel')
            plt.ylabel('calib_DAC_local')
            plt.ylim([-2, 65])
            plt.title(f'Calibration for local threshold DAC for {discri} discriminator, IbCalibDAC {IbCalibDAC}')
            plt.grid()
            plt.tight_layout()
            plt.savefig(local_output_dir + f"IbCalibDAC_{IbCalibDAC}_calib_DAC_local_{discri}.png")
            plt.close()

            plt.figure(1)
            y = local_df_calib_discri[discri+'_after_calib']
            plt.scatter(local_df_calib_discri['channel'], y, marker='.',
                        ls=ls_list[i], color=colors(ci%10),
                        label=discri+' | IbCalibDAC %d | std %.1f'%(IbCalibDAC, np.std(y)))

            plt.figure(2, figsize=(13, 7))
            plt.fill_between(local_df_DAC_ratio['channel'], local_df_DAC_ratio[discri+'_calibDac_0'],
                                 local_df_DAC_ratio[discri+'_calibDac_63'], color='gold', label='Correction range')

            # plt.fill_between(local_df_calib_discri['channel'], local_df_DAC_ratio[discri+'_efficiency_50_calibDacTL_0'],
            #                      local_df_calib_discri['Tx_calibDAC_min'], color='gold', alpha=0.5, label='Extrapolated correction range')

            plt.plot(local_df_calib_discri['channel'], local_df_calib_discri[discri+'_expected'], marker='o', label='Expected thresholds')
            plt.plot(local_df_calib_discri['channel'], local_df_calib_discri[discri+'_after_calib'], marker='o', label='Measured thresholds')
            plt.xlabel('Channel')
            plt.ylabel('Global thresholds [dac]')
            plt.title(f'Thresholds for {discri} discriminator')
            plt.legend()
            plt.grid()
            plt.tight_layout()
            plt.savefig(local_output_dir + f"IbCalibDAC_{IbCalibDAC}_{discri}_thresholds.png")
            # plt.show()
            plt.close()

            plt.figure(3)
            plt.plot(local_df_calib_discri['channel'], local_df_calib_discri[discri+'_calibDAC'], marker='.', label='IbCalibDAC %d'%IbCalibDAC)

            plt.figure(4)
            plt.plot(local_df_calib_discri['channel'], local_df_calib_discri[discri+'_noise_after_calib'], marker='.', label='IbCalibDAC %d'%IbCalibDAC)


        plt.figure(3)
        plt.xlabel('Channel')
        plt.ylabel('calib_DAC_local [dac]')
        plt.ylim([-2, 65])
        plt.title(f'Calibration for local threshold DAC for {discri} discriminator')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_dir + f"{discri}_calibDAC_vs_channel_vs_ibCalibDAC.png")
        plt.close()

        plt.figure(4)
        plt.xlabel('Channel')
        plt.ylabel('Noise [dac]')
        plt.title(f'Noise for {discri} discriminator')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_dir + f"{discri}_noise_vs_channel_vs_ibCalibDAC.png")
        plt.close()

    plt.figure(1)
    plt.xlabel('Channel')
    plt.ylabel('Global thresholds [dac]')
    plt.title(f'Measured channel-wise aligned threshold')
    plt.grid()
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    plt.savefig(local_output_dir + f"aligned_threshold_vs_IbCalibDAC.png")
    plt.close()


    calib_TL_file = '../config/TEMPOROC/B%d_calib_TL.csv' % tempo.board
    print("File should be saved to %s !"%calib_TL_file)




def align_thresholds_with_scurve_align(tempo, config, display=True, just_rerun_analysis=False):
    gain_list = ['TL', 'TH']
    # scurves are to be done with a signal injection simultaneously of a given charge
    # scurve should not be performed without charge injection to detect the pedestal
    # pedestals should be aligned not on the envelopp but on the baseline (middle between the 2 pedestals)
    start = time.perf_counter()

    # FIND DAC ratio dac10b/dac6b by sweeping THRESHOLDS

    board = tempo.board
    if not just_rerun_analysis:
        tempo.setup_scurve_all_ch(gain_list)
        IbCalibDAC = tempo.asic.bias.calibDac.Ib.get()
        print("Configuration: IbCalibDAC = %d" % IbCalibDAC)
    else:
        IbCalibDAC = 7
    # print("ib_calibDAC should be 7 ", (tempo.dev.i2c.read_register(64, 2) & 0xf0) >> 4)
    # print("ib_calibDAC should be 7 ", (tempo.dev.i2c.read_register(64, 2) & 0xf0) >> 4)
    # print("ib_calibDAC should be 7 ", (tempo.dev.i2c.read_register(64, 2) & 0xf0) >> 4)

    df = pd.DataFrame()
    save_folder = config['save_folder'] + '../scurve/'
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    file_scurve = save_folder+"B%d_trigger_effiency_threshold_scan.csv" %board
    file_calib_discri = save_folder+"B%d_calib_discri.csv" % board
    file_DAC_ratio = save_folder+"B%d_DAC_ratio.csv"%board #../config/TEMPOROC/


    need_to_do_DAC_ratio = True
    if os.path.exists(file_DAC_ratio):
        df_DAC_ratio = pd.read_csv(file_DAC_ratio)
        # print("Using recorded data for IbCalibDAC = %d to estimate TL_DAC_ratio = DAC global / DAC local"%IbCalibDAC)
        df_DAC_ratio = df_DAC_ratio[df_DAC_ratio.IbCalibDAC==IbCalibDAC]
        min_DAC_ratio = min(df_DAC_ratio.TH_DAC_ratio.min(), df_DAC_ratio.TL_DAC_ratio.min())
        max_DAC_ratio = max(df_DAC_ratio.TH_DAC_ratio.max(), df_DAC_ratio.TL_DAC_ratio.max())
        # if len(df_DAC_ratio) > 0:
        need_to_do_DAC_ratio = False
    else:
        min_DAC_ratio = 0.5  # with Ib_CALIB_DAC = 7
        max_DAC_ratio = 0.8  # with Ib_CALIB_DAC = 7


    # DAC LOCAL to MIN
    calibDacLocal_min = 0
    need_to_do_DacLocal_min = True
    if os.path.exists(file_scurve):
        df = pd.read_csv(file_scurve)
        if (calibDacLocal_min in df['calibDacTL']) and (calibDacLocal_min in df['calibDacTH']):
            need_to_do_DacLocal_min = False

    # MIN with coarse step
    print("calibDAC=min. Sweeping with coarse step. ", end='')
    acquisition_time_ns0 = 50
    figname0 = "0_dacLocal_%s" % calibDacLocal_min

    if need_to_do_DacLocal_min:
        tempo.asic.ch.all().set.calibDACT1(calibDacLocal_min)
        tempo.asic.ch.all().set.calibDACT2(calibDacLocal_min)
        time.sleep(0.1)
        df0 = tempo.get_scurve_all_ch(range(0, 1023, 10), acquisition_time_ns=acquisition_time_ns0)  # large step
        df0['calibDacTL'] = calibDacLocal_min
        df0['calibDacTH'] = calibDacLocal_min
        df0['step'] = 0
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_scurve, index=False)

    else:
        print("Recovering previous result.")
        df0 = df.loc[(df['calibDacTL']==calibDacLocal_min) & (df['acquisition_time_ns']==acquisition_time_ns0)]

    (global_dac_min, global_dac_max,
     local_thresh_in_global_dacu_for_each_gain,
     channel_to_ignore_for_each_gain) = analyse_poor_granularity_scurve(df0, save_folder, figname0,
                                                                        board, gain_list)

    # MIN with small step
    print("calibDAC=min. Sweeping with fine step. ", end='')
    acquisition_time_ns = 100  # default
    figname = "1_dacLocal_%s" % calibDacLocal_min
    if need_to_do_DacLocal_min:
        df0 = tempo.get_scurve_all_ch(range(global_dac_min, global_dac_max, 1))
        df0['calibDacTL'] = calibDacLocal_min
        df0['calibDacTH'] = calibDacLocal_min
        df0['step'] = 1
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_scurve, index=False)
        # print("Found fine threshold position for all channels to estimate DAC calib ratio for IbCalibDAC = %d" % IbCalibDAC)

    else:
        print("Recovering previous result.")
        df0 = df.loc[(df['calibDacTH']==calibDacLocal_min) & (df['calibDacTL']==calibDacLocal_min) & (df['acquisition_time_ns']==acquisition_time_ns)]
    #      & (df['TL_thres_dac']>=global_dac_min) & (df['TL_thres_dac']<global_dac_max)

    TL_efficiency_50_min_calibDAC, TH_efficiency_50_min_calibDAC, noise_min_calibDAC = analyse_scurve(df0, save_folder, figname, board,
                                                                                                      channel_to_ignore_for_each_gain=channel_to_ignore_for_each_gain, discri_list=gain_list)

    # MAX with small step
    print("calibDAC=max. Sweeping with fine step. ", end='')
    need_to_do_DacLocal_max = True
    calibDacLocal_max = 63
    figname = "2_dacLocal_%s" % calibDacLocal_max
    if os.path.exists(file_scurve):
        df = pd.read_csv(file_scurve)
        df0 = df.loc[(df['calibDacTH'] == calibDacLocal_max)
                     & (df['calibDacTL'] == calibDacLocal_max)
                     & (df['acquisition_time_ns'] == acquisition_time_ns)]
        if len(df0)>0:
            need_to_do_DacLocal_max = False
            print("Recovering previous result")

    if need_to_do_DacLocal_max:
        tempo.asic.ch.all().set.calibDACT1(calibDacLocal_max)
        tempo.asic.ch.all().set.calibDACT2(calibDacLocal_max)
        # print("calibDacTL should be 32 ", tempo.dev.i2c.read_register(0, 5))
        time.sleep(0.1)
        min_expected_offset = + int(calibDacLocal_max * min_DAC_ratio)
        max_expected_offset = + int(calibDacLocal_max * max_DAC_ratio)
        # df0 = tempo.get_scurve_all_ch(range(global_dac_min + min_expected_offset, global_dac_max + max_expected_offset, 1))
        df0 = tempo.get_scurve_all_ch(range(global_dac_min + min_expected_offset, 1023, 1))
        df0['calibDacTL'] = calibDacLocal_max
        df0['calibDacTH'] = calibDacLocal_max
        df0['step'] = 2
        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_scurve, index=False)
        # print("Found fine threshold position for all channels")

    TL_efficiency_50_max_calibDAC, TH_efficiency_50_max_calibDAC, noise_max_calibDAC = analyse_scurve(df0, save_folder, figname, board, channel_to_ignore_for_each_gain=channel_to_ignore_for_each_gain, discri_list=gain_list)

    if need_to_do_DAC_ratio:

        # COMPUTE TL_DAC_ratio = 10b_DAC_global / 6b_DAC_local
        DAC_ratio_per_ch_for_one_IbCalibDAC = {}
        DAC_ratio_per_ch_for_one_IbCalibDAC['channel'] = list(range(64))
        DAC_ratio_per_ch_for_one_IbCalibDAC['IbCalibDAC'] = [IbCalibDAC] * 64

        plt.figure(figsize=(13, 7))

        # default
        TL_DAC_ratio = [min_DAC_ratio]*64
        TH_DAC_ratio = [min_DAC_ratio]*64

        if 'TL' in gain_list:
            TL_DAC_ratio = (np.array(TL_efficiency_50_max_calibDAC) - np.array(TL_efficiency_50_min_calibDAC)) / (calibDacLocal_max-calibDacLocal_min)
            DAC_ratio_per_ch_for_one_IbCalibDAC['TL_efficiency_50_calibDac_0'] = TL_efficiency_50_min_calibDAC
            DAC_ratio_per_ch_for_one_IbCalibDAC['TL_efficiency_50_calibDac_63'] = TL_efficiency_50_max_calibDAC
            DAC_ratio_per_ch_for_one_IbCalibDAC['TL_DAC_ratio'] = list(TL_DAC_ratio)
            plt.plot(TL_DAC_ratio, label='TL')

        if 'TH' in gain_list:
            TH_DAC_ratio = (np.array(TH_efficiency_50_max_calibDAC) - np.array(TH_efficiency_50_min_calibDAC)) / (calibDacLocal_max - calibDacLocal_min)
            DAC_ratio_per_ch_for_one_IbCalibDAC['TH_efficiency_50_calibDac_0'] = TH_efficiency_50_min_calibDAC
            DAC_ratio_per_ch_for_one_IbCalibDAC['TH_efficiency_50_calibDac_63'] = TH_efficiency_50_max_calibDAC
            DAC_ratio_per_ch_for_one_IbCalibDAC['TH_DAC_ratio'] = list(TH_DAC_ratio)

            plt.plot(TH_DAC_ratio, label='TH')

        df_DACratio = pd.DataFrame(DAC_ratio_per_ch_for_one_IbCalibDAC)
        df_DACratio.to_csv(config['save_folder']+"B%d_DAC_ratio.csv"%board, index=False)

        plt.xlabel('Channel')
        plt.ylabel('DAC_ratio')
        plt.legend()
        plt.grid()
        plt.tight_layout()
        plt.savefig(save_folder + "DAC_CALIB_ratio.png")
        plt.close()

        print("DAC ratio computed.")
    else:
        TL_DAC_ratio = df_DAC_ratio.TL_DAC_ratio
        TH_DAC_ratio = df_DAC_ratio.TH_DAC_ratio


    # CHANNEL-WISE threshold DAC calibration
    figname = "3_dacLocal_channelwise"
    acquisition_time_ns = 110
    if not os.path.exists(file_calib_discri):

        # COMPUTE CALIB_6b_DAC CHANNEL-WISE calibration value
        dac_calib_half_range = 32
        res = {'channel': range(64)}

        if 'TL' in gain_list:
            median_TL_global_threshold = np.median(TL_efficiency_50_max_calibDAC)
            TL_dac_calib = dac_calib_half_range - ((np.array(TL_efficiency_50_max_calibDAC) - median_TL_global_threshold) / TL_DAC_ratio)
            TL_dac_calib = np.int32(np.nan_to_num(TL_dac_calib, nan= 0))
            TL_dac_calib = np.clip(TL_dac_calib, 0, 63)  # saturate
            TL_expected_DAC_global = TL_efficiency_50_max_calibDAC + (TL_dac_calib - calibDacLocal_max) * TL_DAC_ratio
            res.update({
                'TL_DAC_ratio': TL_DAC_ratio,
                'TL_calib_DAC_local': TL_dac_calib,
                'TL_expected_DAC_global': TL_expected_DAC_global})

        if 'TH' in gain_list:
            median_TH_global_threshold = np.nanmedian(TH_efficiency_50_max_calibDAC)
            try:
                TH_dac_calib = dac_calib_half_range - ((np.array(TH_efficiency_50_max_calibDAC) - median_TH_global_threshold) / TH_DAC_ratio)
                TH_dac_calib = np.int32(np.nan_to_num(TH_dac_calib, nan=0))
            except RuntimeWarning:
                pass

            TH_dac_calib = np.clip(TH_dac_calib, 0, 63)  # saturate
            TH_expected_DAC_global = TH_efficiency_50_max_calibDAC + (TH_dac_calib - calibDacLocal_max) * TH_DAC_ratio

            res.update({'TH_DAC_ratio': TH_DAC_ratio,
                        'TH_calib_DAC_local': TH_dac_calib,
                        'TH_expected_DAC_global': TH_expected_DAC_global
                        })

        df_calib_discri = pd.DataFrame(res)

        print("calibDAC=channel-wise correction. Sweeping with fine step to check alignment. ", end='')
        # ALIGN THRESHOLDS
        for channel in range(64):
            if 'TL' in gain_list:
                dac_calib_value = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'TL_calib_DAC_local'].iloc[0])
                tempo.asic.ch(channel).set.calibDACT1(dac_calib_value)
                tempo.asic.ch(channel).set.calibDACT2(dac_calib_value)
            if 'TH' in gain_list:
                dac_calib_value = int(df_calib_discri.loc[df_calib_discri.channel == channel, 'TH_calib_DAC_local'].iloc[0])
                tempo.asic.ch(channel).set.calibDACT2(dac_calib_value)

        # VERIFY THRESHOLD CALIBRATION
        if 'TL' in gain_list:
            DAC_global_min = int(df_calib_discri['TL_expected_DAC_global'].min())
        if 'TH' in gain_list:
            DAC_global_min = int(df_calib_discri['TH_expected_DAC_global'].min())
        if ('TL' in gain_list) and ('TH' in gain_list):
            DAC_global_min = int(min(int(df_calib_discri['TL_expected_DAC_global'].min()), df_calib_discri['TH_expected_DAC_global'].min()))

        # DAC_global_max = max(int(df_calib_discri['TL_expected_DAC_global'].max()), df_calib_discri['TH_expected_DAC_global'].max())
        DAC_global_max = 1023

        if (DAC_global_min - 10) < 0 :
            pass
        df0 = tempo.get_scurve_all_ch(range(DAC_global_min - 10, DAC_global_max + 5, 1))


        if 'TL' in gain_list:
            dac_calib_dict = {ch: df_calib_discri['TL_calib_DAC_local'][ch] for ch in range(64)}
            df0['calibDacTL'] = df0.channel.map(dac_calib_dict)
        if 'TH' in gain_list:
            dac_calib_dict = {ch: df_calib_discri['TH_calib_DAC_local'][ch] for ch in range(64)}
            df0['calibDacTH'] = df0.channel.map(dac_calib_dict)
        df0['step'] = 3

        df = pd.concat([df, df0], ignore_index=True)
        df.to_csv(file_scurve, index=False)

    else:
        df = pd.read_csv(file_scurve)
        # last_line = df.loc[(df['calibDacTH']==calibDacLocal_max) & (df['calibDacTL']==calibDacLocal_max) & (df['acquisition_time_ns']==acquisition_time_ns)].index[-1]
        # df0 = df.iloc[last_line+1:, :]
        df0 = df.loc[df['acquisition_time_ns']==acquisition_time_ns, :]

    TL_efficiency_50_after_calib, TH_efficiency_50_after_calib, noise_after_calib = analyse_scurve(df0, save_folder, figname, board, channel_to_ignore_for_each_gain=channel_to_ignore_for_each_gain, discri_list=gain_list)

    if not os.path.exists(file_calib_discri):
        if 'TL' in gain_list:
            df_calib_discri['TL_efficiency_50_after_calib'] = TL_efficiency_50_after_calib
        if 'TH' in gain_list:
            df_calib_discri['TH_efficiency_50_after_calib'] = TH_efficiency_50_after_calib
        df_calib_discri.to_csv(file_calib_discri, index=False)
    else:
        df_calib_discri = pd.read_csv(file_calib_discri)

    print("End aligning thresholds with scurve. Elapsed time : %d seconds" % (time.perf_counter() - start))


    # PLOT AVG NOISE
    plt.figure(1, figsize=(13, 7))
    for i, gain in enumerate(gain_list):
        plt.errorbar(range(64), y=(noise_min_calibDAC[i] + noise_max_calibDAC[i] + noise_after_calib[i]) / 3,
                     yerr=np.vstack((noise_min_calibDAC[i], noise_max_calibDAC[i], noise_after_calib[i])).std(axis=0), label=gain)

    plt.title(("B%d" % board) + " Noise from scurve fit computed from 3 measurements")
    plt.grid(visible=True)
    plt.xlabel("Channel")
    plt.ylabel("Noise [global dac unit]")
    plt.tight_layout()
    plt.legend()
    plt.savefig(save_folder + "noise_from_scurve.png")
    # plt.show()
    plt.close()

    plt.figure(0)
    plt.close()

    # PLOT ALIGNED THRESHOLD
    for gain in gain_list:
        plt.figure(figsize=(13, 7))
        plt.plot(df_calib_discri[gain+'_calib_DAC_local'], marker='o')
        plt.xlabel('Channel')
        plt.ylabel('calib_DAC_local')
        plt.ylim([-2, 65])
        plt.title(f'Calibration for local threshold DAC for {gain} discriminator')
        plt.grid()
        plt.tight_layout()
        plt.savefig(save_folder + f"calib_DAC_local_{gain}.png")

        plt.figure(figsize=(13, 7))
        if need_to_do_DAC_ratio:
            plt.fill_between(range(64), eval(gain+'_efficiency_50_min_calibDAC'),
                             eval(gain+'_efficiency_50_max_calibDAC'), color='gold', label='Correction range')
        else:
            plt.fill_between(range(64), df_DAC_ratio[gain+'_efficiency_50_calibDacTL_0'],
                             df_DAC_ratio[gain+'_efficiency_50_calibDacTL_63'], color='gold', label='Correction range')
        plt.plot(range(64), df_calib_discri[gain+'_expected_DAC_global'], marker='o', label='Expected thresholds')
        plt.plot(range(64), eval(gain+'_efficiency_50_after_calib'), marker='o', label='Measured thresholds')
        plt.xlabel('Channel')
        plt.ylabel('Global thresholds [dac]')
        plt.title(f'Thresholds for {gain} discriminator')
        plt.legend()
        plt.grid()
        plt.tight_layout()
        plt.savefig(save_folder + gain+ "_thresholds.png")
        if display:
            plt.show()
        plt.close()


    calib_TL_file = '../config/TEMPOROC/B%d_calib_TL.csv' % tempo.board
    print("File should be saved to %s !"%calib_TL_file)

    return TL_efficiency_50_after_calib, TH_efficiency_50_after_calib





def align_thresholds_with_staircase(tempo, config, injected_channels_ASIC, discri_list=['TL', 'TH']):

    plot_folder = config['save_folder'] + '../threshold_scan/'
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)

    hv = setup_hv(config, serial_number=list(config['CAEN_serial_number_to_board'].keys())[
        list(config['CAEN_serial_number_to_board'].values()).index(config['board'][0])])
    hv.set_enHV(0)
    time.sleep(1)
    print(measure_SiPM_HV(hv, config))
    time.sleep(1)
    print(measure_SiPM_HV(hv, config))

    # Count triggers with NOR latched trigger
    tempo.asic.interface.en.Nor_TrigT_L_RS()
    tempo.asic.interface.en.Nor_TrigT_H_RS()

    print("Keeping Temporoc's digital ON")
    tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.pll.select_PLL_as_clock_source()
    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.resetn_digital_ASIC(1)

    print('Enabling NOR pad, unlatching trigger, bypassing Temporoc own reset, disabling pd hold')
    tempo.asic.common.dis.tpr_latch()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.bypassResetMgmt()
    tempo.fpga.fpga.reset.latch_ASIC(1)
    tempo.asic.interface.select.global_trigger.ground()

    dac_calib_half_range = 32
    tempo.asic.ch.all().set.calibDACT1(dac_calib_half_range)
    tempo.asic.ch.all().set.calibDACT2(dac_calib_half_range)

    if 'TL' in discri_list:
        apriori_aligned_TL = 210
        TL_list = thres_range(apriori_aligned_TL, 60, 1)
    else:
        TL_list = None

    if 'TH' in discri_list:
        apriori_aligned_TH = 170
        TH_list = thres_range(apriori_aligned_TH, 60, 1)
    else:
        TH_list = None

    tempo.asic.ch.all().disable.all_discri()
    thres_scan_df_filename = config['save_folder'] + "B%d_trigger_counting_threshold_scan.csv" % (config['board'][0])
    if config['step']<0:
        thres_scan_df = pd.DataFrame()

        for channel in injected_channels_ASIC:
            tempo.asic.ch(channel).enable.TL()
            tempo.asic.ch(channel).enable.TH()
            # time.sleep(0.01)
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, TH_list)
            df_tmp['aligned'] = 0
            df_tmp['dac_calib'] = dac_calib_half_range
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(thres_scan_df_filename, index=False)
            tempo.asic.ch(channel).disable.TL()
            tempo.asic.ch(channel).disable.TH()
        config['step']=0
    else:
        thres_scan_df = pd.read_csv(thres_scan_df_filename)



    file_DAC_ratio = "../config/TEMPOROC/B%d_DAC_ratio.csv" % 2

    df_DAC_ratio = pd.read_csv(file_DAC_ratio)
    IbCalibDAC = tempo.asic.bias.calibDac.Ib.get()
    print("Using recorded data for IbCalibDAC = %d to estimate DAC_ratio = DAC global / DAC local" % IbCalibDAC)
    df_DAC_ratio = df_DAC_ratio[df_DAC_ratio.IbCalibDAC == IbCalibDAC]

    if 'TL' in discri_list:
        print("Applying discri calibDAC correction for TL")
        pedestal = thres_scan_df[thres_scan_df.aligned == 0].dropna(subset=['TL_dac', 'TL_freq']).pivot(columns='channel', index='TL_dac', values='TL_freq').idxmax()
        DAC_ratio = df_DAC_ratio[df_DAC_ratio.channel.isin(pedestal.index)].DAC_ratio

        dac_calib_TL = np.int32(dac_calib_half_range - ((pedestal.values - pedestal.mean()) / DAC_ratio))
        dac_calib_TL = np.clip(dac_calib_TL, 0, 63)  # saturate
        print(dac_calib_TL)

        for ci, channel in enumerate(injected_channels_ASIC):
            tempo.asic.ch(channel).set.calibDACT1(int(dac_calib_TL[ci]))

    if 'TH' in discri_list:
        print("Applying discri calibDAC correction for TH")
        pedestal = thres_scan_df[thres_scan_df.aligned == 0].dropna(subset=['TH_dac', 'TH_freq']).pivot(columns='channel', index='TH_dac', values='TH_freq').idxmax()
        DAC_ratio = df_DAC_ratio[df_DAC_ratio.channel.isin(pedestal.index)].DAC_ratio

        dac_calib_TH = np.int32(dac_calib_half_range - ((pedestal.values - pedestal.mean()) / DAC_ratio))
        dac_calib_TH = np.clip(dac_calib_TH, 0, 63)  # saturate
        print(dac_calib_TH)

        for ci, channel in enumerate(injected_channels_ASIC):
            tempo.asic.ch(channel).set.calibDACT2(int(dac_calib_TH[ci]))



    if config['step'] < 1:
        for ci, channel in enumerate(injected_channels_ASIC):
            tempo.asic.ch(channel).enable.TL()
            tempo.asic.ch(channel).enable.TH()
            # time.sleep(0.01)
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, TH_list)
            df_tmp['aligned'] = 1
            if 'TL' in discri_list:
                df_tmp['dac_calib_TL'] = dac_calib_TL[ci]
            if 'TH' in discri_list:
                df_tmp['dac_calib_TH'] = dac_calib_TH[ci]
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(thres_scan_df_filename, index=False)
            tempo.asic.ch(channel).disable.TL()
            tempo.asic.ch(channel).disable.TH()
        config['step'] = 1
    else:
        thres_scan_df = pd.read_csv(thres_scan_df_filename)



    expected_aligned_pedestal_TL = (thres_scan_df[thres_scan_df.aligned == 1].dropna(subset=['TL_dac', 'TL_freq'])
                                    .pivot(columns='channel', index='TL_dac', values='TL_freq').idxmax().values)

    expected_aligned_pedestal_TH = (thres_scan_df[thres_scan_df.aligned == 1].dropna(subset=['TH_dac', 'TH_freq'])
                                    .pivot(columns='channel', index='TH_dac', values='TH_freq').idxmax().values)

    file_calib_discri = config['save_folder'] + "B%d_calib_discri_staircase.csv" % 2
    df_calib_discri = pd.DataFrame({'channel': injected_channels_ASIC, 'DAC_ratio': DAC_ratio,
                                    'calib_DAC_local_TL': dac_calib_TL,
                                    'expected_aligned_pedestal_TL': expected_aligned_pedestal_TL,
                                    'calib_DAC_local_TH': dac_calib_TH,
                                    'expected_aligned_pedestal_TH': expected_aligned_pedestal_TH})

    df_calib_discri.to_csv(file_calib_discri, index=False)



    print("Bonus : Biasing SiPm to breakdown to check effect on pedestal ")
    hv.set_voltage_modulating_ramp(config['SiPM_breakdown'][config['SiPM_model']], config['SiPM_breakdown'][config['SiPM_model']])
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))

    if config['step'] < 2:
        for ci, channel in enumerate(injected_channels_ASIC):
            tempo.asic.ch(channel).enable.TL()
            tempo.asic.ch(channel).enable.TH()
            # time.sleep(0.01)
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, TH_list)
            df_tmp['aligned'] = 2
            if 'TL' in discri_list:
                df_tmp['dac_calib_TL'] = dac_calib_TL[ci]
            if 'TH' in discri_list:
                df_tmp['dac_calib_TH'] = dac_calib_TH[ci]
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(thres_scan_df_filename, index=False)
            tempo.asic.ch(channel).disable.TL()
            tempo.asic.ch(channel).disable.TH()
        config['step'] = 2
    else:
        thres_scan_df = pd.read_csv(thres_scan_df_filename)


    print("Disabling Temporoc's digital to check effect on pedestal ")
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.pll.fpga.set.FPGA_as_clock_source()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.off()
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.fpga.resetn_digital_ASIC(0)

    if config['step'] < 3:
        for ci, channel in enumerate(injected_channels_ASIC):
            tempo.asic.ch(channel).enable.TL()
            tempo.asic.ch(channel).enable.TH()
            # time.sleep(0.01)
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, TH_list)
            df_tmp['aligned'] = 3
            if 'TL' in discri_list:
                df_tmp['dac_calib_TL'] = dac_calib_TL[ci]
            if 'TH' in discri_list:
                df_tmp['dac_calib_TH'] = dac_calib_TH[ci]
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(thres_scan_df_filename, index=False)
            tempo.asic.ch(channel).disable.TL()
            tempo.asic.ch(channel).disable.TH()
        config['step'] = 3
    else:
        thres_scan_df = pd.read_csv(thres_scan_df_filename)

    hv.close()
    save_config_file(config)

    # PLOT

    # CHANNEL per CHANNEL
    for channel in injected_channels_ASIC:
        for discri in discri_list:
            plt.figure(figsize=(14, 8))
            for step in np.unique(thres_scan_df.aligned):
                not_nan_selection = ~(thres_scan_df.loc[:, discri + '_dac'].isna())
                selection = (thres_scan_df.aligned == step) & (thres_scan_df.channel==channel) & not_nan_selection

                thres_dac = thres_scan_df.loc[selection, discri + '_dac']
                counts = thres_scan_df.loc[selection, discri + '_freq']
                calib_DAC_local = df_calib_discri.loc[df_calib_discri.channel == channel, 'calib_DAC_local_' + discri].iloc[0]
                if step==0:
                    label='HV off - DIG on - calibDAC 32'
                if step==1:
                    label='HV off - DIG on - aligned (calibDac = %d)'%calib_DAC_local
                if step==2:
                    label='HV %.1f (breakdown) - DIG on - aligned (calibDac = %d)'%(config['SiPM_breakdown'][config['SiPM_model']], calib_DAC_local)
                if step==3:
                    label='HV %.1f (breakdown) - DIG off - aligned (calibDac = %d)'%(config['SiPM_breakdown'][config['SiPM_model']], calib_DAC_local)

                plt.plot(thres_dac, counts, label=label, marker='o')

            pedestal = df_calib_discri.loc[df_calib_discri.channel==channel, 'expected_aligned_pedestal_'+discri].iloc[0]
            plt.axvline(x=pedestal, color='r', linestyle='--', label='Pedestal %d'%pedestal)
            plt.grid()
            plt.legend()
            plt.yscale('log')
            plt.xlabel('Global threshold [dac]')
            plt.ylabel('Trigger frequency')
            plt.title('Channel %d - ' % channel+discri+' discriminator')
            plt.xlim([pedestal-5, pedestal+5])
            plt.tight_layout()
            plt.savefig(plot_folder + 'ch%d_%s_trigger_frequency_vs_threshold.png'%(channel, discri))
            # plt.autoscale()

        plt.show()

    # ALL CHANNELs
    for discri in discri_list:
        plt.figure(figsize=(14, 8))
        thres_scan_df = thres_scan_df[thres_scan_df.aligned == 1]
        not_nan_selection = ~(thres_scan_df.loc[:, discri + '_dac'].isna())
        ax_list = []
        for channel in config['enable_TL_ASIC_ch'][0]:
            selection = thres_scan_df.channel == channel
            thres_dac = thres_scan_df.loc[selection & not_nan_selection, discri + '_dac']
            counts = thres_scan_df.loc[selection & not_nan_selection, discri + '_freq']
            ax = plt.plot(thres_dac, counts, label='ch%d HV OFF' % channel, linestyle='--')
            ax_list.append(ax)

        pedestal = np.mean(df_calib_discri['expected_aligned_pedestal_'+discri])
        plt.axvline(x=pedestal, color='r', linestyle='--', label=discri +' aligned value')
        plt.grid()
        plt.legend()
        plt.yscale('log')
        plt.xlabel('Global threshold [dac]')
        plt.ylabel('Trigger frequency')
        plt.title("Aligned pedestals")
        plt.tight_layout()
        plt.savefig(plot_folder + discri+'_trigger_frequency_vs_threshold.png')


    plt.figure(figsize=(14, 8))
    plt.plot(df_calib_discri.channel, df_calib_discri.expected_aligned_pedestal_TL, label='aligned TL')
    plt.plot(df_calib_discri.channel, df_calib_discri.expected_aligned_pedestal_TH, label='aligned TH')
    plt.axhline(x=np.mean(TL_pedestal), color='tab:blue', linestyle='--', label='TL aligned value')
    plt.axhline(x=np.mean(TH_pedestal), color='tab:orange', linestyle='--', label='TH aligned value')
    plt.grid()
    plt.legend()
    plt.xlabel('Channel')
    plt.ylabel('Discriminator pedestal')
    plt.title("Pedestals after alignment")
    plt.tight_layout()
    plt.savefig(plot_folder + 'aligned_pedestal_vs_channel.png')


    plt.show()


    return df_calib_discri

def find_slope_staircase(thres_scan_df, df_calib_discri, config, gain='TL', post_calib=False):
    slope_dict = {'channel':[]}


    for channel in config['enable_TL_ASIC_ch'][0]:

        # pedestal = df_calib_discri.loc[df_calib_discri.channel == channel, 'expected_aligned_pedestal'].iloc[0]
        pedestal = thres_scan_df.iloc[thres_scan_df.loc[(thres_scan_df.channel == channel), 'TL_freq'].idxmax()]['TL_dac']

        for i,inDAC in enumerate(np.unique(thres_scan_df.loc[thres_scan_df.channel == channel, 'inDAC'])):

            if post_calib:
                suffix = '_inDAC_post_calib'
            else:
                suffix = '_inDAC_%d' % inDAC

            selection = ((thres_scan_df.channel == channel) & (thres_scan_df.inDAC==inDAC)
                         & (thres_scan_df[gain + '_dac'] > pedestal)
                         & (thres_scan_df[gain + '_freq'] > 0)    # otherwise log issues
                         & (thres_scan_df[gain + '_dac'] != 256))  # abnormal value for dac = 256
            if sum(selection) < 20:
                continue
            thres_dac = thres_scan_df.loc[selection, gain + '_dac']
            counts = thres_scan_df.loc[selection & (thres_scan_df[gain + '_dac'] > pedestal), gain + '_freq']

            if 'slope'+suffix not in slope_dict:
                slope_dict['slope'+suffix] = []
                slope_dict['offset'+suffix] = []

            if len(counts) > 0:
                fitParam, cov = curve_fit(modelFitLinear, thres_dac, np.log(counts))
                offset = fitParam[1]
                slope = fitParam[0]

                slope_dict['slope'+suffix].append(slope)
                slope_dict['offset'+suffix].append(offset)
            else:
                slope_dict['slope'+suffix].append(np.nan)
                slope_dict['offset'+suffix].append(np.nan)

            if i==0:
                slope_dict['channel'].append(channel)

    # fill with default inDac value for not examinated or failed to examin channels
    for channel in set(slope_dict['channel']) ^ set(range(64)):
        slope_dict['channel'].append(channel)
        for keys in set(slope_dict.keys()) ^ {'channel'}:
            slope_dict[keys].append(np.nan)

    slope_df = pd.DataFrame(slope_dict)

    return slope_df


def setup_align_SiPM_gain_with_inDAC(tempo, config):

    # Setup tempo to output trigger to be counted
    gain = 'TL'
    tempo.fpga.select.trigger_mon.or_trig_l_rs()
    tempo.asic.interface.en.Nor_TrigT_L_RS()

    print("Disabling Temporoc's digital to enhance staircase quality ")
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    # tempo.clock.fpga.set.FPGA_as_clock_source()
    tempo.pll.select_PLL_as_clock_source()
    tempo.set_pll_rstb(0) # no need for clocks from the external PLL
    tempo.fpga.select.ck_from_FPGA_to_ASIC.off()
    tempo.fpga.set.ro_enable_ASIC(0)
    tempo.fpga.resetn_digital_ASIC(0)

    print('Enabling NOR pad, unlatching trigger, bypassing Temporoc own reset, disabling pd hold')
    tempo.asic.common.dis.tpr_latch()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.bypassResetMgmt()
    tempo.fpga.fpga.reset.latch_ASIC(1)
    tempo.asic.interface.select.global_trigger.ground()

    file_calib_discri = "../config/TEMPOROC/B%d_calib_TL_staircase.csv" % config['board'][0]
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

    config['aligned_discri_threshold'] = aligned_discri_threshold
    return df_calib_discri


def measure_align_SiPM_gain_with_inDAC(tempo, config, suffix=''):

    board = config['board'][0]
    # BIAS SIPM
    hv_voltage = config['target_hv_voltage']
    hv = setup_hv(config, serial_number = list(config['CAEN_serial_number_to_board'].keys())[list(config['CAEN_serial_number_to_board'].values()).index(board)])


    print("Measure pedestal : unbaising SiPM")
    hv.set_enHV(0)
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    pedestal_df = pd.DataFrame()
    pedestal_df_filename = config['save_folder'] + "B%d_trigger_counting_threshold_scan_pedestal%s.csv"%(board, suffix)
    TL_list = range(config['aligned_discri_threshold'] - 30,
                    config['aligned_discri_threshold'] + 100, 1)
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.ch.all().set.inDac(128)

    for channel in config['enable_TL_ASIC_ch'][0]:
        tempo.asic.ch(channel).enable.TL()
        df_tmp = tempo.common_threshold_scan(int(channel), TL_list, None, time_acq_window=10e-3)
        pedestal_df = pd.concat([pedestal_df, df_tmp])
        pedestal_df.to_csv(pedestal_df_filename, index=False)
        tempo.asic.ch(channel).disable.TL()

    
    print("Turning ON the HV : 22Na radioactive source should be REMOVED")
    hv.set_voltage_modulating_ramp(hv_voltage, config['SiPM_breakdown'][config['SiPM_model']])
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    time.sleep(2)
    print(measure_SiPM_HV(hv, config))
    print(save_periodically_SiPM_HV(hv, config))
    
    print("Sweeping global threshold and counting triggers for 2 extreme values of inDAC")
    thres_scan_df = pd.DataFrame()
    thres_scan_df_filename = config['save_folder'] + "B%d_trigger_counting_threshold_scan_HV_%.1f%s.csv" % (board, hv_voltage, suffix)

    tempo.asic.ch.all().disable.all_discri()
    for channel in config['enable_TL_ASIC_ch'][0]:
        for inDAC in [0, 255]:
            tempo.asic.ch.all().set.inDac(inDAC)
            tempo.asic.ch(channel).enable.TL()
            df_tmp = tempo.common_threshold_scan(int(channel), TL_list, None, time_acq_window=config['staircase_acq_time'])
            df_tmp['inDAC'] = inDAC
            thres_scan_df = pd.concat([thres_scan_df, df_tmp])
            thres_scan_df.to_csv(thres_scan_df_filename, index=False)
            tempo.asic.ch(channel).disable.TL()


    save_config_file(config)
    hv.close()

    return thres_scan_df, pedestal_df

def plot_all_channels_SiPM(df, config, label):
    plt.figure(figsize=(14, 8))
    if label=='biased_SiPM':
        for inDAC in np.unique(df.inDAC):
            for channel in config['enable_TL_ASIC_ch'][0]:
                selection = (df.channel == channel) & (df.inDAC == inDAC)
                plt.plot(df.loc[selection, 'TL_dac'], df.loc[selection, 'TL_freq'],
                         label='ch %d dac %d' % (channel, inDAC))
    elif label=='unbiased_SiPM':
        for channel in config['enable_TL_ASIC_ch'][0]:
            selection = (df.channel == channel)
            plt.plot(df.loc[selection, 'TL_dac'], df.loc[selection, 'TL_freq'],
                     label='ch %d' % channel)
    else:
        print("wrong label %s"%label)
        return
    plt.grid()
    plt.yscale('log')
    # plt.legend(ncols=4)
    plt.tight_layout()
    plt.savefig(config['plot_folder'] + 'staircase_all_channels_'+label+'.png')
    # plt.show()
    plt.close()

def plot_SiPM_non_uniformity(res_df, plot_folder):

    plt.figure(figsize=(10, 8))
    for inDAC in np.unique(res_df.inDAC):
        selection = (res_df.inDAC == inDAC)
        ax = plt.plot(res_df.loc[selection, 'channel'],
                      res_df.loc[selection, 'one_pe_dac'] - res_df.loc[selection, 'pedestal'],
                      label='inDAC %d' % inDAC)
        # ax = plt.plot(res_df.loc[selection, 'channel'],
        #               res_df.loc[selection, 'one_pe_dac'],
        #               label='inDAC %d' % inDAC)
        # plt.plot(res_df.loc[selection, 'channel'],
        #          res_df.loc[selection, 'one_pe_dac']-res_df.loc[selection, 'r1_dac'],
        #          label='inDAC %d'%inDAC,color=ax[0].get_color(), linestyle='--') #

    plt.grid()
    plt.title('1pe amplitude (difference with pedestal) for each channel')
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_folder + "SiPM_gain_non_uniformity.png")
    plt.show()


def find_1pe_amplitude(SiPM_biased_df, pedestal_df, output_folder):
    res = {'channel': [], 'inDAC': [],
           'pedestal': [], 'one_pe_dac': [], 'one_pe_freq': [], 'r1_dac': []}

    channel_folder = output_folder + 'channel/'
    if not os.path.exists(channel_folder):
        os.makedirs(channel_folder)

    for ch in np.unique(SiPM_biased_df.channel): #[28, 50, 56, 61, 62]: #
        plt.subplots(1, 1, figsize=(14, 8))
        # plt.subplots(2, 1, figsize=(14, 8), height_ratios=(3, 1), sharex=True)
        for inDAC in np.unique(SiPM_biased_df.inDAC):
            selection = (SiPM_biased_df.inDAC == inDAC) & (SiPM_biased_df.channel == ch)
            x = SiPM_biased_df.loc[selection, 'TL_dac'][5:]
            y = SiPM_biased_df.loc[selection, 'TL_freq'][5:]
            y_log = np.where(y.values > 0.1, y.values, -10) # remove warning log of 0
            y_log = np.log(y_log, where=(y_log > 0), out=np.zeros_like(y_log, dtype=np.float64))

            ax = plt.scatter(x, y, label='ch %d dac %d' % (ch, inDAC), marker='x')

            methodA=True
            methodAB=False
            if methodA:

                start = np.clip(y_log.argmax()-15, 0, 100)
                init_slice = slice(start, y_log.argmax() + 20, 1)
                diff = np.diff(y_log[init_slice])

                if (len(diff) == 0) | (len(np.unique(diff))==1):
                    continue

                if methodAB:
                    pedestal = pedestal_df.iloc[pedestal_df.loc[pedestal_df.channel==ch, 'TL_freq'].idxmax()].TL_dac
                    pedestal_index_for_x = np.where(x==pedestal)[0][0]
                else:
                    pedestal_index_for_diff = diff.argmax()+7
                    pedestal_index_for_x = start + pedestal_index_for_diff
                    pedestal = x.values[pedestal_index_for_x]

                diff = diff[15-start+(y_log.argmax()-15)+7:]
                one_pe_slice = slice(pedestal_index_for_x, pedestal_index_for_x + 15, 1)
                one_pe_dac = x[:-1].values[one_pe_slice][diff.argmin()]
                crossing_log = y_log[:-1][one_pe_slice][diff.argmin()]

                try:
                    p0_init = [pedestal+10, 1]
                    y_data = y_log[one_pe_slice].copy()
                    B = min(y_data)
                    y_data -= B
                    A = max(y_data)
                    y_data /= A

                    fit, cov = curve_fit(f=ScurveFit, xdata=x[one_pe_slice], ydata=y_data, p0=p0_init)

                    plt.plot(x[one_pe_slice], np.exp(ScurveFit(x[one_pe_slice], *fit)*A+B))
                except:
                    print("fit error")
            else:
                pedestal = x[y.idxmax()]
                diff = np.diff(y_log.loc[y.idxmax() + 9: y.idxmax() + 22])
                if (len(diff) == 0) | (len(np.unique(diff)) == 1):
                    continue
                one_pe_dac = x[:-1].loc[y.idxmax() + 9: y.idxmax() + 22].values[diff.argmin()]
                crossing_log = y_log[:-1].loc[y.idxmax() + 9: y.idxmax() + 22].values[diff.argmin()]

            r1 = find_first_crossing(x.values, y_log, crossing_log)
            crossing = np.exp(crossing_log)

            # plt.subplot(2, 1, 1)
            plt.axvline(pedestal, color='red', linestyle='solid', label='pedestal')
            # plt.axvline(one_pe_dac, color='blue', linestyle='dashed', label='1 pe')
            # plt.axvline(r1, color=ax[0].get_color(), linestyle='dashed', label='r1')
            # plt.axhline(crossing, color=ax[0].get_color(), linestyle='solid', label='crossing')
            # plt.subplot(2, 1, 2)
            # plt.plot(x.loc[y.idxmax()+8 : y.idxmax()+30][:-1], diff, label='ch %d dac %d'%(ch, inDAC))
            # plt.plot(x[:-1], np.diff(y_log), label='ch %d dac %d' % (ch, inDAC))
            res['channel'].append(ch)
            res['inDAC'].append(inDAC)
            res['pedestal'].append(pedestal)
            res['one_pe_dac'].append(one_pe_dac)
            res['one_pe_freq'].append(crossing)
            res['r1_dac'].append(r1)

        # plt.subplot(2, 1, 1)
        plt.grid()
        # plt.xlim([pedestal - 20, pedestal + 50])
        plt.title('Channel %d low' % ch)
        plt.yscale('log')
        plt.legend()

        # plt.subplot(2, 1, 2)
        plt.xlabel('Global threshold [dac]')
        # plt.grid()
        # plt.legend()
        plt.tight_layout()
        plt.savefig(channel_folder + '/ch%d.png' % ch)
        plt.show()
        plt.close()

    res_df = pd.DataFrame(res)
    res_df.to_csv(output_folder + "SiPM_gain.csv", index=False)
    return res_df



def find_3pe_amplitude(SiPM_biased_df, pedestal_df, output_folder):
    res = {'channel': [], 'inDAC': [],
           'pedestal': [], 'one_pe_dac': [], 'one_pe_freq': [], 'r1_dac': []}

    channel_folder = output_folder + 'channel/'
    if not os.path.exists(channel_folder):
        os.makedirs(channel_folder)

    for ch in np.unique(SiPM_biased_df.channel): #[28, 50, 56, 61, 62]: #
        plt.subplots(1, 1, figsize=(14, 8))
        # plt.subplots(2, 1, figsize=(14, 8), height_ratios=(3, 1), sharex=True)
        for inDAC in np.unique(SiPM_biased_df.inDAC):
            selection = (SiPM_biased_df.inDAC == inDAC) & (SiPM_biased_df.channel == ch)
            x = SiPM_biased_df.loc[selection, 'TL_dac'][5:]
            y = SiPM_biased_df.loc[selection, 'TL_freq'][5:]
            y_log = np.where(y.values > 0.1, y.values, -10) # remove warning log of 0
            y_log = np.log(y_log, where=(y_log > 0), out=np.zeros_like(y_log, dtype=np.float64))

            ax = plt.scatter(x, y, label='ch %d dac %d' % (ch, inDAC), marker='x')

            methodA=True
            methodAB=False
            if methodA:

                # start = np.clip(y_log.argmax()-15, 0, 100)
                # init_slice = slice(start, y_log.argmax() + 45, 1)
                # diff = np.diff(y_log[init_slice])

                # if (len(diff) == 0) | (len(np.unique(diff))==1):
                #     continue

                if methodAB:
                    pedestal = pedestal_df.iloc[pedestal_df.loc[pedestal_df.channel==ch, 'TL_freq'].idxmax()].TL_dac
                    pedestal_index_for_x = np.where(x==pedestal)[0][0]
                else:
                    pedestal = x.values[y_log.argmax()]

                    # pedestal_index_for_diff = diff.argmax()+3
                    # pedestal_index_for_x = start + pedestal_index_for_diff
                    # pedestal = x.values[pedestal_index_for_x]
                # diff = diff[15-start+(y_log.argmax()-15)+6:]
                start_index = y_log.argmax()+2
                init_slice = slice(start_index, start_index + 55, 1)
                diff = np.diff(y_log[init_slice])
                # diff = diff[pedestal_index_for_diff:]
                # half_efficiency_pe_list = [-5]
                # for i in range(3):
                #     argmin = np.argmin(diff[half_efficiency_pe_list[-1]+5:])
                #     half_efficiency_pe_list.append(half_efficiency_pe_list[-1]+5+argmin)
                # half_efficiency_pe_list.remove(-5)
                 # for half_efficiency_pe in half_efficiency_pe_list:
                #     plt.axvline(x[:-1].values[pedestal_index_for_x+half_efficiency_pe])

                half_efficiency_pe_list = argrelmin(diff, order=4)[0][:3]
                for half_efficiency_pe in half_efficiency_pe_list:
                    plt.axvline(x[:-1].values[start_index+half_efficiency_pe])
                # plt.plot(diff, marker='*')
                # plt.show()
                if len(half_efficiency_pe_list)<3:
                    pass

                three_pe_size = round((half_efficiency_pe_list[2] - half_efficiency_pe_list[1])*2/3 + half_efficiency_pe_list[2])
                three_pe_slice = slice(start_index, start_index + three_pe_size, 1)
                # three_pe_slice = slice(pedestal_index_for_x, pedestal_index_for_x + 45, 1)
                one_pe_dac = x[:-1].values[three_pe_slice][diff.argmin()]
                crossing_log = y_log[:-1][three_pe_slice][diff.argmin()]

                try:
                    y_data = y_log[three_pe_slice].copy()
                    # B = min(y_data)
                    # y_data -= B
                    # A = max(y_data)
                    # y_data /= A
                    # p0_init = [pedestal+10, 1]
                    # fit, cov = curve_fit(f=ScurveFit, xdata=x[one_pe_slice], ydata=y_data, p0=p0_init)

                    B = min(y_data)
                    y_data -= B
                    A = max(y_data)
                    y_data /= A
                    two_pe_freq = y_data[(half_efficiency_pe_list[1]+half_efficiency_pe_list[0])//2]
                    three_pe_freq = y_data[(half_efficiency_pe_list[2]+half_efficiency_pe_list[1])//2]
                    p0_init = [1-two_pe_freq, pedestal+half_efficiency_pe_list[0], 2, two_pe_freq-three_pe_freq, pedestal+half_efficiency_pe_list[1], 4, three_pe_freq, pedestal+half_efficiency_pe_list[2], 6]
                    # p0_init = [0.4, pedestal+10, 2, 0.3, pedestal+20, 4, 0.3, pedestal+30, 6]
                    # p0_init = [1-middle_freq, pedestal+10, 2, middle_freq, pedestal+20, 4]
                    # p0_init = [1, pedestal+10, 2]
                    fit, cov = curve_fit(f=Scurve_sum_fit, xdata=x[three_pe_slice], ydata=y_data, p0=p0_init)

                    plt.plot(x[three_pe_slice], np.exp(Scurve_sum_fit(x[three_pe_slice], *fit) * A + B))

                except (RuntimeError, TypeError) as e:
                    print("fit error")

            else:
                pedestal = x[y.idxmax()]
                diff = np.diff(y_log.loc[y.idxmax() + 9: y.idxmax() + 22])
                if (len(diff) == 0) | (len(np.unique(diff)) == 1):
                    continue
                one_pe_dac = x[:-1].loc[y.idxmax() + 9: y.idxmax() + 22].values[diff.argmin()]
                crossing_log = y_log[:-1].loc[y.idxmax() + 9: y.idxmax() + 22].values[diff.argmin()]

            r1 = find_first_crossing(x.values, y_log, crossing_log)
            crossing = np.exp(crossing_log)

            # plt.subplot(2, 1, 1)
            plt.axvline(pedestal, color='red', linestyle='solid', label='pedestal')
            # plt.axvline(one_pe_dac, color='blue', linestyle='dashed', label='1 pe')
            # plt.axvline(r1, color=ax[0].get_color(), linestyle='dashed', label='r1')
            # plt.axhline(crossing, color=ax[0].get_color(), linestyle='solid', label='crossing')
            # plt.subplot(2, 1, 2)
            # plt.plot(x.loc[y.idxmax()+8 : y.idxmax()+30][:-1], diff, label='ch %d dac %d'%(ch, inDAC))
            # plt.plot(x[:-1], np.diff(y_log), label='ch %d dac %d' % (ch, inDAC))
            res['channel'].append(ch)
            res['inDAC'].append(inDAC)
            res['pedestal'].append(pedestal)
            res['one_pe_dac'].append(one_pe_dac)
            res['one_pe_freq'].append(crossing)
            res['r1_dac'].append(r1)

        # plt.subplot(2, 1, 1)
        plt.grid()
        # plt.xlim([pedestal - 20, pedestal + 50])
        plt.title('Channel %d low' % ch)
        plt.yscale('log')
        plt.legend()

        # plt.subplot(2, 1, 2)
        plt.xlabel('Global threshold [dac]')
        # plt.grid()
        # plt.legend()
        plt.tight_layout()
        plt.savefig(channel_folder + '/ch%d.png' % ch)
        plt.show()
        plt.close()

    res_df = pd.DataFrame(res)
    res_df.to_csv(output_folder + "SiPM_gain.csv", index=False)
    return res_df



