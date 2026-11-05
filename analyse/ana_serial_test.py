import re, os, glob
import yaml
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib
from matplotlib.ticker import FormatStrFormatter, ScalarFormatter, FuncFormatter

from analyse.ana_coincidence_ext_trigger import *
from analyse.ana_internal_TDC import *
from analyse.common_analyse_ADC import *
from analyse.common_data_decoding import *

matplotlib.use('Qt5Agg')
from src.utils import modelFitLinear, asic_col
import scipy.optimize as opt



def plot_power_conso(search_string, output_folder=None):

    search_string += 'conso*.csv'
    print(search_string)

    csv_files = glob.glob(search_string)
    if len(csv_files)==0:
        print("No csv files found for power conso")
        return
    if output_folder is None:
        output_folder = os.path.dirname(csv_files[0]) + '/../DC/'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # analog_current,digital_current,conditions,board,RO_mode,TDC_injected_count,TDC_injected,injection_freq_kHz,cluster_RO_enabled,channels_injected,tempo_dig_ck_freq
    title = ["Extracting TDC dynamic consumption", ""]
    for i, yvar in enumerate(['analog', 'digital']):
        fig, ax = plt.subplots(figsize=(10, 6))
        TDC_conversion_time = 7 * 3.125e-9
        def freq2occupancy(kHz_freq):
            return TDC_conversion_time *kHz_freq *1e3 *100

        def occupancy2freq(occupancy):
            return occupancy /TDC_conversion_time /1e3 /100

        secax = ax.secondary_xaxis('top', functions=(freq2occupancy, occupancy2freq))
        p=[]

        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            subset = df.iloc[1:9,:] # excluding 40M saturation point
            board = np.unique(df['board'])[0]
            tempo_dig_ck_freq = np.unique(df['tempo_dig_ck_freq'])[0]

            subset = subset.sort_values(by=['injection_freq_kHz'])
            x = subset['injection_freq_kHz']
            y = subset[yvar+'_current']
            par = np.polyfit(x, y, 1).tolist()

            if yvar == 'analog':
                subset = df.iloc[1:10,:] # including 40M saturation point
                x = subset['injection_freq_kHz']
                y = subset[yvar+'_current']
                extra_label = 'slope= %d µA/kHz'%(par[0]*1e3)
                # "\n(Linear fit slope before sat = < 11 MHz = TDC conv time at 80 MHz)")
            else:
                extra_label= ''
            p1, = ax.plot(x, y, label=' B%d at %d MHz '%(board, tempo_dig_ck_freq)+extra_label, marker='o')
            p.append(p1)
        secax.set_xlabel('TDC occupancy [%]')
        # formatter not working
        # formatter = FuncFormatter(lambda y, _: '{:.16g}'.format(y))
        # formatter = ScalarFormatter()
        # secax.xaxis.set_major_formatter(formatter) #FormatStrFormatter('%.3f'))
        # secax.yaxis.set_major_formatter(formatter) #FormatStrFormatter('%.3f'))

        ax.set_xlabel('Injection frequency [kHz] (Trigger latch disabled)')
        ax.set_ylabel(yvar+' current [mA RMS]')
        ax.set_title(title[i])

        ax.set_xscale('log')
        ax.legend(handles=p)
        plt.grid()
        plt.tight_layout()
        plt.savefig(output_folder + yvar+"_current_vs_freq.png")
        # plt.show()
        plt.close()


    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        subset = df.iloc[10:,:]
        board = np.unique(df['board'])[0]
        tempo_dig_ck_freq = np.unique(df['tempo_dig_ck_freq'])[0]

        subset = subset.sort_values(by=['channels_injected'])
        x = subset['channels_injected']

        plt.figure(6)
        y = subset['analog_current']
        plt.plot(x, y, label='B%d at %d MHz'%(board, tempo_dig_ck_freq), marker='o')

        plt.figure(5)
        y = subset['digital_current']
        plt.plot(x, y, label='B%d at %d MHz'%(board, tempo_dig_ck_freq), marker='o')

    plt.figure(6)
    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 30),
    #              xycoords='axes pixels')
    plt.xlabel('Number of injected channels')
    plt.ylabel('ANALOG current [mA RMS]')
    plt.grid()
    plt.legend()
    plt.title("Analog current versus nb of ch injected at 200 kHz")
    plt.tight_layout()
    plt.savefig(output_folder + "ASIC_analog_conso_vs_channels.png")
    plt.close()

    plt.figure(5)
    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 30),
    #              xycoords='axes pixels')
    plt.xlabel('Number of injected channels')
    plt.ylabel('DIGITAL current [mA RMS] ')
    plt.grid()
    plt.legend()
    plt.title("Digital current versus nb of ch injected at 200 kHz")
    plt.tight_layout()
    plt.savefig(output_folder + "ASIC_digital_conso_vs_channels.png")
    plt.close()

    # plt.show()
    # plt.close()



