import os
import time
import pandas as pd
from alive_progress import alive_bar

from src import CONSTANTS
from src.FPGA import FPGA_base
from src.deserializer_standalone_TDC import deserializer_standalone_TDC
from src.external_DAC import external_DAC
from src.pll import PLL
from src.deserialiser import ASIC_deserializer
from src.external_ADC import external_ADC
from src.ASIC.asic import asic
from src.temperature_sensor import temperature_sensor
from src.utils import *

from src.HV_WRAPPER import HV_WRAPPER
import src.CONSTANTS
from uiroc.device import FtdInterface


class temporoc3:

    def __init__(self, config, mode='master', SC_config_file="../config/temporoc3_hw_default_SC.csv",
                 FPGA_PLL=False):
        # No communication in the constructor to allow to instantiate object without the board connected and powered on.
        self.mode = mode
        board_config = board = None
        for board in config['board']:
            board_config = config['config_B%d' % board]
            if board_config['mode'] == mode:
                break
        assert board_config is not None, "config was not defined as expected ! \nFor exemple: config = {'board': [1], 'config_B1': {'board': 1, 'mode': 'master'}}"
        self.board = board
        self.board_config = board_config
        self.config = config
        self.dev = FtdInterface()

        self.connected = False

        self.asic = asic(self.dev, SC_config_file, chipID=1)
        # self.asic2 = asic(self.dev, SC_config_file, chipID=5)
        self.asic_list = [self.asic]

        if len(self.asic_list) == 1:
            type = "single"
        elif len(self.asic_list) == 2:
            type = "dual"
        else:
            raise ValueError("Only single or dual board is supported")

        self.fpga = FPGA_base(self.dev, self.asic_list, FPGA_PLL)
        self.board_config['FPGA_PLL'] = FPGA_PLL

        self.deserializer = ASIC_deserializer(self.dev, self.asic)
        self.deserializer_list = [self.deserializer]
        config['DLL_decodeLib'] = self.deserializer.decodeLibName

        # extra deserialiser for TDC test structures
        self.deserializer_standalone_TDC = deserializer_standalone_TDC(self.dev)

        # Extra component on the evaluation board
        self.pll = PLL(self.dev, self.deserializer_list)
        self.external_ADC = external_ADC(self.dev)
        self.external_DAC = external_DAC(self.dev)
        self.temperature_sensor = temperature_sensor(self.dev)

        self.hv = HV_WRAPPER(board_config)
        self.object_to_close_at_the_end = []


    def connect_ASIC(self):
        serial_startswith = b'TP2_%02d' % self.board
        self.dev.connect(serial_startswith)
        if not self.dev.is_connected():
            print("Check ASIC & FPGA are powered ON and connected to PC !")
            os.removedirs(self.config['save_folder'])
            exit()
        self.connected = True

        self.config['firmware_timestamp_str'] = self.fpga.get.read_timestamp()


        return True


    def close(self):
        self.asic.i2c.SC_stats()

        for instance in self.object_to_close_at_the_end:
            instance.close()
        # self.pll.set_pll_rstb(0) # save power!  # comment this line because PLL is slow to configure each time again
        self.fpga.set.power_on_ASIC(0)
        if self.hv.connected:
            self.hv.close()

        return self.dev.close()

    def correct_default_HW_SC(self):
        # should be default

        # bias_1V HW default is 8
        self.asic.common.set.bias_1V(11)
        # Vbias_1V = 1V when code 11 for B6

        # ib_calibDac HW default is 4
        self.asic.bias.calibDac.Ib.set_4b(7)
        self.asic.common.set.Ibo_threshold_dac(1) # maximum current in thresholdDAC OTA

        # Discriminator thresholds default = 0
        self.asic.common.set.dacTL(1023)
        self.asic.common.set.dacTH(1023)
        self.asic.common.set.dacQ(1023)

        # Zin dac_select default = 0 = low impedance
        self.asic.ch.all().select.Zin.high()

    def init_ASIC(self):
        self.correct_default_HW_SC()

        readout_mode = 'fuller' # 'full_adc_tdc'
        self.asic.interface.select.dig_modeRO(readout_mode)
        self.board_config['readout_mode_code'] = self.asic.interface.select.dig_modeRO.RO_code
        self.board_config['readout_mode'] = readout_mode

        self.asic.common.select.trigger.global_ASIC()  # to launch all peak detector with ch0 low trigger
        self.asic.interface.select.global_trigger.ORTL()

        nb_trigger = 1
        self.asic.interface.set.nb_trigger(nb_trigger)
        self.board_config['nb_trigger'] = nb_trigger

        self.asic.common.en.latch()
        self.fpga.set.ro_enable_ASIC(1)
        self.fpga.set.val_evt_ASIC(1)
        # tempo.asic.interface.en.sync_cluster()  # not required : only if Cluster specific data conversion

        # Time Trigger and Threshold settings
        self.asic.bias.discri.TL.enable()
        self.asic.bias.discri.TH.enable()
        self.asic.common.dis.hyst_TH()
        self.asic.common.dis.hyst_TL()

    def get_firmware_name(self, config):
        fw_hash = self.fpga.get.hash_fw_version()
        config['fw_hash'] = fw_hash

        # todo: fw_hash is not changed at every compilation
        # # check fw_hash corresponds to what is expected
        # if not src.CONSTANTS.is_firmware_top_2026_02_16_17_30(fw_hash):
        #     print("Uncorrect firmware loaded into the FPGA !")
        #     pass
        #
        # # All firmware known should be listed there:
        # if is_firmware_top_2026_02_16_17_30(fw_hash):
        #     fw_name = 'top_2026_02_16_17_30'
        # else:
        #     fw_name = 'Firmware not identified !'
        #     print(fw_name)

        # config['fw_name'] = fw_name

    def save_ASIC_and_FPGA_config(self, config):

        # read all FPGA registers
        FPGA_registers = []
        for i in range(128):
            FPGA_registers.append(self.dev.read_word(i))
            time.sleep(0.001)  # required delay
        config['FPGA'] = {i : FPGA_registers[i] for i in range(128)}

        local_output_dir = config['save_folder']
        config_file = local_output_dir + '/config.yaml'
        with open(config_file, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False, Dumper=VerboseSafeDumper)
            outfile.close()

        # save a copy for parallel analysis (while taking data)
        # shutil.copyfile(config_file, local_output_dir + '/config0.yaml')

        filepath_i2c_df = local_output_dir + "/i2c_df.csv"
        self.asic.i2c.df_i2c.to_csv(filepath_i2c_df, index=False)


    def get_standalone_ADC_10b_single_sample(self):
        # firmware orders temporoc standalone ADC to sample when writing anything into register addr_test_adc_low (auto-reset)
        # ie control ADCSample (L21) and ADCSelectn (M18)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_adc_low, 55)  # arbitrary value
        return (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_adc_high )<<8) + self.dev.read_word \
            (src.CONSTANTS.REGISTERS.addr_test_adc_low)

    def turn_off_digital_activity(self):

        # CUT digital clock
        self.fpga.set.FPGA_as_clock_source() # instead of PLL source
        self.fpga.select.ck_from_FPGA_to_ASIC.off()

        # DISABLE hit register probe
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_read_reg_channel, 0)

        # DISABLE clusters readout clocks
        self.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

        # DISABLE digital
        self.fpga.set.ro_enable_ASIC(0)

        # # DISABLE latch trigger
        # self.fpga.set.val_evt_ASIC(1)
        # self.common.en.latch()


    def count_trigger_rising_edges(self, time_acq_window = 2e-3):
        # time_acq_window is seconds

        # time_lsb = 2048 * 20e-9 # s
        time_lsb = 256 * 20e-9 # s
        time_acq_code = int(time_acq_window//time_lsb) - 1 # 2 ms = 47
        assert time_acq_code >= 0
        assert time_acq_code < 2** 16
        time_acq_window = time_acq_code * time_lsb

        # reset 16-bit counter
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_probe_mon_reset, 1)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_probe_mon_reset, 0)
        # you may want to double the reset to make sure it's reset effectively done
        # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_probe_mon_reset, 1)
        # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_probe_mon_reset, 0)

        # set time out and launch counter
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_probe_mon_time1, (time_acq_code & 0xff00) >> 8)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_probe_mon_time0, (time_acq_code & 0xff))
        time.sleep(time_acq_window)

        # read counter
        count = ((self.dev.read_word(src.CONSTANTS.REGISTERS.addr_probe_mon_val3) << 24) +
                 (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_probe_mon_val2) << 16) +
                 (self.dev.read_word(src.CONSTANTS.REGISTERS.addr_probe_mon_val1) << 8) +
                 self.dev.read_word(src.CONSTANTS.REGISTERS.addr_probe_mon_val0))
        return time_acq_window, count

    def find_approximately_threshold(self, channel):

        thres = 512  # 2**10/2
        step = 512
        for i in range(7):
            self.asic.common.set.dacTL(thres)
            self.asic.common.set.dacTH(thres)
            self.fpga.reset.tpr_latch()
            # self.reset_hit_register()    addr_read_reg_reset
            hit_reg = self.fpga.get.hit_register_channel(channel)
            # print(thres, bin(hit_reg))
            # tempo.fpga.get.hit_map()

            if hit_reg & 0b100:  # transition from 1 to 0 is above tested threshold
                thres += step // 2
            else:
                thres -= step // 2
            step = step // 2

        # print(thres)
        # tempo.reset_hit_register()
        # tempo.fpga.set.hit_register_channel(channel)
        # print(tempo.fpga.get.hit_register_channel())
        return thres

    def scurve(self, range_TL: list, range_TH: list):
        acquisition_time_ns = 20
        self.fpga.set.val_event_width_ns(
            acquisition_time_ns)  # set minimum val_event width to be as max as possible immune to noise
        self.fpga.reset.latch_ASIC(1)  # set high because active low signal controlled by FPGA
        self.fpga.set.val_evt_ASIC(0)  # set low because active high signal controlled by FPGA 

        efficiency = {'channel': [], 'acquisition_time_ns': [],
                      'low_thres_dac': [], 'high_thres_dac': [],
                      'low_efficiency': [], 'high_efficiency': []}
        channel_list = [i for i in range(64)]
        gain_left = 'high' if len(range_TL) <= len(range_TH) else 'low'
        N_min = min(len(range_TL), len(range_TH))
        N_max = max(len(range_TL), len(range_TH))

        for i in range(N_min):
            TL = range_TL[i]
            TH = range_TH[i]
            self.asic.common.set.dacTL(TL)
            self.asic.common.set.dacTH(TH)
            hit_reg = self.fpga.get.hit_register_faster()

            efficiency['low_thres_dac'] += [TL] * len(channel_list)
            efficiency['low_efficiency'] += hit_reg.T[src.CONSTANTS.REGISTERS.low_gain_index][channel_list].tolist()
            efficiency['high_thres_dac'] += [TH] * len(channel_list)
            efficiency['high_efficiency'] += hit_reg.T[src.CONSTANTS.REGISTERS.high_gain_index][channel_list].tolist()

        for i in range(N_min, N_max):
            if gain_left == 'low':
                TL = range_TL[i]
                self.asic.common.set.dacTL(TL)
                hit_reg = self.fpga.get.hit_register_faster()
                efficiency['low_thres_dac'] += [TL] * len(channel_list)
                efficiency['low_efficiency'] += hit_reg.T[src.CONSTANTS.REGISTERS.low_gain_index][channel_list].tolist()
                efficiency['high_thres_dac'] += [np.nan] * len(channel_list)
                efficiency['high_efficiency'] += [np.nan] * len(channel_list)

            elif gain_left == 'high':
                TH = range_TH[i]
                self.asic.common.set.dacTH(TH)
                hit_reg = self.fpga.get.hit_register_faster()
                efficiency['low_thres_dac'] += [np.nan] * len(channel_list)
                efficiency['low_efficiency'] += [np.nan] * len(channel_list)
                efficiency['high_thres_dac'] += [TH] * len(channel_list)
                efficiency['high_efficiency'] += hit_reg.T[src.CONSTANTS.REGISTERS.high_gain_index][
                    channel_list].tolist()

        efficiency['channel'] += channel_list
        efficiency['acquisition_time_ns'] = [acquisition_time_ns] * len(efficiency['channel'])

        return pd.DataFrame(efficiency)

    def find_approximately_threshold_for_all_channels(self):
        # Enable pads outputting multiplexed latched trigger signals
        self.asic.interface.en.trigT_L_RS_mux()
        self.asic.interface.en.trigT_H_RS_mux()
        self.asic.interface.en.trigQ_RS_mux()

        # self.asic.ch.all().disable.TH()

        # Let the FPGA handles the trigger latches reset
        self.asic.common.en.bypassResetMgmt()  # needed otherwise temporoc digital under reset (if ro_enable at 0) holds the trigger latch under reset
        self.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset

        acquisition_time_ns = 20  # probably less because of superposition of resetn_latch with val_evt_p
        self.fpga.set.val_event_width_ns(acquisition_time_ns)  # set minimum val_event width to be as max as possible immune to noise
        self.fpga.set.resetn_latch_ASIC(1)  # set high because active low signal controlled by FPGA
        self.fpga.set.val_evt_ASIC(0)  # set low because active high signal controlled by FPGA
        self.asic.common.en.latch()  # enable latching because FPGA monitor latch state of any trigger

        thres = np.array([[512, 512]] * 64)
        step = np.array([[512, 512]] * 64)
        # direction = np.array([['', '']] * 64)
        channel_list = range(64)

        efficiency = {'channel': [], 'acquisition_time_ns': [], 'low_thres_dac': [], 'high_thres_dac': [],
                      'low_efficiency': [], 'high_efficiency': []}
        # next_print = "i 0 ch %d  high [%d - %d] => %s => %s %d" % (0, thres[0][1] - step[0][1], thres[0][1] + step[0][1], '%d', '%s', thres[0][1])
        thres_left_to_explore = [512]

        print('Thresholds left to explore (for both gain):')

        while len(thres_left_to_explore) > 0:
            # set global threshold for all channel for both gain
            self.asic.common.set.dacTH(thres_left_to_explore[0])
            self.asic.common.set.dacTL(thres_left_to_explore[0])
            time.sleep(0.1)  # needed otherwise low threshold not stabilised yet
            print(thres_left_to_explore)
            hit_reg = self.fpga.get.hit_register_faster()

            efficiency['channel'] += channel_list
            efficiency['low_thres_dac'] += [thres_left_to_explore[0]] * len(channel_list)
            efficiency['low_efficiency'] += hit_reg.T[src.CONSTANTS.REGISTERS.low_gain_index][channel_list].tolist()
            efficiency['high_thres_dac'] += [thres_left_to_explore[0]] * len(channel_list)
            efficiency['high_efficiency'] += hit_reg.T[src.CONSTANTS.REGISTERS.high_gain_index][channel_list].tolist()

            # Update only channel and gain whose threshold match explored threshold (during this iteration)
            scanned_channel_gain = thres == thres_left_to_explore[0]
            channel_list_to_update, gain_list_to_update = np.where(scanned_channel_gain)
            for ci, gain in zip(channel_list_to_update, gain_list_to_update):

                # for each hit_reg MSB to LSB : DISCRI H / L / Q
                if hit_reg[ci][gain] == 1:
                    thres[ci][gain] += step[ci][gain] // 2
                    # direction[ci][gain] = '>'
                else:
                    thres[ci][gain] -= step[ci][gain] // 2
                    # direction[ci][gain] = '<'
                step[ci][gain] = step[ci][gain] // 2

                # print(next_print%(hit_reg[ci][gain], direction[ci][gain]))
                # next_print = "ch %d  low [%d - %d] => %s => %s %d" % (ci, thres[ci][gain] - step[ci][gain], thres[ci][gain] + step[ci][gain], '%d', '%s', thres[ci][gain])
                # self.common.probeDig.channel(ci).TrigT_H_RS()

            # Update threshold list to explore
            thres_left_to_explore.remove(thres_left_to_explore[0])
            unique_thres_list = np.unique(thres[np.where((step >= 8) & scanned_channel_gain)]).tolist()
            thres_left_to_explore += unique_thres_list
            pass
        pass

        efficiency['acquisition_time_ns'] = [acquisition_time_ns] * len(efficiency['channel'])

        df = pd.DataFrame(efficiency)

        # determine expected threshold
        expected_threshold = {'channel': [], 'low_thres_dac': [], 'high_thres_dac': [],
                              'low_thres_dac_A': [], 'high_thres_dac_A': [],
                              'low_thres_dac_B': [], 'high_thres_dac_B': []}
        for channel in channel_list:
            selection = (df.channel == channel)
            expected_threshold['channel'].append(channel)
            for gi, gain in enumerate(['high', 'low']):

                # closest efficiency value to 0.5 or last threshold tested if efficiency saturated
                array = np.asarray(df.loc[selection, gain + '_efficiency'])
                idx = (np.abs(array - 0.5)).argmin()
                estimated_threshold_A = int(thres.T[gi][channel])
                estimated_threshold_B = df.loc[selection, gain + '_thres_dac'].iloc[idx]

                if (array[idx] == 1.0) | (array[idx] == 0.0):
                    estimated_threshold = estimated_threshold_A
                    # print('ch%d %s : eff %.2f -> [%d]  %d' % (channel, gain, estimated_threshold_A, array[idx], estimated_threshold_B))
                else:
                    estimated_threshold = estimated_threshold_B
                    # print('ch%d %s : eff %.2f -> %d  [%d]' % (channel, gain, estimated_threshold_A, array[idx], estimated_threshold_B))

                expected_threshold[gain + '_thres_dac'].append(estimated_threshold)
                expected_threshold[gain + '_thres_dac_A'].append(estimated_threshold_A)
                expected_threshold[gain + '_thres_dac_B'].append(estimated_threshold_B)

                # # find value on which fit should be applied
                # indexesOfMin = np.where( == df.toa.min())[0]
                # start = indexesOfMin[0]
                # indexesOfMin = indexesOfMin[
                #     indexesOfMin > (start + 3125 / step / 1e12)]  # length of the tdc caracteristic
                # if len(indexesOfMin) == 0:
                #     print("Could not find the end of the TDC caracteristic.")
                # stop = indexesOfMin[0]

        expected_threshold_df = pd.DataFrame(expected_threshold)
        return expected_threshold_df, df

    def setup_scurve_all_ch(self, discri_list=[1, 2]):
        self.fpga.set.ro_enable_ASIC(0)
        self.fpga.select.ck_from_FPGA_to_ASIC.off()
        self.asic.interface.dis.ck320()
        self.asic.interface.dis.tdc_ck()
        self.asic.ch.all().disable.tdcL()
        self.asic.ch.all().disable.tdcH()

        # Enable pads outputting multiplexed latched trigger signals
        self.asic.interface.en.trigT_L_RS_mux()
        self.asic.interface.en.trigT_H_RS_mux()
        self.asic.interface.en.trigQ_RS_mux()

        # Let the FPGA handles the trigger latches reset
        self.asic.common.en.bypassResetMgmt()  # let the FPGA control the trigger latch reset
        self.fpga.pulser.release_resetn_latch()  # otherwise, FPGA pulser holds the resetn_latch line in reset
        self.fpga.set.resetn_latch_ASIC(1)  # set high because active low signal controlled by FPGA
        self.fpga.set.val_evt_ASIC(0)  # set low because active high signal controlled by FPGA
        self.asic.common.en.latch()  # enable latching because FPGA monitor latch state of any trigger

        enabled_ASIC_ch = list(range(64))
        self.asic.ch.all_except(enabled_ASIC_ch).disable.front_end_except_pdet()
        self.asic.ch.group(enabled_ASIC_ch).set.patGain(63)   # max to minimise noise gaussian
        self.asic.ch.group(enabled_ASIC_ch).set.patComp(0)
        self.asic.ch.group(enabled_ASIC_ch).disable.TQ()

        if 1 in discri_list:
            self.asic.ch.group(enabled_ASIC_ch).enable.TL()
            self.asic.bias.discri.TL.enable()
        else:
            self.asic.ch.group(enabled_ASIC_ch).disable.TL()
            self.asic.bias.discri.TL.disable()

        if 2 in discri_list:
            self.asic.ch.group(enabled_ASIC_ch).enable.TH()
            self.asic.bias.discri.TH.enable()
        else:
            self.asic.ch.group(enabled_ASIC_ch).disable.TH()
            self.asic.bias.discri.TH.disable()

        self.asic.ch.all_except(enabled_ASIC_ch).disable.all_discri()

    def setup_scurve_for_injection(self):
        self.asic.ch.all().disable.use_ctest()  # bypass 1.5 pF internal injection capacitor, use external instead
        self.asic.ch.all().enable.cmd_test()
        self.fpga.OUT2_select.val_evnt()
        # # self.fpga.OUT2_select.tpr_read_clk()

    def get_scurve_all_ch(self, dac_range, acquisition_time_ns=1000, discri_list=[1,2]):
        start = time.perf_counter()
        self.fpga.set.val_event_width_ns(acquisition_time_ns)  # set minimum val_event width
        # min is 20 ns to be as max as possible immune to noise
        # max is ((2**8)-1) * 20 ns

        efficiency = {'channel': [], 'acquisition_time_ns': []}
        efficiency.update({'T%d_%s'%(discri, col):[] for discri in discri_list for col in ['thres_dac', 'efficiency']})

        channel_list = list(range(64))
        for dac_threshold in dac_range:
            # self.asic.common.set.dacT12_wait_stable(dac_threshold, dac_threshold)
            for discri in discri_list:
                self.asic.common.set.dacTx_wait_stable(dac_threshold, discri)

            # self.asic.common.set.dacTQ(dac_threshold)
            # index = src.CONSTANTS.REGISTERS.charge_index

            hit_reg = self.fpga.get.hit_register_faster()

            last_x_values_size = 4 * len(channel_list)
            last_x_values_null = True
            for discri in discri_list:
                index = src.CONSTANTS.REGISTERS.get_index(discri)
                efficiency['T%d_thres_dac'%discri] += [dac_threshold] * len(channel_list)
                efficiency['T%d_efficiency'%discri] += np.round(hit_reg.T[index][channel_list], 2).tolist()
                last_x_values_null &= efficiency['T%d_efficiency'%discri][-last_x_values_size:] == [0] * last_x_values_size
                pass
            efficiency['channel'] += channel_list
            efficiency['acquisition_time_ns'] += [acquisition_time_ns] * len(channel_list)

            if last_x_values_null:
                # print(f"breaking threshold loop at {dac_threshold} dac")
                break

        print("get_scurve_all_ch  Elapsed time : %d seconds" % (time.perf_counter()-start))
        return pd.DataFrame(efficiency)


    def get_scurve_all_discri_individually(self, min_TL_range_per_channel, min_TH_range_per_channel, step=1, acquisition_time_ns=100, discri_list=[1,2]):
        start = time.perf_counter()
        self.fpga.set.val_event_width_ns(acquisition_time_ns)  # set minimum val_event width
        # min is 20 ns to be as max as possible immune to noise
        # max is ((2**8)-1) * 20 ns

        efficiency = {'channel': [], 'acquisition_time_ns': []}
        efficiency.update({'T%d_%s'%(discri, col):[] for discri in discri_list for col in ['thres_dac', 'efficiency']})

        channel_list = list(range(64))
        self.asic.ch.all().disable.all_discri()
        if isinstance(min_TL_range_per_channel, int):
            min_TL_range_per_channel = [min_TL_range_per_channel]*len(channel_list)
        if isinstance(min_TH_range_per_channel, int):
            min_TH_range_per_channel = [min_TH_range_per_channel]*len(channel_list)

        with alive_bar(len(channel_list), force_tty=True) as bar:
            for channel in channel_list:

                self.asic.ch(channel).enable.TL()

                for dac_threshold in range(min_TL_range_per_channel[channel], 1023, 1):
                    self.asic.common.set.dacTL_wait_stable(dac_threshold)
                    TL_eff = self.fpga.get.hit_register_for_one_discri(channel, src.CONSTANTS.REGISTERS.low_gain_index)
                    efficiency['TL_thres_dac'].append(dac_threshold)
                    efficiency['TL_efficiency'].append(np.round(TL_eff,2))
                    if efficiency['TL_efficiency'][-4:] == [0] * 4:
                        # last_4_values_null
                        break
                self.asic.ch(channel).disable.TL()

                self.asic.ch(channel).enable.TH()
                for dac_threshold in range(min_TH_range_per_channel[channel], 1023, 1):
                    self.asic.common.set.dacTH_wait_stable(dac_threshold)
                    TH_eff = self.fpga.get.hit_register_for_one_discri(channel, src.CONSTANTS.REGISTERS.high_gain_index)
                    efficiency['TH_thres_dac'].append(dac_threshold)
                    efficiency['TH_efficiency'].append(np.round(TH_eff,2))
                    if efficiency['TH_efficiency'][-4:] == [0] * 4:
                        # last_4_values_null
                        break
                self.asic.ch(channel).disable.TH()

                longest_list_length = max(len(efficiency['TL_efficiency']), len(efficiency['TH_efficiency']))
                efficiency['TL_efficiency'] += [np.nan] * (longest_list_length - len(efficiency['TL_efficiency']))
                efficiency['TH_efficiency'] += [np.nan] * (longest_list_length - len(efficiency['TH_efficiency']))
                efficiency['TL_thres_dac'] += [np.nan] * (longest_list_length - len(efficiency['TL_thres_dac']))
                efficiency['TH_thres_dac'] += [np.nan] * (longest_list_length - len(efficiency['TH_thres_dac']))
                efficiency['channel'] += [channel] * (longest_list_length - len(efficiency['channel']))
                efficiency['acquisition_time_ns'] += [acquisition_time_ns] * (longest_list_length - len(efficiency['acquisition_time_ns']))
                bar()

        print("get_scurve_all_ch  Elapsed time : %d seconds" % (time.perf_counter()-start))
        return pd.DataFrame(efficiency)

    def get_scurve_all_discri_bygroup(self, min_threshold_range_per_channel, step=1, group_size=8,
                                           acquisition_time_ns=100, discri_list = [1,2]):
        assert group_size in [1,2,4,8,16,32,64]
        start = time.perf_counter()
        self.fpga.set.val_event_width_ns(acquisition_time_ns)  # set minimum val_event width
        # min is 20 ns to be as max as possible immune to noise
        # max is ((2**8)-1) * 20 ns

        efficiency = {'channel': [], 'acquisition_time_ns': []}
        efficiency.update({'T%d_%s'%(discri, col):[] for discri in discri_list for col in ['thres_dac', 'efficiency']})

        self.asic.ch.all().disable.all_discri()
        if isinstance(min_threshold_range_per_channel, int):
            min_threshold_range_per_channel = [min_threshold_range_per_channel] * 64
        last_x_values_size = 4 * group_size

        with alive_bar(group_size*len(discri_list), force_tty=True) as bar:
            for channel_start in range(group_size):

                channel_list = list(range(channel_start, 64, group_size))
                for i, discri in enumerate(discri_list):

                    self.asic.ch.group(channel_list).enable.discri(discri)
                    min_threshold_range = min(min_threshold_range_per_channel[i][channel_list])
                    if min_threshold_range < 0:
                        min_threshold_range = 0
                        pass
                    for dac_threshold in range(min_threshold_range, 1023, step):
                        self.asic.common.set.dacTx_wait_stable(dac_threshold, discri)
                        threshold_eff = self.fpga.get.hit_register_for_group_size_discri(channel_start,
                                                                                         src.CONSTANTS.REGISTERS.get_index(discri),
                                                                                         group_size)
                        if dac_threshold==min_threshold_range:
                            if all(threshold_eff<1):
                                print("Strange result, repeating first acquisition for channels "+str(channel_list))
                                threshold_eff = self.fpga.get.hit_register_for_group_size_discri(channel_start,
                                                                                                 src.CONSTANTS.REGISTERS.get_index(
                                                                                                     discri),
                                                                                                 group_size)
                        efficiency['T%d_thres_dac'%discri] += [dac_threshold]*group_size
                        efficiency['T%d_efficiency'%discri] += np.round(threshold_eff, 2).tolist()

                        if efficiency['T%d_efficiency'%discri][-last_x_values_size:] == [0] * last_x_values_size:
                            break
                    self.asic.ch.group(channel_list).disable.discri(discri)
                    bar()

                # longest_list_length = max(len(efficiency['T1_efficiency'])) # todo, len(efficiency['T2_efficiency']))
                longest_list_length = len(efficiency['T1_efficiency'])
                for discri in discri_list:
                    efficiency['T%d_efficiency'%discri] += [np.nan] * (longest_list_length - len(efficiency['T%d_efficiency'%discri]))
                    efficiency['T%d_thres_dac'%discri] += [np.nan] * (longest_list_length - len(efficiency['T%d_thres_dac'%discri]))

                efficiency['channel'] += channel_list * int((longest_list_length - len(efficiency['channel']))/group_size)
                efficiency['acquisition_time_ns'] += [acquisition_time_ns] * (
                            longest_list_length - len(efficiency['acquisition_time_ns']))


        print("get_scurve_all_ch  Elapsed time : %d seconds" % (time.perf_counter() - start))
        return pd.DataFrame(efficiency)


    def common_threshold_scan(self, channel, range_low=None, range_high=None, time_acq_window=50e-3, verbose=False):
        res = {'channel': [], 'acquisition_time_s': [],
               'TH_dac': [], 'TH_freq': [],
               'TL_dac': [], 'TL_freq': []}

        # start = time.perf_counter()
        channel = int(channel)

        prev_thresh = 1023
        self.asic.common.set.dacTL(prev_thresh)
        self.asic.common.set.dacTL(prev_thresh)
        self.count_trigger_rising_edges()  # one for nothing (first acquisition returns shit)

        # self.asic.interface.en.Nor_TrigT_L_RS()
        # self.asic.interface.en.Nor_TrigT_H_RS()
        self.asic.interface.en.digital_probe()

        # LOW gain
        if range_low:
            # Count triggers with digital probe
            # self.fpga.select.trigger_mon.or_trig_l_rs() # NOR latched trigger is too loaded !!
            self.fpga.select.trigger_mon.digit_probe() # Digital probe faster return to baseline
            self.asic.common.probeDig.channel(channel).TrigT_L()

            # res.update({'TL_dac': [], 'TL_freq': []})
            print("ch%d low" % channel)
            pedestal_swept = False
            # self.common.probeDig.channel(channel).TrigT_L()
            # self.common.probeDig.channel(channel).TrigT_L_RS()

            for thresh in range_low:

                self.asic.common.set.dacTL(thresh)  # set threshold
                res['TL_dac'].append(thresh)
                time.sleep(0.01 + abs(prev_thresh-thresh)*0.0001)
                prev_thresh = thresh

                time_acq_window2, count = self.count_trigger_rising_edges(time_acq_window)
                if count==0:
                    # repeat just to be sure
                    time_acq_window2, count = self.count_trigger_rising_edges(time_acq_window)
                res['TL_freq'].append(count / time_acq_window)

                if verbose:
                    print(thresh, count)
                if (count > 100) & (thresh > range_low[4]):  # not among the first threshold values
                    pedestal_swept = True

                last_x_values_null = res['TL_freq'][-4:] == [0] * len(res['TL_freq'][-4:])
                if pedestal_swept & last_x_values_null:
                    break

        # HIGH gain
        if range_high:
            # res.update({'TH_dac': [], 'TH_freq': []})
            # self.fpga.select.trigger_mon.or_trig_h_rs()
            self.fpga.select.trigger_mon.digit_probe() # faster
            self.asic.common.probeDig.channel(channel).TrigT_H()

            print("ch%d high" % channel)
            pedestal_swept = False
            # self.common.probeDig.channel(channel).TrigT_H()
            # self.common.probeDig.channel(channel).TrigT_H_RS()
            for thresh in range_high:
                # print(tempo.dev.i2c.read_register(channel, 66))# == 0b0100_0000

                self.asic.common.set.dacTH(thresh)
                res['TH_dac'].append(thresh)

                time_acq_window2, count = self.count_trigger_rising_edges(time_acq_window)  # FW monitors only digital probe
                res['TH_freq'].append(count / time_acq_window)

                if verbose:
                    print(thresh, count)

                if count > 100:
                    pedestal_swept = True

                last_x_values_null = res['TH_freq'][-4:] == [0] * len(res['TH_freq'][-4:])
                if pedestal_swept & last_x_values_null:
                    break

        # stop = time.perf_counter()
        # print("%.3f ms per channel" % (stop - start))

        # pad lists up to equal length
        longest_list_length = max(len(res['TL_dac']), len(res['TH_dac']), len(res['TL_freq']), len(res['TH_freq']))
        res['channel'] = [channel] * longest_list_length
        res['acquisition_time_s'] = [time_acq_window] * longest_list_length
        res['TL_dac'] += [np.nan] * (longest_list_length - len(res['TL_dac']))
        res['TH_dac'] += [np.nan] * (longest_list_length - len(res['TH_dac']))
        res['TL_freq'] += [np.nan] * (longest_list_length - len(res['TL_freq']))
        res['TH_freq'] += [np.nan] * (longest_list_length - len(res['TH_freq']))

        return pd.DataFrame(res)

    def init_board(self, tempo_dig_ck_freq=320):
        self.pll.configure_with_default_behaviour(self.mode, tempo_dig_ck_freq)
        self.fpga.set.PLL_as_clock_source()
        self.reset_power_check_correct_clock_init()

    def reset_power_check_correct_clock_init(self, FPGA_PLL):
        a = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch)
        if a > 0:
            print('SC fifo full (%d) at startup. power off asic' % a)
            exit()
        self.fpga.set.power_on_ASIC(1)
        self.fpga.reset.all_temporoc()
        time.sleep(0.05)
        if not FPGA_PLL:
            i = 0
            while i<100:
                i +=1
                is_locked = self.pll.check_is_locked()
                # print(is_locked)
                time.sleep(0.01)
                if is_locked:
                    # print("iteration %d" % i)
                    break

            if not self.pll.check_is_locked():
                assert False, "PLL not locked"


