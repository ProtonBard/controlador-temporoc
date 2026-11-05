import glob
import math
import os
import re

import numpy as np

from src.temporoc3 import *
import src.tools as tools
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
output_dir = '../output/standalone_adc/'

# Linearity test

def measure_dac_dynamic_range():
    tempo = temporoc3(config)
    tempo.init_board()

    tempo.external_DAC.set_dac_VinP(0)
    tempo.external_DAC.set_dac_VinN(0)
    # measure min voltage with multimeter at the 60 Ohm resistance R303

    tempo.external_DAC.set_dac_VinP(2**12-1)
    tempo.external_DAC.set_dac_VinN(2**12-1)
    # measure max voltage with multimeter at the 60 Ohm resistance R307

    # save to csv file 'board', 'max_dac_VinP', 'max_dac_VinN', 'min_dac_VinP', 'min_dac_VinN'
    tempo.close()

def adc_static_scan():
    # control the 2 dac in opposite direction, read ADC N times, write output files

    local_output_dir = "../output/standalone_adc/raw/"

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

    tempo = temporoc3(config)
    tempo.init_board()
    

    local_filepath = local_output_dir + "%d_B%d.csv" % (new_file_index, board)


    res = {"dacP":[],
           "dacN": [],
           "iter":[],
           "ADC":[]}

    for dacP in range(0, 2**12, 1):
        for n in range(10):
            tempo.external_DAC.set_dac_VinP(dacP)
            dacN = dac1_to_2_function(dacP)
            tempo.external_DAC.set_dac_VinN(dacN)
            # time.sleep(0.1)
            res['ADC'].append(tempo.get_standalone_ADC_10b_single_sample())
            res['iter'].append(n)
            res['dacP'].append(dacP)
            res['dacN'].append(dacN)

    df = pd.DataFrame(res)
    df.to_csv(local_filepath, index=False)
    tempo.close()

    pass

def  dac1_to_2_function(code_dac1):
    return 2**12-1-code_dac1
    # goal is to have an ADC characteristic centered : 0 V gives 2**12/2 = 512 adc code

def adc_dynamic_scan():
    # BONUS

    # generate a sinus waveform at the output of the external DAC DAC2902Y/1K at a given frequency,
    # of amplitude matched to the adc dynamic range (min/max values from linearity)
    # read standalone temporoc ADC data, compute dynamic ENOB, SNHR, THD, SFDR, SINAD

    # ADC dead time = 100 ns => 10 MSps maximum sampling frequency (Only for standalone ADC)
    # sampling speed should be swept among 1MHz, 10 MHz
    # input frequency should be swept for points below 0.1 * Nyquist frequency
    # at fs=10 MHz, 0.1 * Nyquist freq = 2 MHz, input freq should be among {1M, 2M} Hz
    # at fs=2 MHz, 0.1 * Nyquist freq = 400 kHz, input freq should be among {200, 400} kHz

    # One period sinus stored in lookup table of size 1250 (= fs_max/fin_min = 125MHz/100kHz)
    # as a list of dac values to be sent to the dac at a rate
    # fixed by the writing clock frequency given by the external PLL (dac max is 125 MHz) on out 0
    # loop over a period length (smaller than the lookuptable size for fin>fin_min) given by an FPGA register

    flash_dac_period_memory("config/.csv")
    pass

def flash_dac_period_memory(csv_file):
    # read csv_file and update FPGA fifo programming the
    # Memory should always be read at a constant speed : here maximum DAC frequency = 125 MHz
    # Memory should be read as in a loop of N samples (where N is the number of lines of csv_file)
    pass


