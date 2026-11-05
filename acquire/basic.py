import importlib
import random
from src.common_setup import *
from src.temporoc3 import *
import src.tools as tools
import pandas as pd

def test_basic_read_register(board):
    config = {'board': [board], 'config_B%d'%board: {'board': board, 'mode': 'master'}}
    tempo = temporoc3(config)

    tempo.init_board()
    tempo.asic.interface.dis.ck320()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

    tempo.dev.write_word(30, 0)
    tempo.dev.read_word(30)
    tempo.dev.write_word(REGISTERS.addr_sc_status, 7)
    print(bin(tempo.dev.read_word(REGISTERS.addr_sc_status)))
    time.sleep(1)
    tempo.dev.i2c.write_register(0, 0, 2)
    print(tempo.dev.i2c.read_register(0, 0))

    print(bin(tempo.dev.read_word(REGISTERS.addr_sc_status)))
    tempo.close()



def test_pulser(board):
    config = {'board': [board], 'config_B%d'%board: {'board': board, 'mode': 'master'}}
    tempo = temporoc3(config)
    tempo.init_board()
    tempo.asic.interface.dis.ck320()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()
    tempo.fpga.pulser.disable()
    tempo.fpga.pulser.set_async_feedthrough_mode()
    tempo.fpga.pulser.set_frequency_in_Hz(1.25e6)
    # tempo.FPGA.pulser.set_sync_mode()
    tempo.fpga.pulser.set_nb_impulsions(10)

    print("nb impulsions %d" % tempo.fpga.pulser.get_nb_impulsions())
    print("""""00" & sig_ena_clock & sig_ena_io_0 & sig_ena_in_delay & sig_synchronous (1b) & sig_freq_ctrl (2b);""")
    print(bin(tempo.dev.read_word(REGISTERS.addr_test_tdc_config)))

    tempo.close()

    # tempo.FPGA.pulser.launch()

    # tempo.FPGA.pulser.set_async_feedthrough_mode()
    # tempo.FPGA.pulser.unmask_on_IO0()

    # tempo.pulse_ext_trigger_sync(0, 40)  # infinite loop


def delaybox_scan(board):
    config = {'board': [board], 'config_B%d'%board: {'board': board, 'mode': 'master'}}
    print("connect on Lecroy scope CH0 :    CH1 : ")

    scopeLecroy = tools.lecroyOscilloDAQ("192.168.2.21")
    # scopeLecroy = None
    if scopeLecroy:
        # scopeLecroy.save_setup("delay_box_carac.lss")
        scopeLecroy.load_setup("delay_box_carac.lss")

    time.sleep(1)

    # scope trigger on external trigger, configure to measure delay
    scopeChannelforDelay = 1

    print("Unpower temporoc digital VDDD removing jumper J6 and resistance R62, since both TDC & SC are supplied by VDDA")
    tempo = temporoc3(config)

    tempo.pll.configure_PLL_sync_ext_trigger()
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()

    tempo.reset_power_check_correct_clock_init()

    results = {'delay_code': [],
               'oscilloDelay_mean': [],
               'oscilloDelay_sdev': []}

    local_output_dir = "../output/tdc_scan/delaybox_step_oscillo_delay/"
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # options
    N = 100
    

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()
    # tempo.FPGA.pulser.disable()
    tempo.fpga.pulser.set_sync_mode()
    tempo.fpga.pulser.sync_enable_forever()
    tempo.fpga.pulser.set_frequency_in_Hz(78125)
    tempo.fpga.pulser.launch()
    # tempo.FPGA.pulser.set_async_feedthrough_mode()
    # tempo.FPGA.pulser.set_nb_impulsions(N)

    freq = tempo.fpga.pulser.get_frequency_in_Hz()
    options = "B%d_hitFreq_%d_N_%d"%(board, freq, N)

    # debug
    # tempo.IO.IO7_select.pulse_tdc()
    tempo.fpga.OUT8_select.digit_probe()
    tempo.asic.interface.en.digital_probe()

    # tempo.IO.IO5.en_ck40M()
    # tempo.IO.IO1.en_ck320()
    # tempo.asic.ch.all().disable.front_end()
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacQ(1023)
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

    channel = 1
    tempo.asic.interface.select.dig_modeRO.low_high_tdc()
    tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
    tempo.asic.ch(channel).select.trigTL.external()
    tempo.asic.ch(channel).select.trigTH.external()
    tempo.asic.ch(channel).enable.TH()
    tempo.asic.ch(channel).enable.TL()

    tempo.asic.common.en.latch()
    tempo.fpga.pulser.release_resetn_latch()
    tempo.fpga.set.val_evt_ASIC(1)
    tempo.fpga.fpga.reset.latch_ASIC(1)

    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.conv_syst_ASIC(0)

    # find unique file number
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
    print("Will save events under index %d" % new_file_index)
    filepath = local_output_dir + "%d_%s.csv"%(new_file_index, options)

    for delay in range(2 ** 10):

        tempo.fpga.set.delay_ext_trigger(delay)
        scopeLecroy.clearSweep()
        time.sleep(0.5)

        if scopeLecroy:
            avg = scopeLecroy.getMeasure(scopeChannelforDelay, 'mean')*1e12
            std = scopeLecroy.getMeasure(scopeChannelforDelay, 'sdev')*1e12
        else:
            avg = 0
            std = 0

        print("delay %d : avg=%d ps, std=%d ps" % (delay, avg, std))
        results['delay'].append(delay)
        results['oscilloDelay_mean'].append(avg)
        results['oscilloDelay_sdev'].append(std)

    tempo.close()

    df = pd.DataFrame(results)
    df.to_csv(local_output_dir+"%d_%s.csv"%(new_file_index, options), index=False)






# 1. check 320 MHz clocks with differential probe at voltage converter on capa C152/153
# 2. check jitter between 320 MHz clock and injected pulse
# 3. check linearity external delay box
# 4. check jitter between 320 MHz clock and delayed clocks
# for standalone TDC: on C399/C400
# for internal TDC: on trig_ext on pin5 U26
# 5. check delayed clock frequency: 32 MHz expected

