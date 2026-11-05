import glob
import re

from src import tools
from src.temporoc3 import *
import matplotlib
import pandas as pd

# https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_manuals/user_manual/1335_9090_01/RTM3000_UserManual_en_10.pdf
from RsInstrument import LoggingMode, RsInstrument
from packaging import version

# matplotlib.use('Qt5Agg')
font = {'size'   : 10}
matplotlib.rc('font', **font)
from analyse.common_analysis_TDC import frequency_planner

output_dir = '../output/standalone_tdc/'
# Do not put digital under reset (otherwise standalone TDC will also be under reset)


def setup_teledyne_scope_visa():
    import pyvisa

    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    scope = rm.open_resource(resources[0])

    print(scope.query("""vbs? 'return=app.measure.p0.mean.result.value' """))
    return scope

def setup_RS_scope():


    dev = RsInstrument.list_resources('?*', 'rs')
    print("Scope available : "+dev[0])
    try:
        # Adjust the VISA Resource string to fit your instrument
        mxo = RsInstrument(dev[0], id_query=True, reset=True, options="SelectVisa='rs'")
        fw_version = version.parse(mxo.instrument_firmware_version)
        if fw_version < version.parse("1.4"):
            raise Exception(f"Your instrument has an older FW Version ({fw_version}) not supported by this example. "
                            f"The minimum supported version is 1.4.2.2. Please make a FW update")
        mxo.logger.mode = LoggingMode.On
        mxo.visa_timeout = 5000  # Timeout for VISA Read Operations
        mxo.opc_timeout = 8000  # Timeout for opc-synchronised operations
        mxo.instrument_status_checking = True  # Error check after each command
        mxo.write('*RST')

        # Horizontal and Vertical settings
        mxo.write('CHANnel1:STATe ON')
        mxo.write('CHANnel1:POSITION -3')
        mxo.write('CHANnel1:RANGe 2')
        mxo.write('CHANnel1:COUPling DCLimit')
        mxo.write('TIMebase:SCALe 5E-9')

        mxo.write('CHANnel3:STATe ON')
        mxo.write('CHANnel3:RANGe 5') # 500 mV
        mxo.write('CHANnel3:COUPling ACLimit')

        # Trigger settings
        mxo.write('TRIGger:A:MODE NORM')
        mxo.write('TRIGger:A:SOURce CH1')
        mxo.write('TRIGger:A:TYPE EDGE')
        mxo.write('TRIGger:A:EDGE:SLOPe NEG')
        mxo.write('TRIGger:A:LEVel1:VALue 0.9')

        # Measurements settings
        mxo.write('MEASurement1:MAIN DELay')
        mxo.write('MEASurement1:SOURCE CH1,CH3')
        mxo.write('MEASurement1:DELay:SLOpe NEG,NEG')
        mxo.write('MEASurement1:DELay:DIR NEAR,NEAR')
        mxo.write('MEASurement1:ENABle ON')
        mxo.write('MEASurement1:STAT:ENABle ON')

        # scope.write('&GTL')
        # scope.close()
    except Exception as ex:
        print('Error initializing the instrument session:\n' + ex.args[0])
        exit()
    return mxo