def plot_BG_Vbias(search_string, output_folder=None):

    search_string += 'BG_dac_range*.csv'
    print(search_string)

    csv_files = glob.glob(search_string)
    if len(csv_files)==0:
        print("No csv files found for BG Vbias")
        return
    # output_folder = os.path.dirname(search_string) + '/../DC/'

    if output_folder is None:
        output_folder = os.path.dirname(csv_files[0]) + '/../DC/'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # bias_1V_dac,bias_1V_mV,BG_dac,BG_mV,temp_mV
    plt.figure(1)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        board = int(re.findall("(?<=\\B)[0-9]+", csv_file)[0])

        df = df.sort_values(by=['bias_1V_dac'])
        x = df['bias_1V_dac']
        y = df['bias_1V_mV']
        ideal_Vbias_1V_dac = int(df.iloc[(df['bias_1V_mV']-1000).abs().sort_values().index[0]]['bias_1V_dac'])
        plt.plot(x, y, label='B%d Vbias should = %d dac'%(board, ideal_Vbias_1V_dac), marker='o')

    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(100, 30),
    #              xycoords='axes pixels')

    plt.xlabel('Vbias_1V [dac]')
    plt.ylabel('Vbias_1V [mV]')
    plt.title("Vbias versus dac for Vbg=8 dac")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "Vbias1V_vs_dac.png")
    # plt.show()
    plt.close()

def plot_inputDAC_range(search_string, output_folder=None):

    search_string += 'inputDAC_range_per_channel*.csv'
    print(search_string)

    csv_files = glob.glob(search_string)
    if len(csv_files)==0:
        print("No csv files found for input dac range")
        return

    # output_folder = os.path.dirname(search_string) + '/../DC/'
    if output_folder is None:
        output_folder = os.path.dirname(csv_files[0]) + '/../DC/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    fig, ax1 = plt.subplots(figsize=(13,6))
    ax2 = ax1.twinx()
    p=[]
    #channel,ch_input_dac,ch_input_mV
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        board = int(re.findall("(?<=\\B)[0-9]+", csv_file)[0])

        df = df.sort_values(by=['channel'])
        x = df.loc[df['ch_input_dac']==0, 'channel']
        y1 = df.loc[df['ch_input_dac']==0, 'ch_input_mV']
        y2 = df.loc[df['ch_input_dac']==255, 'ch_input_mV']

        # plt.fill_between(x, y1, y2, label='B%d'%board)
        # ax = plt.plot(x, y1, label='B%d InputDAC=0'%board, marker='o', linestyle='--')
        # plt.plot(x, y2, label='B%d InputDAC=255'%board, marker='o', color= ax[0].get_color())
        p1, = ax1.plot(x, y1, label='B%d InputDAC=0'%board, marker='o')
        ax1.plot(x, y2, marker='o', color=p1.get_color())
        p.append(p1)

        lsb = (y2.values-y1.values)/256
        ax2.plot(x, lsb, marker='x', color=p1.get_color(), linestyle='--')

    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 100),
    #              xycoords='axes pixels')

    ax1.set_xlabel('Channel')
    ax1.set_ylabel('Input DAC [mV]')
    ax1.set_title("Input DAC voltage range versus channel (max=255 dac & min=0 dac)")
    ax2.set_ylabel('LSB [mv/dac]')
    ax1.legend(handles=p)

    plt.grid()
    plt.tight_layout()
    plt.savefig(output_folder + "InputDAC_mV_range_vs_channel.png")
    # plt.show()
    plt.close()


