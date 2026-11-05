# test acquisition peak detector HG and LG
# with external ADCs (on PCB)

from src.temporoc3 import *
from src.tools import *
from analyse.common_analysis_TDC import *



def acquire_pdet_with_ext_ADC(board):
    config = {'board': [board], 'config_B%d' % board: {'board': board, 'mode': 'master'}}
    tempo = temporoc3(config)
    tempo.init_board()
    tempo.correct_default_HW_SC()


    channel = 1
    cluster = channel//16
    local_output_dir = "../output/charge_scan/ch%d/raw/"%channel

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

    
    Cinj = 100e-12
    df_filepath = local_output_dir + "%d_B%d_Cinj_%dpF_adc_externe.csv" % (new_file_index, board, Cinj*1e12)

    tempo.asic.ch.all().disable.TQ()
    tempo.asic.ch.all().disable.all_discri()
    tempo.asic.ch(channel).enable.TH()# On enable le trigger H du channel under test
    tempo.asic.ch(channel).enable.TL()
    #tempo.asic.ch(channel).select.trigTH.external() # On connecte le trigger H du channel under test sur trigext
    tempo.asic.ch(channel).select.trigTH.internal()
    tempo.asic.ch(channel).select.trigTL.internal()
    tempo.asic.interface.set.nb_trigger(31) # cluster valid


    # tempo.asic.interface.en.sync_cluster()  # not required : only if Cluster specific data conversion
    tempo.asic.interface.dis.ClkDataRO_cluster([1, 2, 3])

    #Digital readout enable and Force conversion settings
    tempo.fpga.set.ro_enable_ASIC(1)

    # Time PA gain
    tempo.asic.ch(channel).set.patGain(8)
    tempo.asic.ch(channel).set.patComp(3)

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
    tempo.asic.common.set.dacTL(300)
    tempo.asic.common.set.dacQ(1023)

    # Shaper and Peak Detector setting
    tempo.asic.ch(channel).enable.pdetHG()
    tempo.asic.ch(channel).enable.pdetLG()
    tempo.asic.common.set.delay_pdet(2**8-1)
    tempo.asic.common.select.trigger.local_time_high()
    tempo.asic.bias.pdbuf.enable()
    tempo.asic.bias.sh.HG.enable()
    tempo.asic.bias.sh.LG.enable()
    tempo.asic.ch(channel).set.tauHG(1)
    tempo.asic.ch(channel).set.pahgGain(10)
    tempo.asic.ch(channel).set.tauLG(1)
    tempo.asic.ch(channel).set.palgGain(10)

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
    tempo.asic.interface.en.LG_pdet_MUX_output()
    tempo.asic.interface.en.HG_pdet_MUX_output()
    #tempo.asic.common.probeDig.channel(channel).TrigT_H()
    #tempo.asic.common.probeDig.channel(channel).TH()
    #tempo.asic.common.probeDig.channel(channel).TrigT_H_RS()
    tempo.asic.common.probeDig.channel(channel).TrigT_L_RS()
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

    ext_pulser = tektronix_AFG()

    res = {'Vinj_mV': [],
           'iter': [],
           'pdet_LG': [],
           'pdet_HG': []
           }

    tempo.fpga.set.hit_register_channel(channel)
    tempo.asic.common.en.bypassResetMgmt()
    tempo.fpga.reset.tpr_latch()
    ext_pulser.AFG.write("SOURce1:BURSt:NCYCles 1")

    for Vinj in range(100, 1000, 100):
        # charge injection with async external pulser through a cap of 100 pF
        # Qinj = 10 pC = 100 mV * 100 pF

        ext_pulser.set_voltage_amplitude(Vinj)
        tempo.fpga.reset.tpr_latch() # needed because changing the amplitude of the pulser triggers the channel...
        time.sleep(0.1)

        for i in range(10):
            ext_pulser.trigger()
            res['pdet_LG'].append(tempo.read_external_LG_ADC())
            res['pdet_HG'].append(tempo.read_external_HG_ADC())
            res['Vinj_mV'].append(Vinj/10)
            res['iter'].append(i)

            tempo.fpga.reset.tpr_latch()

    df = pd.DataFrame(res)
    df.to_csv(df_filepath, index=False)
    tempo.close()

if __name__=="__main__":
    acquire_pdet_with_ext_ADC(1)