# 1. TDC scan with sync hit delayed by 10 ps step for measuring absolute LSB
def tdc_scan_delaybox_step(board, use_scope_lecroy=True, use_scope_RS=False):

    if use_scope_lecroy:
        scopeLecroy = tools.lecroyOscilloDAQ("192.168.2.21")
        # scopeLecroy.save_setup("delay_box_carac.lss")
        scopeLecroy.load_setup("delay_box_carac.lss")

    if use_scope_RS:
        scopeRS = setup_RS_scope()

    print("Unpower temporoc digital VDDD removing jumper J6 and resistance R62, since both TDC & SC are supplied by VDDA")
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    tempo = temporoc3(config)

    tempo.pll.configure_PLL_sync_ext_trigger()
    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()

    tempo.reset_power_check_correct_clock_init()


    tempo.asic.interface.dis.ck320()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])

    local_output_dir = output_dir + "delaybox_step/raw/"
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    tempo.asic.interface.dis.TDC_passthrough()
    # tempo.asic.interface.en.TDC_passthrough()

    # options
    N = 100
    board = int(tempo.dev.device.getDeviceInfo()['serial'][4:-1])
    VDDD = 1.3 if board==1 else 1.2

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()
    # tempo.FPGA.pulser.disable()
    tempo.fpga.pulser.set_sync_mode()
    # tempo.FPGA.pulser.set_async_feedthrough_mode()
    tempo.fpga.pulser.set_nb_impulsions(N)
    tempo.fpga.pulser.set_frequency_in_Hz(1.25e6)

    freq = tempo.fpga.pulser.get_frequency_in_Hz()
    options = "B%d_hitFreq_%d_N_%d"%(board, freq, N)

    # debug
    tempo.fpga.OUT7_select.pulse_tdc()
    tempo.fpga.OUT8_select.tdc_dat_val()
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT1.en_ck320()
    # check pulser
    # print(bin(tempo.dev.read_word(REGISTERS.addr_test_tdc_config)))

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

    oscillo_delay_carac = {'delay':[], 'oscilloDelay_mean': [], 'oscilloDelay_std': []}

    nb_delays = 2**10 # 100
    # with alive_bar(nb_delays) as bar:  # your expected total
    for delay in range(nb_delays):
        if scopeRS:
            scopeRS.write('MEASurement1:STAT:RESET')
        if use_scope_lecroy:
            scopeLecroy.clearSweep()
        time.sleep(0.2)
        tempo.deserializer.reset_fifo_standalone_TDC()
        tempo.fpga.set.delay_ext_trigger(delay)

        while 1:
            tempo.fpga.pulser.launch()
            time.sleep(1)

        # temperature = tempo.temperature_sensor.read_temperature()
        temperature = 0
        tempo.deserializer.extract_data_standalone_tdc(N, filepath, delay, temperature)

        if use_scope_RS:
            avg = scopeRS.query_float_with_opc('MEASurement1:RESult:AVG?')
            std = scopeRS.query_float_with_opc('MEASurement1:RESult:STDDev?')

        time.sleep(0.2)
        if use_scope_lecroy:
            avg = scopeLecroy.getMeasure(1, 'mean')*1e12
            std = scopeLecroy.getMeasure(1, 'sdev')*1e12

        if use_scope_RS or use_scope_lecroy:
            print("delay %d : avg=%d ps, std=%d ps" % (delay, avg, std))
            oscillo_delay_carac['delay'].append(delay)
            oscillo_delay_carac['oscilloDelay_mean'].append(avg)
            oscillo_delay_carac['oscilloDelay_std'].append(std)

            # bar()
    oscillo_delay_folder = local_output_dir + "oscillo_delay"
    oscillo_delay_filename = oscillo_delay_folder + "/B%d.csv"%board
    if not os.path.exists(oscillo_delay_folder):
        os.makedirs(oscillo_delay_folder)
    pd.DataFrame(oscillo_delay_carac).to_csv(oscillo_delay_filename, index=False)

    # analyse_linearity_quick_file(filepath)
    # analyse_oscillo_delay(oscillo_delay_filename)
    # analyse_linearity(local_output_dir)
    tempo.close()