def analyse_adc_static_scan(board):

    # read adc data
    res = {'dac_VinP':[], 'dac_VinN':[],
           'adc_mean':[], 'adc_sdev':[]}

    for i in range(2**12):
        csv_file = "dac_VinP_code%d.csv"%i
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            res['dac_VinP'].append(i)
            res['dac_VinN'].append(dac1_to_2_function(i))
            res['adc_mean'].append(df['adc_value'].mean())
            res['adc_sdev'].append(df['adc_value'].std())
        else:
            print("missing file : ", csv_file)
    df_adc = pd.DataFrame(res)


    # read dac data
    df = pd.read_csv(output_dir + 'dac_parameters.csv')
    dac_VinP_slope_volt_per_dacu = df.loc[df.board == board, 'max_dac_VinP'] - df.loc[df.board == board, 'min_dac_VinP']
    dac_VinP_offset_volt = df.loc[df.board == board, 'min_dac_VinP']
    dac_VinN_slope_volt_per_dacu = df.loc[df.board == board, 'max_dac_VinN'] - df.loc[df.board == board, 'min_dac_VinN']
    dac_VinN_offset_volt = df.loc[df.board == board, 'min_dac_VinN']

    # compute non-linearity
    df_adc['VinP_volt'] = df_adc['dac_VinP']*dac_VinP_slope_volt_per_dacu+dac_VinP_offset_volt
    df_adc['VinN_volt'] = df_adc['dac_VinN']*dac_VinN_slope_volt_per_dacu+dac_VinN_offset_volt
    df_adc['Vin_diff_volt'] = df_adc['VinP_volt'] - df_adc['VinN_volt']

    try:
        slope_adcu_per_volt, offset_adcu = np.polyfit(df_adc['Vin_diff_volt'], df_adc['adc_mean'], 1)
    except:
        print('fit failed')
        return

    df_adc['adc_fit_adcu'] = slope_adcu_per_volt*df['Vin_diff_volt']+offset_adcu
    df_adc['INL_adcu'] = df_adc['adc_fit'] - df_adc['adc_mean']
    df_adc['DNL_adcu'] = np.roll(df_adc['INL_adcu'], -1) - df_adc['INL_adcu']
    df_adc.iloc[0, 'DNL_volt'] = 0

    N = 2**10 # number of adc code observed
    static_enob = math.log2(N/np.sqrt(12*(12**-1+(N-2)**-1*(df_adc['INL_adcu']**2)[1:N-2].sum())))
    print('static_enob ', static_enob)

    df_adc.to_csv(output_dir + "standalone_ADC_linearity.csv", index=False)



def check_if_adc_establishing_time_is_enough():
    # time between channel selection with MUX and ADC sample start "SelectADCLG" is around 150 ns (given by digital state machine)
    # enough ?

    # For one given internal ADC (Low or High), enable only 2 channels for the adc's cluster,
    # inject 2 signals of same amplitude in both channels, note adc values reading consecutively the channels
    # repeat injection in both channels, reducing amplitude of only one channel.
    # how is the digitised amplitude of the first constant channel changing with the amplitude digitised on the second channel ?
    print()

def generateSinusWaveform():
    """@param freq_sinus : in Hz"""
    fig, axs = plt.subplots(3, 4, figsize=(15, 8)) #, sharex=True)
    axs = axs.reshape(-1)

    # 10 bits DAC with configurable max speed 125 MHz
    max_amplitude = 2 ** 10 - 1
    DAC_max_freq = 125e6/2

    output_dir = '../config/ADC_tests/DAC_at_%.1f_MHz/'%(DAC_max_freq/1e6)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    for fi,freq_sinus in enumerate([200e3,400e3, 1e6, 2e6]):

        number_DAC_samples = DAC_max_freq//freq_sinus
        period_sinus = 1/freq_sinus

        dt = period_sinus/number_DAC_samples
        t = np.arange(0,period_sinus,dt)
        yi = np.sin(2*math.pi*freq_sinus*t)*max_amplitude
        y = []
        for i,_ in enumerate(yi):
            y += [int("{0:08b}".format(round(yi[i])),2)]
        y = np.array(y)

        if number_DAC_samples <= DAC_max_freq / 1e6:  # see debug
            y = y[:-1]
            yi = yi[:-1]
            t = t[:-1]

        # debug : check continuity over 2 periods (not 2 consecutive "0" values)
        a = list(range(len(y)))
        b = list(range(len(y), 2*len(y)))
        axs[fi+8].scatter(a, y)
        axs[fi+8].scatter(b, y, marker='x')

        # Save config file

        y.tofile(output_dir+'DAC_values_for_freq_%.1f_MHz.csv' % (freq_sinus / 1e6), sep='\n')

        axs[fi].scatter(t, yi, label='float')
        axs[fi].set_title("DAC generated sinus at %.1f MHz"%(freq_sinus/1e6))
        axs[fi].scatter(t, y, label='int 10 bits')
        axs[fi+4].scatter(t, yi-y, label='relative error \nRMS = %.2f\nstd = %.2f'%(np.std(np.sqrt((yi-y)**2)), np.std(yi-y)))

        axs[fi].legend()
        axs[fi+4].legend()

    fig.suptitle("10 bit DAC operated at freq : %.1f MHZ"%(DAC_max_freq/1e6))
    axs[8].set_ylabel("Vérifier raccord entre 2 périodes")
    axs[4].set_ylabel("Résidue [dacU]")
    axs[0].set_ylabel("DAC amplitude [dacu]")
    plt.savefig(output_dir+'DAC_at_%d_MHz.png'%(DAC_max_freq))
    plt.show()


if __name__ == "__main__":
    # generateSinusWaveform()
    adc_static_scan()