def plot_Vth1Q_dac_range(search_string, output_folder=None):

    search_string += 'Vth12Q_dac_range*.csv'
    print(search_string)

    csv_files = glob.glob(search_string)

    if len(csv_files)==0:
        print("No csv files found for Vth1Q dac range")
        return

    if output_folder is None:
        output_folder = os.path.dirname(csv_files[0]) + '/../DC/'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    #dac,Vth1_mV,VthQ_mV
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        board = int(re.findall("(?<=\\B)[0-9]+", csv_file)[0])

        df = df.sort_values(by=['dac'])
        x = df['dac']
        Vth1_mV = df['Vth1_mV']
        VthQ_mV = df['VthQ_mV']

        par = np.polyfit(x, Vth1_mV, 1).tolist()
        lsb = par[0]
        plt.figure(3)
        plt.plot(x, Vth1_mV, label='B%d slope= %.3f mV/dac'%(board, lsb), marker='.')

        plt.figure(4)
        yfit = x * par[0]+par[1]
        inl =  (Vth1_mV - yfit)/lsb
        label = 'INL min/max/rms {:.1f}/{:.1f}/{:.1f}'.format(np.nanmin(inl), np.nanmax(inl), np.std(inl))
        if board != 5:
            plt.plot(x, inl, label='B%d '%board+label, marker='.')

        selection = VthQ_mV<=800
        par = np.polyfit(x[selection], VthQ_mV[selection], 1).tolist()
        plt.figure(5)
        plt.plot(x, VthQ_mV, label='B%d slope= %.3f mV/dac'%(board, par[0]), marker='.')

        plt.figure(6)
        yfit = x * par[0]+par[1]
        inl = ((VthQ_mV - yfit)/lsb)[selection]
        label = 'INL min/max/rms {:.1f}/{:.1f}/{:.1f}'.format(np.nanmin(inl), np.nanmax(inl), np.std(inl))
        if board != 5:
            plt.plot(x[selection], inl, label='B%d '%board+label, marker='.')


    plt.figure(3)
    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(200, 50),
    #              xycoords='axes pixels')
    plt.xlabel('Vth [dac]')
    plt.ylabel('Discriminator threshold voltage [mV]')
    plt.title("Vth1 global versus dac")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "Vth1_vs_channel.png")
    # plt.close()

    plt.figure(4)
    plt.xlabel('Vth [dac]')
    plt.ylabel('Non-linearity [lsb]')
    plt.title("Vth1 INL")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "INL_Vth1_vs_channel.png")
    # plt.close()

    plt.figure(5)
    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 50),
    #              xycoords='axes pixels')
    plt.xlabel('Vth [dac]')
    plt.ylabel('Discriminator threshold voltage [mV]')
    plt.title("VthQ global versus dac (fit below 800 dac)")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "VthQ_vs_channel.png")
    plt.close()

    plt.figure(6)
    plt.xlabel('Vth [dac]')
    plt.ylabel('Non-linearity [lsb]')
    plt.title("VthQ INL")
    plt.grid(visible=True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "INL_VthQ_vs_channel.png")
    plt.close()
    plt.show()


def digitalRO_check(root_folder, search_folder):
    print(search_folder)
    config = read_config(root_folder, search_folder)
    df = analyse_init(search_folder, config)
    config['output_folder'] += '/code_density_tdc/'

    # TDC jitter
    analyse_code_density_internal_tdc(df, config)

    # ADC pedestal
    pedestal_df = analyse_pedestal_core(df, search_folder, config)
    problematic_adc_channels = pedestal_df.loc[(pedestal_df['pedestal_mean']>100) | (pedestal_df['pedestal_mean']<20), ['channel', 'gain', 'board']]
    dead_adc_channels = pedestal_df.loc[pedestal_df['pedestal_mean']==0, ['channel', 'gain', 'board']]
    print("problematic_adc_channels", problematic_adc_channels)
    print("dead_adc_channels", dead_adc_channels)

def analyse_TOT_sweep(root_folder, search_folder):
    print(search_folder)
    config = read_config(root_folder, search_folder)

    tot_df_file = config["output_folder"] + 'TOT_sweep.feather'
    if os.path.exists(tot_df_file):
        tot_df = pd.read_feather(tot_df_file)
    else:
        tot_df = pd.DataFrame()
        for width in range(4,200,10):
            suffix = '_nsWidth_%d' % width

            df0 = analyse_init(search_folder, config, file_suffix=suffix)
            df0['nsWidth'] = width
            tot_df = pd.concat([tot_df, df0], ignore_index=True)

        time_conversion_method = 'lsb_fromCAL_moving_avg'
        time_conversion_method = 'DNL_TOA_calibrated_time'
        tot_df = compute_ps_time_within_one_msb_cpt_for_all_channels(tot_df, config, time_conversion_method)
        tot_df['tot'] = tot_df['toa_ps_low_ch1_B4'] - tot_df['toa_ps_high_ch1_B4']

        tot_df.to_feather(tot_df_file)

    plt.figure()

    # serie = tot_df[['tot', 'nsWidth']]
    print(np.std(tot_df['tot']))
    df_mean = pd.pivot_table(tot_df, values='tot', index='nsWidth', aggfunc=['mean','std']) # 'toa_ps_low_ch2_B4', 'toa_ps_high_ch2_B4'
    # plt.errorbar(df_mean['mean']['tot'].index, df_mean['mean']['tot'].values, yerr=df_mean['std']['tot'].values)
    plt.scatter(tot_df['nsWidth'].values, tot_df['tot'].values)

    # plt.plot(df_mean['toa_ps_low_ch2_B4'])
    # plt.plot(df_mean['toa_ps_high_ch2_B4'])
    plt.grid()
    plt.show()
    pass