# 2. TDC scan with random hit for measuring non-linearities
def tdc_scan_code_density(board, required_events = 1e5):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    print("Unpower temporoc digital VDDD removing jumper J6 and resistance R62, since both TDC & SC are supplied by VDDA")
    tempo = temporoc3(config)

    # PLL_config_file = "Si5345_3_hit_1150000_Hz_CK_2300000_Hz.txt"
    # PLL outputs
    # 0 : FPGA clock : 1.15M (= #8/2) (not a multiple of 320M)
    # 3 : FPGA clock : 320M
    # 6 : TEMPOROC digital : 320M
    # 7 : external hit : 2.3M
    # 8 : standalone TDC ck : 320M


    # PLL_config_file = "Si5345_7_hit_9000000_Hz_CK_18000000_Hz-Registers.txt"
    # PLL outputs
    # 0 : FPGA clock : 9M (= #8/2)  (not a multiple of 320M)
    # 3 : FPGA clock : 320M
    # 6 : TEMPOROC digital : 320M
    # 7 : external hit : 18M
    # 8 : standalone TDC ck : 320M


    # PLL_config_file = "Si5345_8_hit_450000_Hz_CK_900000_Hz-Registers.txt"
    # PLL outputs
    # 0 : FPGA clock : 450 kHz (= #8/2)  (not a multiple of 320M)
    # 3 : FPGA clock : 320M
    # 6 : TEMPOROC digital : 320M
    # 7 : external hit : 900 kHz
    # 8 : standalone TDC ck : 320M

    PLL_config_file = "Si5345_9_hit_15000000_Hz_CK_30000000_Hz-Registers.txt"
    # PLL outputs
    # 0 : FPGA clock : 15M (= #8/2)  (not a multiple of 320M)  # max 25 MHz
    # 3 : FPGA clock : 320M
    # 6 : TEMPOROC digital : 320M
    # 7 : external hit : 30M
    # 8 : standalone TDC ck : 320M

    tempo.pll.flash("config/PLL/" + PLL_config_file)

    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()
    tempo.fpga.set.power_on_ASIC(1)
    tempo.fpga.reset.all_temporoc()
    time.sleep(0.3)
    assert tempo.pll.check_is_locked()

    tempo.asic.interface.dis.ck320()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.asic.interface.dis.TDC_passthrough()
    # tempo.asic.interface.en.TDC_passthrough()

    local_output_dir = output_dir + "code_density/"
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # options
    
    hitFreq = int(re.findall("(?<=hit_)[0-9]+", PLL_config_file)[0])
    CK_freq = int(re.findall("(?<=CK_)[0-9]+", PLL_config_file)[0])

    options = "B%d_hit_%d_Hz_CK_%d_Hz" % (board, hitFreq, CK_freq)

    # Setup FPGA pulser
    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.mask_on_ext_trigger()
    tempo.fpga.pulser.set_async_feedthrough_mode()

    # debug
    tempo.fpga.OUT8_select.tdc_dat_val()
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT1.en_ck320()

    filepath = local_output_dir + "%d_%s.csv"
    file_list = glob.glob(local_output_dir + '/*.csv')
    if not file_list:
        new_file_index = 0
    else:
        new_file_index = int(re.findall("[0-9]+(?=_B)", file_list[-1])[0]) + 1
    filepath = filepath % (new_file_index, options)
    print("will save events in file %s" % filepath)

    total_received_events = 0
    fifo_size = 2**14
    fifo_max_number_events = fifo_size//7   # 7 bytes per events
    # 2303 max in practice

    number_acquistions = round(required_events/fifo_max_number_events)
    for i in range(number_acquistions):
        tempo.deserializer_standalone_TDC.reset_fifo_standalone_TDC()
        tempo.fpga.pulser.unmask_on_ext_trigger()

        time.sleep(1) # whatever time needed to get the required number of events
        temperature = 0
        received_events = tempo.deserializer_standalone_TDC.get_number_of_events_in_FIFO_stdalone_tdc()
        total_received_events += received_events

        # assert received_events == fifo_max_number_events
        tempo.deserializer.extract_data_standalone_tdc(fifo_max_number_events, filepath, None, temperature)
        print("%d/%d : %d events received in total " % (i, number_acquistions, total_received_events))

    tempo.close()