def test_write_read_fifo(tempo, add, subadd, data=3):
    print("before ", tempo.dev.i2c.read_register(add, subadd), end=" ")
    tempo.dev.i2c.write_fifo(pd.DataFrame({'add': [add], 'subadd' : [subadd], 'data': [data]}))
    print("after words ", tempo.dev.i2c.read_register(add, subadd), end=" ")
    tempo.dev.i2c.write_register(add, subadd, data)
    print("after word", tempo.dev.i2c.read_register(add, subadd))

def test_write_fifo(tempo):
    print("before ", tempo.dev.i2c.read_register(0, 1), end=" ")
    tempo.dev.i2c.write_fifo(pd.DataFrame({'add': [0,0], 'subadd' : [1,2], 'data': [15,15]}))
    time.sleep(0.1)
    print("after words ", tempo.dev.i2c.read_register(0, 1), end=" ")


def read_compare_default_HW_SC(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    tempo = temporoc3(config)
    tempo.init_board()

    for i, row in tempo.dev.i2c.df_i2c.iterrows():
        add = row["add"]
        subadd = row["subadd"]
        read_value = tempo.dev.i2c.read_register(add, subadd)
        read_value = tempo.dev.i2c.read_register(add, subadd)
        default_value = int(row["data"],2)
        if read_value != default_value:
            read_value = tempo.dev.i2c.read_register(add, subadd)
            if read_value != default_value:
                print("add, subadd, read_value, default_value", add, subadd, bin(read_value), bin(default_value))
    print("Done comparing. No other differences.")
    tempo.close()

def delete_inherited_registers(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    # extra reg from radioroc not existing in temporoc
    tempo = temporoc3(config)
    tempo.init_board()

    index_to_drop = []
    for i, row in tempo.dev.i2c.df_i2c.iterrows():
        subadd = row["subadd"]
        default_value = row["data"]
        if (subadd>=9) & (subadd<=12):
            if default_value=='00001110':
                index_to_drop.append(i)

    df = tempo.dev.i2c.df_i2c.copy()
    df=df.drop(index_to_drop)
    df.to_csv("config/2.csv", index=False)

    tempo.close()

def setup_combined_test(config):
    config.update({'ck_cycles_in_between_2_hits': [], 'expected_step': [], 'current_step': [],
                   'hit_freq': [], 'pulser_type': [], 'PLL_config_file': []})
    for board in config['board']:
        config['config_B%d'%board].update({'tempo_dig_ck':80})

    injected_channels_ASIC = list(range(64))
    # injected_channels_ASIC = [43, 42, 41]
    # injected_channels_ASIC = [43]

    tempo = temporoc3(config)

    # internal TDC custom step
    tempo.connect_ASIC()
    print("Connecting board %d" % tempo.board)

    m = importlib.import_module('3_internal_TDC', package=None)
    (PLL_config_file, expected_step,
     ck_cycles_in_between_2_hits, hit_frequency, FPGA_divider, tempo_dig_clock_from_PLL_config) = m.select_PLL_config_file(config)

    tempo_dig_ck = config['config_B%d' % tempo.board]['tempo_dig_ck']

    tempo.deserializer.filter.disable.coincidence_inter_asic()
    tempo.fpga.select.foreign_eof.off()

    # Select temporoc digital clock
    tempo.fpga.set.PLL_as_clock_source()

    # PLL input clock on its pin IN0 should be the 100 MHz cristal distributed via the FPGA
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()

    # 320 MHz clock should be received by MASTER FPGA from the MASTER SI5345 PLL
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()

    tempo.pll.flash("../config/PLL/" + PLL_config_file, tempo_dig_clock=tempo_dig_ck)

    tempo.reset_power_check_correct_clock_init()
    tempo.correct_default_HW_SC()

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()

    freq_offset_added_to = 'hit' if tempo_dig_clock_from_PLL_config == (tempo_dig_ck * 1e6) else 'tdc_ck'
    if freq_offset_added_to == 'tdc_ck':  # vary temporoc digital & tdc clock frequency
        tempo.fpga.pulser.set_sync_mode()
        tempo.fpga.pulser.sync_enable_forever()
        tempo.fpga.pulser.set_frequency_in_Hz(hit_frequency) # todo : check hit_frequency value
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

    tempo.asic.ch.all().disable.front_end()

    for injected_channel in injected_channels_ASIC:
        tempo.asic.ch(injected_channel).select.trigTL.external()
        # tempo.asic.ch(injected_channel).select.trigTH.external()
        # tempo.asic.ch(injected_channel).enable.TH()
        tempo.asic.ch(injected_channel).enable.TL()

    tempo.board_config['enable_TL_ASIC_ch']= [injected_channels_ASIC]
    print("injected channels: ", np.sort(injected_channels_ASIC))
    clusters_list = np.unique(np.array(injected_channels_ASIC) // 16).tolist()
    update_config_dict(tempo.board_config, clusters_list)
    tempo.board_config['power_cluster'] = clusters_list
    tempo.asic.interface.dis.ClkDataRO_clusters_except(clusters_list)

    # probed_channel = 43
    # tempo.asic.interface.en.digital_probe()
    # tempo.fpga.OUT2_select.digit_probe()
    # tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()

    # tempo.IO.IO2_select.ser_ovf(cluster)
    # tempo.IO.OUT2_select.pulse_tdc()
    # tempo.fpga.OUT4_select.ser_clk(probed_cluster)

    tempo.asic.interface.select.dig_modeRO('low_tdc')
    print(tempo.asic.interface.select.dig_modeRO.RO_str)

    # for cluster in range(4):
    #     config['total_nb_events_expected_cluster%d'%cluster] = 0

    deserialiser_time = 0
    tempo.deserializer.set_time(deserialiser_time)
    tempo.board_config['deserialiser_time'] = deserialiser_time

    tempo.deserializer.filter.disable.charge()
    tempo.deserializer.filter.disable.coincidence_inter_cluster()


    tempo.save_ASIC_and_FPGA_config(config)

    return tempo



def measure_power_consumption_0(board, static=True, dynamic=False, increase=True, one_by_one=False, freq=200000):
    # 150000  # 200000 # 78125 #20000

    def fill_dict():
        res['RO_mode'].append("full_adc_tdc")
        res['TDC_injected_count'].append(0)
        res['TDC_injected'].append('')
        res['channels_injected'].append(0)
        res['injection_freq'].append(0)

    # connect external pulser and place jumper JU13 close to the SMA input ext_trig
    # configure external pulser to minimum pulse (leading 2.5 ns, trailing 2.5 ns, width 2.5 ns, amplitude 0-1.2V
    # set the frequency to match python function (saved value)
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    v = tools.visaController(16)

    res = {'conditions': [],
           'RO_mode': [],
           'TDC_injected_count': [],
           'TDC_injected': [],
           'injection_freq': [],
           'cluster_RO_enabled': [],
           'channels_injected': [],
           'analog_current': [],
           'digital_current': []}

    print("Remove jumpers on both VDDD and VDDA")
    tempo = temporoc3(config)
    a = tempo.dev.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch)
    if a > 0:
        print('SC fifo full (%d) at startup. power off asic' % a)
        exit()

    options = "B%d_conso" % (board)

    local_output_dir = "../output/basic/DC/"

    # find unique new file index
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
        # new_file_index = int(re.findall("[0-9]+(?=_B)", file_list[-1])[0]) + 1
    filepath = local_output_dir + "%d_%s.csv"
    filepath = filepath % (new_file_index, options)
    print("Will save events in file %s" % filepath)

    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # tests start here
    if static:
        tempo.pll.configure_PLL_no_clocks_except_FPGA()
        time.sleep(0.5)
        assert tempo.pll.check_is_locked()

        tempo.fpga.set.power_on_ASIC(0)
        res['conditions'].append('asic off no clock')
        res['cluster_RO_enabled'].append(0)
        fill_dict()
        digital_current, analog_current = visaController.get_current_consumption()
        res['analog_current'].append(analog_current)
        res['digital_current'].append(digital_current)

        tempo.fpga.set.power_on_ASIC(1)
        tempo.fpga.reset.all_temporoc()
        tempo.asic.interface.select.dig_modeRO.full_adc_tdc()
        res['conditions'].append("asic on after reset")
        fill_dict()
        res['cluster_RO_enabled'].append(4)
        digital_current, analog_current = visaController.get_current_consumption()
        res['analog_current'].append(analog_current)
        res['digital_current'].append(digital_current)

        tempo.pll.configure_PLL_with_default_behaviour()

        tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
        tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
        tempo.fpga.set.PLL_as_clock_source()

        time.sleep(0.5)
        assert tempo.pll.check_is_locked()
        res['conditions'].append("dig with clock ")
        res['cluster_RO_enabled'].append(4)
        fill_dict()
        digital_current, analog_current = visaController.get_current_consumption()
        res['analog_current'].append(analog_current)
        res['digital_current'].append(digital_current)

        for cluster_still_enabled in range(3, -1, -1):
            tempo.asic.interface.dis.ClkDataRO_cluster([cluster_still_enabled])
            res['conditions'].append("%d/4 cluster readout enabled  " % cluster_still_enabled)
            res['cluster_RO_enabled'].append(cluster_still_enabled)

            fill_dict()
            digital_current, analog_current = visaController.get_current_consumption()
            res['analog_current'].append(analog_current)
            res['digital_current'].append(digital_current)
            pass
        tempo.fpga.set.power_on_ASIC(1)
        tempo.fpga.reset.all_temporoc()
        tempo.asic.interface.select.dig_modeRO.full_adc_tdc()

        df = pd.DataFrame(res)
        df.to_csv(filepath, index=False)

        tempo.asic.ch.all().disable.charge()
        tempo.asic.ch.all().disable.timing()
        tempo.asic.ch.all().disable.all_discri()
        tempo.asic.common.set.dacTL(1023)
        tempo.asic.common.set.dacTH(1023)
        tempo.asic.common.set.dacQ(1023)
        res['conditions'].append("Cut all analog charge & timing & discri ")
        fill_dict()
        res['cluster_RO_enabled'].append(0)
        digital_current, analog_current = visaController.get_current_consumption()
        res['analog_current'].append(analog_current)
        res['digital_current'].append(digital_current)

    if dynamic:
        tempo.fpga.set.power_on_ASIC(1)
        tempo.fpga.reset.all_temporoc()
        tempo.asic.interface.select.dig_modeRO.low_high_tdc()

        tempo.asic.ch.all().disable.charge()
        tempo.asic.ch.all().disable.timing()
        tempo.asic.ch.all().disable.all_discri()
        tempo.asic.common.set.dacTL(1023)
        tempo.asic.common.set.dacTH(1023)
        tempo.asic.common.set.dacQ(1023)

        tempo.pll.configure_PLL_sync_ext_trigger()
        time.sleep(0.5)
        assert tempo.pll.check_is_locked()

        # FPGA pulser not used
        # tempo.FPGA.pulser.set_async_feedthrough_mode()
        # tempo.FPGA.pulser.set_frequency_in_Hz(78125)
        # tempo.FPGA.pulser.unmask_on_IO0()
        # tempo.FPGA.pulser.unmask_on_ext_trigger()
        # freq = tempo.FPGA.pulser.get_frequency_in_Hz()

        tempo.fpga.set.val_evt_ASIC(1)
        tempo.asic.common.en.latch()
        tempo.fpga.set.ro_enable_ASIC(1)
        tempo.asic.interface.en.Inh_rstOnDlyH()
        tempo.asic.interface.en.Inh_rstOnDlyL()
        tempo.asic.interface.set.nb_trigger(31)  # expecting never 3 frames per injection, instead always 2

        # debug:
        # tempo.asic.interface.en.digital_probe()
        tempo.asic.interface.dis.digital_probe()

        tempo.fpga.OUT5.en_ck40M()
        tempo.fpga.OUT8_select.digit_probe()
        # tempo.IO.IO7_select.ser0_data()
        tempo.fpga.OUT7_select.ser_clk(0)
        tempo.fpga.OUT1.en_ck320()
        # tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
        tempo.asic.interface.en.ClkDataRO_cluster([0, 1, 2, 3])

        if one_by_one:
            for channel in range(64):
                tempo.asic.ch(channel).select.trigTL.external()
                tempo.asic.ch(channel).select.trigTH.external()
                tempo.asic.ch(channel).enable.TH()
                tempo.asic.ch(channel).enable.TL()
                tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
                time.sleep(0.1)

                res['conditions'].append("one_by_one_channel")
                res['RO_mode'].append("low_high_tdc")
                res['TDC_injected_count'].append(2)
                res['TDC_injected'].append('both')
                res['channels_injected'].append(channel)
                res['injection_freq'].append(freq)
                res['cluster_RO_enabled'].append(4)

                digital_current, analog_current = visaController.get_current_consumption()
                res['analog_current'].append(analog_current)
                res['digital_current'].append(digital_current)
                print("analog %.2f mA, digital %.2f mA" % (analog_current, digital_current))

                tempo.asic.ch(channel).disable.TH()
                tempo.asic.ch(channel).disable.TL()
        else:
            for channel in range(63):
                tempo.asic.ch(channel).select.trigTL.external()
                tempo.asic.ch(channel).select.trigTH.external()

                if increase == False:
                    tempo.asic.ch(channel).enable.TH()
                    tempo.asic.ch(channel).enable.TL()
            if increase:
                list_channel = list(range(64))
            else:
                list_channel = list(range(63, -1, -1))

            for channel in list_channel:
                if increase:
                    tempo.asic.ch(channel).enable.TH()
                    tempo.asic.ch(channel).enable.TL()
                    time.sleep(0.1)
                    digital_current, analog_current = visaController.get_current_consumption()

                else:
                    digital_current, analog_current = visaController.get_current_consumption()
                    tempo.asic.ch(channel).disable.TH()
                    tempo.asic.ch(channel).disable.TL()
                    time.sleep(0.1)
                # tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
                print("ch%d : analog %.2f mA, digital %.2f mA" % (channel, analog_current, digital_current))

                if (channel == 0) | (channel == 8) | (channel == 9):
                    pass
                channels_injected_count = channel + 1
                res['conditions'].append("channel_enabled_variation_no_dig_probe")
                res['RO_mode'].append("low_high_tdc")
                res['TDC_injected_count'].append(2 * channels_injected_count)
                res['TDC_injected'].append('both')
                res['channels_injected'].append(channels_injected_count)
                res['injection_freq'].append(freq)
                res['cluster_RO_enabled'].append(4)  # 0

                res['analog_current'].append(analog_current)
                res['digital_current'].append(digital_current)
                pass

    df = pd.DataFrame(res)
    df.to_csv(filepath, index=False)
    tempo.close()

    pass

def measure_power_consumption(tempo: temporoc3, config, visaController, method='serial_test'):

    # if method=='serial_test':
    # Goal : measure power consumption
    #  - steady state (after SC reset)
    #  - for different channel occupancy:  64/64, 32/64, 8/64
    #  - for different injection rate : 10, 50, 100 kHz


    # 150000  # 200000 # 78125 #20000
    res = {'analog_current': [],
           'digital_current': [],
           'conditions': [],
           'board': [],
           'RO_mode': [],
           'TDC_injected_count': [],
           'TDC_injected': [],
           'injection_freq_kHz': [],
           'cluster_RO_enabled': [],
           'channels_injected': [],
           'tempo_dig_ck_freq': []
        }

    print("Remove jumpers on both VDDD and VDDA")
    print("Connect FPGA external pulser by plugging jumper JU13 on the left (away from the SMA ext trigger)")

    if method == 'full':
        pass
        # # STATIC
        # tempo.pll.configure_PLL_no_clocks_except_FPGA()
        # time.sleep(0.5)
        # assert tempo.pll.check_is_locked()
        #
        # tempo.fpga.set.power_on_ASIC(0)
        # res['conditions'].append('asic off no clock')
        # res['cluster_RO_enabled'].append(0)
        # fill_dict()
        # digital_current, analog_current = visaController.get_current_consumption()
        # res['analog_current'].append(analog_current)
        # res['digital_current'].append(digital_current)


    # STATIC
    # tempo_dig_ck_freq = tempo.pll.dig_clock_freq
    tempo_dig_ck_freq = tempo.board_config['tempo_dig_ck']
    # tempo.init_board(tempo_dig_ck_freq=tempo_dig_ck_freq)
    # tempo.init_ASIC()
    # tempo.board_config['readout_mode'] = readout_mode
    # tempo.asic.interface.select.dig_modeRO(readout_mode)
    res['conditions'].append("asic on after reset with %d MHz clock"%tempo_dig_ck_freq)
    res['board'].append(tempo.board)
    res['RO_mode'].append(tempo.asic.interface.select.dig_modeRO.RO_str)
    res['TDC_injected_count'].append(0)
    res['TDC_injected'].append([])
    res['channels_injected'].append(0)
    res['injection_freq_kHz'].append(0)
    res['cluster_RO_enabled'].append(4)
    res['tempo_dig_ck_freq'].append(tempo_dig_ck_freq)
    digital_current, analog_current = visaController.get_current_consumption(decimal=0)
    res['analog_current'].append(analog_current)
    res['digital_current'].append(digital_current)

    # DYNAMIC
    # BEST case :
    # tempo.asic.ch.all().disable.all_discri()
    # tempo.asic.ch.all().disable.tdcH()
    # tempo.asic.ch.all().disable.tdcL()
    # visaController.get_current_consumption(decimal=0)
    # tempo.asic.interface.dis.tdc_ck()
    # visaController.get_current_consumption(decimal=0)


    # WORST case : threshold in the noise ?
    # tempo.asic.common.set.dacTL(200)
    # tempo.asic.common.set.dacTH(200)
    tempo.fpga.set.conv_syst_ASIC(1)
    time.sleep(0.1)
    res['conditions'].append("conv syst")
    res['board'].append(tempo.board)
    res['RO_mode'].append(tempo.asic.interface.select.dig_modeRO.RO_str)
    res['TDC_injected_count'].append(0)
    res['TDC_injected'].append([])
    res['channels_injected'].append(0)
    res['injection_freq_kHz'].append(0)
    res['cluster_RO_enabled'].append(4)
    res['tempo_dig_ck_freq'].append(tempo_dig_ck_freq)
    digital_current, analog_current = visaController.get_current_consumption(decimal=0)
    res['analog_current'].append(analog_current)
    res['digital_current'].append(digital_current)
    tempo.fpga.set.conv_syst_ASIC(0)


    if tempo.board_config['FPGA_PLL']:
        print("Can not execute the rest of the code without the external PLL operational!")
    else:
        # SETUP TEST SIGNAL : Setup FPGA pulser : forever pulser
        tempo.fpga.pulser.unmask_on_ext_trigger()
        # tempo.fpga.pulser.unmask_on_IO0()
        tempo.fpga.pulser.set_sync_mode()
        tempo.fpga.pulser.sync_enable_forever()
        tempo.asic.interface.en.ClkDataRO_cluster([0,1,2,3])

        # SWEEPING FREQUENCY to estimate TDC consumption
        enabled_ASIC_ch = list(range(64))
        tempo.asic.ch.group(enabled_ASIC_ch).select.trigTL.external()
        tempo.asic.ch.group(enabled_ASIC_ch).select.trigTH.external()
        tempo.asic.ch.all_except(enabled_ASIC_ch).disable.all_discri()
        tempo.asic.common.dis.latch() # allows triggering at high frequency !

        tempo.fpga.OUT7_select.ser_data(0)
        # tempo.asic.common.en.bypassResetMgmt()  # needed otherwise temporoc digital under reset (if ro_enable at 0) holds the trigger latch under reset
        # tempo.fpga.pulser.take_control_of_resetn_latch()

        # 20 MHz seems the maximum frequency reachable by the pulser on external trigger due to:
        # - resynchr DFF operated at 640 MHz: unlikely
        # - jumper causes an RC ?
        # - SN74AUP1T34DCKR (Single Ended 2v5 to 1v2) have a frequency limit to ? (propagation delay ~10 ns)
        # 40 MHz seen on IO0 but not on external trigger


        for injection_freq in [2, 20, 100, 200, 500, 1000, 2000, 10000, 20000]: # kHz
            pulser_divider = int(80e6/injection_freq/1e3)

            tempo.fpga.pulser.set_divider(pulser_divider)
            tempo.fpga.pulser.disable()
            tempo.fpga.pulser.launch()

            res['conditions'].append("64 channels injected at %.2f kHz - latch disabled "%injection_freq)
            res['board'].append(tempo.board)
            res['RO_mode'].append(tempo.asic.interface.select.dig_modeRO.RO_str)
            res['TDC_injected_count'].append(128)
            res['TDC_injected'].append(['low', 'high'])
            res['channels_injected'].append(64)
            res['injection_freq_kHz'].append(injection_freq)
            res['cluster_RO_enabled'].append(4)
            res['tempo_dig_ck_freq'].append(tempo_dig_ck_freq)
            digital_current, analog_current = visaController.get_current_consumption(decimal=0)
            res['analog_current'].append(analog_current)
            res['digital_current'].append(digital_current)


        # SWEEPING nb of channels injected
        injection_freq = 200 #kHz
        pulser_divider = int(80e6 / injection_freq / 1e3)
        tempo.fpga.pulser.set_divider(pulser_divider)
        tempo.asic.common.en.latch()

        # if number of injected cluster varies, does not change digital power conso !
        # for enabled_ASIC_ch in [list(range(16)), list(range(32)), list(range(48)), list(range(64))]:
        for enabled_ASIC_ch in  [list(range(0, 64, 8)), list(range(0, 64, 2)), list(range(64))]:
            tempo.asic.ch.group(enabled_ASIC_ch).select.trigTL.external()
            tempo.asic.ch.group(enabled_ASIC_ch).select.trigTH.external()
            tempo.asic.ch.all_except(enabled_ASIC_ch).disable.all_discri()
            tempo.asic.ch.all_except(enabled_ASIC_ch).select.trigTL.internal()
            tempo.asic.ch.all_except(enabled_ASIC_ch).select.trigTH.internal()
            time.sleep(0.1)

            channels_injected_count = len(enabled_ASIC_ch)
            res['conditions'].append("%d channels injected at %d kHz"%(channels_injected_count, injection_freq))
            res['board'].append(tempo.board)
            res['RO_mode'].append(tempo.asic.interface.select.dig_modeRO.RO_str)
            res['TDC_injected_count'].append(2*channels_injected_count)
            res['TDC_injected'].append(['low', 'high'])
            res['channels_injected'].append(channels_injected_count)
            res['injection_freq_kHz'].append(injection_freq)
            res['cluster_RO_enabled'].append(4)
            res['tempo_dig_ck_freq'].append(tempo_dig_ck_freq)
            digital_current, analog_current = visaController.get_current_consumption(decimal=0)
            res['analog_current'].append(analog_current)
            res['digital_current'].append(digital_current)

    df = pd.DataFrame(res)
    time_suffix = datetime.now().strftime('%H_%M_%S')


    df.to_csv(config['save_folder'] + 'conso_%s.csv'%time_suffix, index=False)


def measure_channel_DC_levels(tempo, config, visaController, method='serial_test'):

    print("Connect Keithley to JTAG.")
    print("Connect (on PCB) JTAG channels n°13 to ground with a small wire")
    print("Connect (on PCB) JTAG channels n°14 to analog probe test point (prior PCB buffer, aka not in SMA)") # 7

    tempo.asic.interface.en.analog_probe()

    if method == 'serial_test':
        channel_range = [0, 16, 31, 48, 63]
    elif method == 'full':
        channel_range = range(64)
    else:
        print("Unknown measurement method")
        exit()

    # DAC range check
    res_channel_DC_levels = {'channel': []}
    res_channel_DC_levels.update({analog_probe+'_mV_prior_PCB_buffer':[] for analog_probe in ['shH', 'shL', 'paLG', 'paHG']})

    for channel in channel_range:
        res_channel_DC_levels['channel'].append(channel)

        for analog_probe in ['shH', 'shL', 'paLG', 'paHG']:

            tempo.asic.ch(channel).select.analogProbe(analog_probe)
            analog_probe_mV_prior_PCB_buffer = visaController.get_channel_voltage(8) * 1e3

            res_channel_DC_levels[analog_probe+'_mV_prior_PCB_buffer'].append(analog_probe_mV_prior_PCB_buffer)

    df = pd.DataFrame(res_channel_DC_levels)
    time_suffix = datetime.now().strftime('%H_%M_%S')


    df.to_csv(config['save_folder'] + 'channel_DC_levels_%s.csv'%time_suffix, index=False)



def measure_inputDAC_dac_range(tempo, config, visaController, method='serial_test'):
    # Input dac range check for each channel via bypassed ctest sma input

    print("Connect Keithley to JTAG.")
    print("Connect (on PCB) JTAG channels n°20 to Ctest SMA")  # 10

    res_input_dac = {'channel': [],
                     'ch_input_dac': [],
                     'ch_input_mV': []}

    # bypass injection capacitor and 50 ohm resistor to ground to access input dac DC voltage
    tempo.asic.ch.all().disable.use_ctest()

    if method=="full":
        dac_range = range(2 ** 8)
        channel_range = range(64)
    elif method=="serial_test":
        dac_range = [0,255]
        channel_range = range(64) #[0, 16, 31, 48, 63] # goal : test DC path connected for all channels
    else:
        print("Unknown measurement method")
        exit()

    for ch in channel_range:
        # enable ctest for this given channel
        tempo.asic.ch(ch).enable.cmd_test()

        for dac in dac_range:
            tempo.asic.ch(ch).set.inDac(dac)
            res_input_dac['ch_input_dac'].append(dac)
            res_input_dac['channel'].append(ch)
            time.sleep(0.05)
            input_mV = visaController.get_channel_voltage(10) * 1e3
            res_input_dac['ch_input_mV'].append(input_mV)

        # disable ctest for this given channel
        tempo.asic.ch(ch).disable.cmd_test()

    df2 = pd.DataFrame(res_input_dac)
    time_suffix = datetime.now().strftime('%H_%M_%S')

    df2.to_csv(config['save_folder'] + 'inputDAC_range_per_channel_%s.csv'%time_suffix, index=False)


def measure_Vth1Q_dac_range(tempo, config, visaController, method='serial_test', dac_range=None):
    # measure DC voltages of dac1/dacq ranges
    # dac2 excluded for measuring internal voltages

    print("Connect Keithley to JTAG.")
    print("Connect (on PCB) JTAG channels n°13/15/17/19 to ground via small wires")
    # print("Connect (on PCB) JTAG channels n°14 to test point Vth2")     # 7
    print("Connect (on PCB) JTAG channels n°16 to test point Vth1")     # 8
    print("Connect (on PCB) JTAG channels n°18 to test point VthQ")     # 9

    if method=='full':
        dac_range = range(2**10)

    elif method=='serial_test':
        # Goal : measure the average slope + potential dac anomaly around 256
        dac_range = list(range(0,2**10,2**6))+[254, 255, 257, 258]
        # dac_range = [0,7,8,9,15,16,17]+list(range(70, 315))+[511,512,513,1023]
        # tempo.asic.bias.calibDac.Ib.set_4b(7)

    elif dac_range is not None:
        print("Using custom dac range provided")
        dac_range = dac_range

    else:
        print("Unknown measurement method")
        exit()

    # Vth DAC range check
    res_vth_dac = {'dac': [],
           'Vth1_mV': [],
           # 'Vth2_mV': [],
           'VthQ_mV': []}

    for dac in dac_range:
        # tempo.asic.common.set.dacTH(dac)
        tempo.asic.common.set.dacTL(dac)
        tempo.asic.common.set.dacQ(dac)
        res_vth_dac['dac'].append(dac)
        time.sleep(0.05)

        # Vth2 = visaController.get_channel_voltage(7)*1e3
        Vth1 = visaController.get_channel_voltage(8)*1e3
        VthQ = visaController.get_channel_voltage(9)*1e3

        # res_vth_dac['Vth2_mV'].append(Vth2)
        res_vth_dac['Vth1_mV'].append(Vth1)
        res_vth_dac['VthQ_mV'].append(VthQ)

    df1 = pd.DataFrame(res_vth_dac)
    time_suffix = datetime.now().strftime('%H_%M_%S')


    df1.to_csv(config['save_folder'] + 'Vth12Q_dac_range_%s.csv'%time_suffix, index=False)



def measure_BG(tempo, config, visaController, method='quick'):
    print("Start measuring BG")
    # DAC range check
    res_BG_dac = {'bias_1V_dac': [],
                  'bias_1V_mV': [],
                  'BG_dac': [],
                  'BG_mV': [],
                  "temp_mV": []}

    start = time.time()

    if method=='temperature_test':
        bias_1V_dac_range = [0, 15]
        BG_dac_range = range(16)
    elif method=='extensive':
        bias_1V_dac_range = range(16)
        BG_dac_range = range(16)
    elif method=='serial_test':
        # Goal : find the best value for the 1V reference voltage
        bias_1V_dac_range = range(16)
        BG_dac_range = [8]
    else:
        print("Unknown BG measurement method")
        exit()

    for BG_dac in BG_dac_range:
        tempo.asic.common.set.BG(BG_dac)

        for bias_1V_dac in bias_1V_dac_range:
            tempo.asic.common.set.bias_1V(bias_1V_dac)

            res_BG_dac['bias_1V_dac'].append(bias_1V_dac)
            res_BG_dac['BG_dac'].append(BG_dac)

            # reversed polarity on PCB
            BG_mV = -visaController.get_channel_voltage(6) * 1e3
            temp_mV = -visaController.get_channel_voltage(5) * 1e3  # labeled by mistake Vref_1V on the PCB & datasheet
            bias_1V_mV = -visaController.get_channel_voltage(4) * 1e3

            res_BG_dac['BG_mV'].append(BG_mV)
            res_BG_dac['bias_1V_mV'].append(bias_1V_mV)
            res_BG_dac['temp_mV'].append(temp_mV)

    stop = time.time()
    print("End measuring BG elapsed time: %d s" % (stop - start))
    df = pd.DataFrame(res_BG_dac)
    time_suffix = datetime.now().strftime('%H_%M_%S')



    df.to_csv(config['save_folder'] + 'BG_dac_range_%s.csv'%time_suffix, index=False)



def temperature_BG_check(board, combined_test=False):
    pass

# def temperature_BG_check(board, combined_test=True):

    # measure BG, Vbias_1V, Vref_1V = temp
    print("Connect Keithley to JTAG.")
    print("Plug jumpers on both VDDD and VDDA to short shunt resistor")

    visaController = tools.visaController(16)
    visaController.setup_DC_voltage()

    config = {'board': [board], 'config_B%d'%board: {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/combined_BG_TDC_tests/"
    find_new_folder_index(local_output_dir, config)

    if combined_test:
        tempo = setup_combined_test(config)
        reset_FPGA_FIFO_and_tempo_digital([tempo])
        tempo.save_ASIC_and_FPGA_config(config)

        number_times_fifo_empty = 2000000
        expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count / 8 + 9  # + 9 bytes including 32 bits ovf counter
        fifo_max_number_events = round(2 ** 15 / expected_bytes_per_event)

        acquire_data_multi_boards(number_times_fifo_empty * fifo_max_number_events, config, [tempo])

        # period_in_minutes = 2
        # timer = threading.Timer(60 * period_in_minutes, measure_BG, [tempo, config, visaController])
        # timer.start()
        #
        # t = threading.Thread(acquire_data_multi_boards(number_times_fifo_empty * fifo_max_number_events, config, [tempo]))
        # t.run()


    else:
        tempo = temporoc3(config)
        enabled_ASIC_ch = list(range(64))
        setup_temporoc([tempo], config)
        tempo.save_ASIC_and_FPGA_config(config)

        measure_BG(tempo, config, visaController, method='temperature_test')



    tempo.close()

    pass


def temporoc_test_sc_communication(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)
    tempo.init_board()

    for n in range(1000):
        addr = random.randint(0, 67)
        if addr<64:
            sudaddr_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 65, 66]
            subaddr = random.choice(sudaddr_list)
        elif addr==64:
            subaddr = random.randint(0, 18)
        elif addr == 65:
            subaddr = random.randint(0, 19)
        elif addr == 66:
            subaddr = random.randint(0, 6)
        else: # addr == 67:
            subaddr = random.randint(0, 3)

        data = random.randint(0, 255)
        tempo.dev.i2c.write_register(addr, subaddr, data)

    tempo.asic.i2c.SC_details()
    tempo.asic.i2c.SC_stats()
    tempo.close()

def temporoc_test_reg_communication(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)
    tempo.init_board()

    error = 0
    N = 1000000
    for n in range(N):
        addr_list = [4, 6, 69]
        addr = random.choice(addr_list)
        data = random.randint(0, 255)
        tempo.dev.write_word(addr, data)
        val = tempo.dev.read_word(addr)
        if val != data:
            print(addr)
            error += 1
    print("%d (%.2f %%) errors found over %d tests" % (error, error/N*100, N))
    tempo.close()


def temporoc_test_mode(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    tempo = temporoc3(config)
    tempo.init_board()

    local_output_dir = "../output/basic/test_mode/"

    # find unique new file index
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
    print("Will save events with index %d" % new_file_index)

    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.asic.interface.set.nb_trigger(31)
    tempo.asic.interface.select.dig_modeRO.test()

    cluster = 0
    bytes_count = tempo.deserializer.get_number_of_bytes_in_fifo(cluster)
    expected_bytes_per_event = tempo.asic.interface.select.dig_modeRO.RObit_count // 8
    events_asked = bytes_count // expected_bytes_per_event

    local_filepath = local_output_dir + "%d_B%d.csv" % (new_file_index, board)
    status = tempo.deserializer.extract_data(events_asked, cluster, local_filepath, verbose=True)
    pass



def scan_frame_count_versus_nb_trigger_vs_injected_channels(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}

    output_dir = "../output/basic/"
    scopeLecroy = tools.lecroyOscilloDAQ("192.168.2.21")

    # have to choose parameters:
    # - send_rstn_latch_after_pulser
    # - dig clock frequency
    # - both trigger gain or low or high

    send_rstn_latch_after_pulser = False
    # send_rstn_latch_after_pulser = True # no need, degrades results

    gain_type = 'low' #'high'


    tempo = temporoc3(config)
    # tempo_dig_clock, external_hit = tempo.pll.configure_PLL_sync_ext_trigger()
    # tempo_dig_clock, external_hit = tempo.pll.configure_PLL_40M_dig_ck()
    # tempo_dig_clock, external_hit = tempo.pll.configure_PLL_80M_dig_ck()
    tempo_dig_clock, external_hit =  tempo.pll.configure_PLL_160M_dig_ck()

    # scopeLecroy.save_setup("scan_frame_count_versus_nb_trigger_vs_injected_channels_dig_ck_%dMHz.lss"%tempo_dig_clock)
    scopeLecroy.load_setup("scan_frame_count_versus_nb_trigger_vs_injected_channels_dig_ck_%dMHz.lss"%tempo_dig_clock)
    scopeChannelforEdgeCount = 1
    cluster = 0

    print("SCOPE lecroy\nCH1 : FPGA IO8 dig probe latched trigger\nCH2 : FPGA IO7 ser clk cluster %d\nExt trigger : FPGA IO0 FPGA pulser"%cluster)
    print("Power on for both VDDD and VDDA")
    results = {'injected_enabled_channels':[], 'nb_channels_enabled_injected':[], 'tdc_injected':[], 'power_cluster':[],
               'nb_trigger':[], 'readout_mode':[], 'repeat':[], 'ck_edge_count_mean':[], 'ck_edge_count_sdev':[]}
    config = {'tempo_dig_ck':[], 'VDDD':[], 'board':[], 'hit_freq':[],  'FPGA':[], 'fw_version_major':[], 'fw_version_minor':[], 'fw_hash':[], 'test':[]}

    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()
    # tempo.fpga.set.FPGA_as_clock_source()

    tempo.reset_power_check_correct_clock_init()

    tempo.asic.ch.all().disable.front_end()
    tempo.asic.common.set.dacTL(1023)
    tempo.asic.common.set.dacTH(1023)
    tempo.asic.common.set.dacQ(1023)

    #  test 1
    # channel = 0
    # cluster = channel//16
    # tempo.asic.interface.dis.ClkDataRO_cluster([1, 2, 3])
    # channel_label= str(channel)

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()
    tempo.fpga.pulser.set_sync_mode()
    repeat = 7
    # tempo.FPGA.pulser.set_async_feedthrough_mode()
    tempo.fpga.pulser.set_nb_impulsions(repeat)

    if (tempo_dig_clock==320) or (tempo_dig_clock==160):
        tempo.fpga.pulser.set_frequency_in_Hz(39062.5)

    if tempo_dig_clock == 40:
        tempo.fpga.pulser.set_frequency_in_Hz(80e6 / 2048 / 2 / 4)


    # tempo.FPGA.pulser.set_frequency_in_Hz(78125) # not higher otherwise temporoc has not enough time to TX data
    if send_rstn_latch_after_pulser:
        tempo.asic.common.en.bypassResetMgmt()
        tempo.fpga.pulser.take_control_of_resetn_latch()
        if tempo_dig_clock==320:
            tempo.fpga.pulser.set_reset_delay_in_ns(1834)
        if tempo_dig_clock == 160:
            tempo.fpga.pulser.set_reset_delay_in_ns(2279)
        config['test'].append("forcing resetn_latch when pulsing gain="+gain_type)

    else:
        tempo.fpga.pulser.release_resetn_latch()
        config['test'].append("temporoc default behavior (resetn_latch handled internally) gain="+gain_type)

    freq = tempo.fpga.pulser.get_frequency_in_Hz()
    config['hit_freq'].append(freq)
    
    config['board'].append(board)
    config['tempo_dig_ck'].append(tempo_dig_clock)

    # delay box should be inhibited because Temporoc internal digital
    tempo.asic.interface.en.Inh_rstOnDlyH()
    tempo.asic.interface.en.Inh_rstOnDlyL()

    local_output_dir = output_dir + "/frame_count/dig_ck_%d_MHz/raw/"%tempo_dig_clock
    new_index, local_output_dir = find_new_folder_index(local_output_dir, config)

    # debug: check if reset cluster works from analog instead of digital
    tempo.asic.interface.en.digital_probe()

    # tempo.asic.common.probeDig.cluster(0).end_delayL()
    # tempo.asic.common.probeDig.cluster(0).rstn_delaybox()

    # tempo.asic.common.probeDig.cluster(0).rstnLatchInt()

    tempo.fpga.OUT5.en_ck40M()
    # tempo.IO.IO8_select.or_trig_l_rs()
    # tempo.IO.IO8_select.ser0_clk()
    tempo.fpga.OUT8_select.digit_probe()
    # tempo.IO.IO7_select.ser0_data()
    tempo.fpga.OUT7_select.ser_clk(cluster)
    tempo.fpga.OUT1.en_ck320()

    tempo.asic.interface.en.Nor_TrigT_L_RS()

    tempo.fpga.set.val_evt_ASIC(1)
    tempo.asic.common.en.latch()
    tempo.fpga.set.ro_enable_ASIC(1)
    tempo.fpga.set.delay_ext_trigger(0)

    readout_mode_list = ['full_adc_tdc'] #,'lg_adc_low_tdc', 'hg_adc_low_tdc']   #, 'low_high_tdc', 'low_tdc', ]:

    for mode in readout_mode_list:

        tempo.asic.interface.select.dig_modeRO(mode)
        print(tempo.asic.interface.select.dig_modeRO.RO_str)

        for nb_channels_enabled_injected in range(17):#[1] 17 to have all combinations for one cluster

            injected_enabled_channels = list(range(cluster * 16, cluster * 16 + nb_channels_enabled_injected))
            tempo.asic.ch.group(injected_enabled_channels).select.trigTL.external()
            tempo.asic.ch.group(injected_enabled_channels).select.trigTH.external()

            if gain_type=='both':
                tempo.asic.ch.group(injected_enabled_channels).enable.TH()
                tempo.asic.ch.group(injected_enabled_channels).enable.TL()
            elif gain_type == 'low':
                tempo.asic.ch.group(injected_enabled_channels).disable.TH()
                tempo.asic.ch.group(injected_enabled_channels).enable.TL()
            elif gain_type == 'high':
                tempo.asic.ch.group(injected_enabled_channels).enable.TH()
                tempo.asic.ch.group(injected_enabled_channels).disable.TL()

            not_injected_channels_within_cluster = list(set( injected_enabled_channels) ^ set(range(cluster * 16, (cluster+1) * 16)))
            tempo.asic.ch.group(not_injected_channels_within_cluster).disable.all_discri()

            if len(injected_enabled_channels)>0:
                probed_channel = injected_enabled_channels[-1]
                if (gain_type == 'both') or (gain_type == 'low'):
                    tempo.asic.common.probeDig.channel(probed_channel).TrigT_L_RS()
                if gain_type == 'high':
                    tempo.asic.common.probeDig.channel(probed_channel).TrigT_H_RS()

            for nb_trigger in reversed(range(32)):# [26]: # #32
                scopeLecroy.clearSweep()
                time.sleep(0.05)

                tempo.asic.interface.set.nb_trigger(nb_trigger)
                if not send_rstn_latch_after_pulser:
                    tempo.fpga.reset.latch_force(tempo.asic)
                results['nb_trigger'].append(nb_trigger)
                results['injected_enabled_channels'].append(injected_enabled_channels)
                results['nb_channels_enabled_injected'].append(nb_channels_enabled_injected)
                results['tdc_injected'].append('both')
                results['power_cluster'].append(cluster)
                results['readout_mode'].append(mode)
                results['repeat'].append(repeat)

                for i in range(5):
                    tempo.fpga.pulser.launch()
                    time.sleep(0.05) # crutial

                avg = scopeLecroy.getMeasure(scopeChannelforEdgeCount, 'mean')
                std = scopeLecroy.getMeasure(scopeChannelforEdgeCount, 'sdev')
                print(nb_channels_enabled_injected, nb_trigger, avg)

                if avg>(5*1043*7):
                    pass
                results['ck_edge_count_mean'].append(avg)
                results['ck_edge_count_sdev'].append(std)

    pd.DataFrame(results).to_csv(local_output_dir+'frame_count.csv', index=False)

    tempo.save_ASIC_and_FPGA_config(config)


    # config_file = local_output_dir%(new_file_index, 'config.json')
    # with open(config_file, 'w') as fout:
    #     json.safe_dump(config, fout)
    # fout.close()
    tempo.close()

    pass


def test_temperature(board):

    config = {'board': [board], 'config_B6': {'board': board, 'mode': 'master'}}

    local_output_dir = "../output/basic/DC/"
    find_new_folder_index(local_output_dir, config)

    tempo = temporoc3(config)
    enabled_ASIC_ch = list(range(64))
    setup_temporoc([tempo], config)
    print(tempo.temperature_sensor.read_temperature())

    pass


    
if __name__ == '__main__':
    pass

    # delaybox_scan()
    # delete_inherited_registers()
    # read_compare_default_HW_SC()
    # dac_range_check(skip=True)

    # temperature_BG_check(2)
    # test_temperature(6)

    # channel_DC_levels()

    # temporoc_test_mode()
    # temporoc_test_sc_communication()
    # temporoc_test_reg_communication()
    # scan_frame_count_versus_nb_trigger_vs_injected_channels()