def mimic_time_counter(root_folder, search_folder):

    print(search_folder)
    for conf in range(38):
        file_suffix = '_conf%d'%conf
        config = read_config(root_folder, search_folder, file_suffix=file_suffix)
        df  = analyse_init(search_folder, config, file_suffix=file_suffix)


def plot_mimic_counter_offset(search_folder):

    df = pd.read_csv(search_folder+'../offset_stats.csv')
    df_conf = pd.read_csv(search_folder+'conf.csv')

    df2 = pd.DataFrame()
    df2['offset'] = df.loc[df['cluster']==0, 'offset0'] - 1
    df2['conf'] = df.loc[df['cluster']==0, 'conf']
    df_conf = df_conf.merge(df2, on='conf', how='inner')

    df_conf.to_csv(search_folder+'conf2.csv')

    plt.figure()
    for i in range(3):
        # ylabel= 'offset%d' % i
        # ylabel= 'offset_proba%d' % i
        ylabel= 'delta%d' % i
        ylabel= 'delta_proba%d' % i

        # plt.plot(df.conf, df[ylabel], label=ylabel)

    plt.plot(df.conf, df.fraction_events_corrected)
    plt.ylabel("fraction events corrected")
    plt.xlabel("conf")
    plt.grid()
    plt.legend()
    plt.show()
    pass


def compare_DC_results():
    output_folder = "../output/serial_test/board_comparison/"
    # search_string = "../output/serial_test/B6/0/raw/"
    search_string = "../output/serial_test/**/**/raw/"

    # output_folder = None
    # search_string = "../output/serial_test/B3/0/raw/"

    plot_power_conso(search_string, output_folder)
    plot_BG_Vbias(search_string, output_folder)
    plot_Vth1Q_dac_range(search_string, output_folder)
    plot_inputDAC_range(search_string, output_folder)

    generate_report_DC_comparison(output_folder, search_string)

def analyse_coincidence_ext_trig():
    # root_folder = 'Y:/temporoc_sw/'
    root_folder = '../'
    search_folder = root_folder + "output/serial_test/coincidence_ext_trig/4-6/0/raw/"


    analyse_coincidence_ext_trigger(root_folder, search_folder)
    # generate_report({"save_folder": "../output/serial_test/coincidence_ext_trig/B5-6/0/raw/"})

def analyse_DC_results(search_string):

    search_string += "/DC_measurement/**/**/"
    plot_power_conso(search_string)
    plot_BG_Vbias(search_string)
    plot_Vth1Q_dac_range(search_string)
    plot_inputDAC_range(search_string)

if __name__ == "__main__":
    # search_string = "../output/serial_test/B3/2/raw/"

    # compare_DC_results()
    # analyse_digitalRO_check()
    # analyse_coincidence_ext_trig()

    root_folder = "../"
    # asic=37 # 32
    # search_string = root_folder + "output/B7_TPR%d/serial_test/"%asic
    # analyse_DC_results(search_string)

    search_folder = root_folder + "output/B4_TPR104/serial_test/TDC_code_density/"
    # search_folder = root_folder + "output/B7_TPR32/serial_test/TDC_code_density/"
    # search_folder = root_folder + "output/B4_TPR104/serial_test/mimic_time_counter_offsetS/1/raw/"
    i = find_latest_folder_index(search_folder)

    # analyse_TOT_sweep(root_folder, search_folder+"%d/raw/"%i)
    digitalRO_check(root_folder, search_folder+"%d/raw/"%i)
    # mimic_time_counter(root_folder, search_folder)
    # plot_mimic_counter_offset(search_folder)
    # analyse_custom_step(root_folder, search_folder)