# 3. TDC scan with async hit
def tdc_scan_custom_step(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    # frequency_planner(16e6, 2e-12)
    expected_step, ck_cycles_in_between_2_hits = frequency_planner(8e6, 4e-12)

    # select_FPGA_as_clock_source

    print("Unpower temporoc digital VDDD removing jumper J6 and resistance R62, since both TDC & SC are supplied by VDDA")
    tempo = temporoc3(config)

    # tempo.pll.configure_PLL_async_ext_trigger()

    # PLL_config_file = "Si5345_5_hit_1250003_Hz_CK2500006_Hz_step_2ps.txt"
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

    tempo.pll.flash("config/PLL/" + PLL_config_file)


    tempo.fpga.select.ck_from_FPGA_to_PLL.cristal_100MHz()
    tempo.fpga.select.ck_from_FPGA_to_ASIC.PLL_OUT3()
    tempo.fpga.set.PLL_as_clock_source()
    tempo.fpga.set.power_on_ASIC(1)
    tempo.fpga.reset.all_temporoc()
    time.sleep(0.3)
    assert tempo.pll.check_is_locked()

    tempo.asic.interface.dis.ck320()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.interface.dis.ClkDataRO_cluster([0, 1, 2, 3])
    tempo.asic.interface.dis.TDC_passthrough()
    # tempo.asic.interface.en.TDC_passthrough()
    delay = 1500//(10*4) # arbitrary value but insure constant constant value between acquisition
    # shift by 1.5 ns to have the TDC carac centered
    tempo.fpga.set.delay_ext_trigger(delay)

    local_output_dir = output_dir + "custom_step/"
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    # options
    
    hitFreq = int(re.findall("(?<=hit_)[0-9]+", PLL_config_file)[0])
    CK_freq = int(re.findall("(?<=CK_)[0-9]+", PLL_config_file)[0])

    options = "B%d_hit_%d_Hz_CK_%d_Hz_step_%dps_delay_%d" % (board, hitFreq, CK_freq, expected_step*1e12, delay)

    # Setup FPGA pulser
    tempo.fpga.pulser.mask_on_IO0()
    tempo.fpga.pulser.mask_on_ext_trigger()
    tempo.fpga.pulser.set_async_feedthrough_mode()

    # debug
    tempo.fpga.OUT8_select.tdc_dat_val()
    tempo.fpga.OUT5.en_ck40M()
    tempo.fpga.OUT1.en_ck320()

    # check pulser
    # print(bin(tempo.dev.read_word(REGISTERS.addr_test_tdc_config)))

    # find unique file number
    filepath = local_output_dir + "%d_%s.csv"
    file_list = glob.glob(local_output_dir + '/*.csv')
    if not file_list:
        new_file_index = 0
    else:
        new_file_index = int(re.findall("[0-9]+(?=_B)", file_list[-1])[0]) + 1
    filepath = filepath % (new_file_index, options)
    print("will save events in file %s" % filepath)

    tempo.deserializer_standalone_TDC.reset_fifo_standalone_TDC()

    tempo.fpga.pulser.unmask_on_IO0()
    tempo.fpga.pulser.unmask_on_ext_trigger()

    # temperature = tempo.temperature_sensor.read_temperature()
    temperature = 0
    time.sleep(2)
    N = tempo.deserializer_standalone_TDC.get_number_of_events_in_FIFO_stdalone_tdc()
    print("%d events received "%N)
    tempo.deserializer.extract_data_standalone_tdc(N, filepath, None, temperature)

    # This measure requires a given minimum of consecutive hits to cover the full TDC dynamic range depending on the step chosen
    # There is a trade-off between the hit frequency and the step precision (spoiled by the PLL jitter) :
    # a lower sub-frequency delta between hit and TDC 320M clock implies a higher jitter
    tempo.close()







if __name__ == "__main__":
    tdc_scan_delaybox_step(1)
    # analyse_oscillo_delay("../output/tdc_scan/standalone_tdc/delaybox_step/oscillo_delay/B1.csv")
    # analyse_linearity_quick_file("../output/tdc_scan/standalone_tdc/delaybox_step/1_B2_VDDD_1.2V_hitFreq_1M25_N_100.csv")

    # tdc_scan_custom_step()


    # tdc_scan_code_density(1e5)
    # analyse_code_density(output_dir+"code_density/0_B2_VDDD_1.2V_hit_1150000_Hz_CK_2300000_Hz.csv")