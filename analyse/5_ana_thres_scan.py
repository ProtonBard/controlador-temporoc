import glob
import re

import yaml
from scipy.optimize import curve_fit

from matplotlib import pyplot as plt, animation

plt.switch_backend('agg')
from analyse.common_analysis import analyse_scurve

import pandas as pd
import math
import os
import numpy as np


def threshold_scan(search_string):
    search_string += "/*threshold_scan.csv"
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:

        #  scurves
        # filepath_df_scurve = csv_file.replace('.csv', '_scurve.csv')
        # filepath_df_estimated_threshold = csv_file.replace('.csv', '_estimated_threshold.csv')

        # efficiency_df = pd.read_csv(filepath_df_scurve)
        # threshold_df = pd.read_csv(filepath_df_estimated_threshold)

        # threshold scan
        df = pd.read_csv(csv_file)
        gain = 'TL'
        for channel in np.unique(df.channel):
            plt.figure()
            for asic_config in np.unique(df.asic_config):
                selection = (df.asic_config == asic_config) & (df.channel==channel)
                thres_dac = df.loc[selection, gain+'_dac']
                trigger_freq = df.loc[selection, gain+'_freq']
                plt.plot(thres_dac, trigger_freq, label=str(asic_config))

            plt.grid()
            plt.legend()
            plt.yscale('log')
            # plt.title(gain + ' threshold scan')
            # plt.suptitle("Channel %d" % channel)

            plt.tight_layout()

            plt.savefig(folder + 'ch%d_threshold_scan.png'%channel)
            plt.show()
            plt.close()

        # for channel in range(1):
        #     plt.figure(0)
        #     plt.subplots(2, 2, figsize=(10, 8), sharex='col')
        #
        #     #  scurves
        #     selection = (efficiency_df.channel == channel)
        #     for gi, gain in enumerate(['low', 'high']):
        #         plt.subplot(2, 2, gi + 1)
        #         efficiency_df.sort_values(by=[gain+'_thres_dac'], inplace=True)
        #         ax = plt.plot(efficiency_df.loc[selection, gain+'_thres_dac'], efficiency_df.loc[selection, gain+'_efficiency'], label='ch%d' % channel, marker='*')
        #         plt.axvline(threshold_df.loc[(threshold_df.channel==channel), gain+'_thres_dac'].values[0], color=ax[0].get_color(), linestyle='dashed')
        #         plt.grid()
        #         plt.legend()
        #         plt.title(gain + ' scurve')
        #
        #     # threshold scan
        #     selection = df.channel == channel
        #
        #     for gi, gain in enumerate(['TL', 'TH']):
        #         plt.subplot(2, 2, gi + 3)
        #
        #         not_nan_selection = ~(df.loc[:, gain + '_dac'].isna())
        #         thres_dac = df.loc[selection & not_nan_selection, gain+'_dac']
        #         counts = df.loc[selection & not_nan_selection, gain+'_freq']
        #
        #         # if not((counts > 0.5*max(counts)).all() | (counts < 0.1*max(counts)).all()):
        #         #     # try to fit
        #         #     try:
        #         #         p0 = [thres_dac.iloc[np.argmax(counts)], 2, max(counts)]
        #         #         fitParam, cov = curve_fit(modelGauss, thres_dac, counts, p0=p0)
        #         #         meanHisto = fitParam[0]
        #         #         sigmaHisto = fitParam[1]
        #         #         ampHisto = fitParam[2]
        #         #         xmin = meanHisto - 2 * sigmaHisto
        #         #         xmax = meanHisto + 2 * sigmaHisto
        #         #         xfit = np.arange(xmin, xmax, (xmax - xmin) / 20)
        #         #         yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)
        #         #
        #         #         # thres_dac = (thres_dac-1/2).tolist()+[thres_dac[-1:].iloc[0]+1/2]
        #         #
        #         #         ax = plt.stairs(thres_dac[:-1], counts, label=" mean %.1f ps  RMS = %.1f ps" % (meanHisto, sigmaHisto))
        #         #         plt.plot(xfit, yfit, linestyle='--', color=ax.get_edgecolor(),
        #         #                  label=' mean %.1f ps  sigma = %.1f ps ' % (meanHisto, sigmaHisto))
        #         #         plt.xlabel("Threshold [dac]")
        #         #
        #         #         plt.ylabel('Count')
        #         #         plt.grid()
        #         #         plt.legend()
        #         #     except RuntimeError as e:
        #         #
        #         #         print("Fail to fit")
        #         #         print(e)
        #
        #         plt.plot(thres_dac, counts, label='ch%d'%channel)
        #         plt.grid()
        #         plt.legend()
        #         # plt.yscale('log')
        #         plt.title(gain + ' threshold scan')
        #     plt.suptitle("Channel %d"%channel)
        #     plt.tight_layout()
        #     plt.savefig(folder+'ch%d.png'%channel)
        #     plt.show()
        #     # plt.close()

def scurve(search_string):
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:

        # plot scurves
        filepath_df_scurve = csv_file
        filepath_df_estimated_threshold = csv_file.replace('scurve.csv', 'estimated_threshold.csv')

        efficiency_df = pd.read_csv(filepath_df_scurve)
        threshold_df = pd.read_csv(filepath_df_estimated_threshold)

        for cluster in range(4):
            plt.figure(cluster)
            for gi, gain in enumerate(['low', 'high']):
                efficiency_df.sort_values(by=[gain + '_thres_dac'], inplace=True)
                plt.subplot(1, 2, gi + 1)
                for i in range(16):
                    channel = 16*cluster+i
                    selection = (efficiency_df.channel == channel)
                    ax = plt.plot(efficiency_df.loc[selection, gain+'_thres_dac'], efficiency_df.loc[selection, gain+'_efficiency'], label='ch%d' % channel, marker='*')
                    plt.axvline(threshold_df.loc[(threshold_df.channel==channel), gain+'_thres_dac'].values[0], color=ax[0].get_color(), linestyle='dashed')
                    plt.title(gain + ' scurve')
                plt.grid()
                plt.legend(ncols=4)
            plt.tight_layout()
            plt.savefig(folder+'scurve_cluster%d.png'%cluster)
        plt.show()

def plot_estimated_thres(search_string):
    search_string = search_string.replace('.csv', 'estimated_threshold.csv')
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:

        threshold_df = pd.read_csv(csv_file)
        threshold_df.sort_values(by=['channel'], inplace=True)
        plt.figure(0)
        for gi, gain in enumerate(['low', 'high']):
            plt.subplot(1, 2, gi + 1)
            for method in ['_A', '_B', '']:
                if method == '_A':
                    label= 'dichotomously'
                elif method == '_B':
                    label = 'closest to 0.5'
                else:
                    label='chosen'
                plt.plot(threshold_df.loc[:, 'channel'], threshold_df.loc[:, gain+'_thres_dac'+method], label=label, marker='*')
            plt.title(gain + ' scurve')
            plt.grid()
            plt.legend()
            plt.tight_layout()
            plt.savefig(folder+'estimated_thres.png')
        plt.show()


def plot_calibDAC6b_linearity(search_string, output_folder=None):

    search_string += '*_T1_vs_calibDAC.csv'
    print(search_string)

    csv_files = glob.glob(search_string)

    if len(csv_files)==0:
        print("No csv files found for Vth1Q dac range")
        return

    if output_folder is None:
        output_folder = os.path.dirname(csv_files[0]) + '/../'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        df = df.sort_values(by=['calibDAC'])
        board = int(re.findall("(?<=\\B)[0-9]+", csv_file)[0])

        plt.figure(0, figsize=(17,9))
        plt.figure(1, figsize=(17,9))

        for channel in df.channel:
            selection = (df.channel == channel) # & (df.IbCalibDAC==IbCalibDAC)
            x = df.loc[selection, 'calibDAC']
            y = df.loc[selection, 'T1']
            par = np.polyfit(x, y, 1).tolist()
            lsb = par[0]

            plt.figure(0)
            plt.plot(x, y, label='%d %.3f'%(channel, lsb), marker='.')

            plt.figure(1)
            yfit = x * par[0] + par[1]
            inl = (y - yfit) / lsb
            label = '{:.2f}/{:.2f}/{:.2f}'.format(np.nanmin(inl), np.nanmax(inl), np.std(inl))
            plt.plot(x, inl, label=label, marker='.')


        plt.figure(0)
        plt.grid()
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.title('B%d legend = ch slope [dac_10b_global/dac_6b_local]'%board)
        plt.xlabel('calibDAC6b [dac]')
        plt.ylabel('T1 [dac]')
        # plt.tight_layout()
        plt.savefig(output_folder + "linearity_calibDAC6b.png")

        plt.figure(1)
        plt.grid()
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.title('B%d legend = INL min/max/rms '%board)
        plt.xlabel('calibDAC6b [dac]')
        plt.ylabel('Non-linearity [lsb]')
        # plt.tight_layout()
        plt.savefig(output_folder + "INL_calibDAC6b.png")

        plt.show()

def plot_scurve(search_folder):
    print(search_folder)
    folder = os.path.dirname(search_folder)

    folder_index_str = re.findall("(?<=raw/)[0-9]+", folder)
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    board = config['board'][0]

    output_folder = folder + '/../../' + folder_index_str+'/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    csv_files = [search_folder+'/B%d_trigger_effiency_threshold_scan.csv'%board]

    for filepath_df_trigger_effiency_threshold_scan in csv_files:
        df = pd.read_csv(filepath_df_trigger_effiency_threshold_scan)

        analyse_scurve(df, output_folder)



def plot_IbCalibDAC():
    folder  = "../output/B4_TPR104/ib_calibDAC/83/"
    output_folder = folder+"output/"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    file = folder + "raw/B4_DAC_ratio.csv"
    df = pd.read_csv(file)


    # channel,IbCalibDAC,TL_efficiency_50_calibDacTL_0,TL_efficiency_50_calibDacTL_63,DAC_ratio
    plt.figure(figsize=(13, 7))
    for IbCalibDAC in np.unique(df.IbCalibDAC):
        selection = df.IbCalibDAC==IbCalibDAC
        plt.plot(range(64),df.loc[selection, 'DAC_ratio'], label = 'IbCalibDAC %d'%IbCalibDAC) #, linewidth = IbCalibDAC+2)
        # plt.plot(df.loc[selection, 'TL_efficiency_50_calibDacTL_0'], label='calibDacTL_0')
        # plt.plot(df.loc[selection, 'TL_efficiency_50_calibDacTL_63'], label='calibDacTL_63')
    plt.xlabel("Channel")
    plt.grid()
    plt.legend(bbox_to_anchor=(1, 0.5))
    plt.ylabel("DAC_ratio")
    plt.title("DAC_ratio versus IbCalibDAC versus channel")
    plt.tight_layout()
    plt.savefig(output_folder+ "DAC_ratio_vs_IbCalibDAC_vs_channel.png")
    plt.close()


    plt.figure(figsize=(13, 7))
    df_pivot_mean = df.pivot_table(index='IbCalibDAC', values='DAC_ratio',  aggfunc='mean')
    df_pivot_std = df.pivot_table(index='IbCalibDAC', values='DAC_ratio',  aggfunc='std')
    # plt.plot(df_pivot_mean.index, df_pivot_mean.DAC_ratio, marker='*')
    plt.errorbar(df_pivot_mean.index, df_pivot_mean.DAC_ratio, yerr=df_pivot_std.DAC_ratio)
    plt.xlabel("IbCalibDAC")
    plt.grid()
    plt.ylabel("DAC_ratio = DAC global / DAC local")
    plt.title("DAC_ratio versus IbCalibDAC averaged over channel")
    plt.tight_layout()
    plt.savefig(output_folder + "DAC_ratio_vs_IbCalibDAC.png")
    plt.close()

    calib_dac_list = [int(re.findall("(?<=calibDacTL_)[0-9]+", col)[0]) for col in df.columns if 'calibDac' in col]
    assert len(calib_dac_list) == 2
    df['span'] = df['TL_efficiency_50_calibDacTL_%d'%(max(calib_dac_list))] - df['TL_efficiency_50_calibDacTL_%d'%(min(calib_dac_list))]

    plt.figure(figsize=(13, 7))
    a = df.pivot(columns='IbCalibDAC', index='channel', values='span')
    plt.boxplot(a, labels=a.columns)
    plt.legend()
    plt.xlabel("IbCalibDAC (4b)")
    plt.ylabel("Channel-wise threshold DAC correction range [global dac unit]")
    plt.grid()
    plt.tight_layout()
    plt.savefig(output_folder + "local_dac_range_vs_IbCalibDAC.png")
    plt.close()

    # for IbCalibDAC in np.unique(df.IbCalibDAC):
    #     selection = df.IbCalibDAC==IbCalibDAC
    #     plt.figure(figsize=(13, 7))
    #     # plt.plot(range(64),df.loc[selection, 'span'], label = 'IbCalibDAC %d'%IbCalibDAC)
    #     plt.fill_between(range(64), df.loc[selection, 'TL_efficiency_50_calibDacTL_63'],
    #                      df.loc[selection, 'TL_efficiency_50_calibDacTL_0']) #,label='IbCalibDAC %d' % IbCalibDAC)
    #     plt.xlabel("Channel")
    #     plt.grid()
    #     plt.title('IbCalibDAC %d' % IbCalibDAC)
    #     # plt.legend(bbox_to_anchor=(1, 0.5))
    #     plt.tight_layout()
    #     plt.close()
    # # plt.show()

    # GIF experimentation
    # fig, ax = plt.subplots()
    # IbCalibDAC = np.sort(np.unique(df.IbCalibDAC))[::-1]
    # def animate(i):
    #     selection = df.IbCalibDAC == IbCalibDAC[i]
    #     ax0 = ax.fill_between(range(64), df.loc[selection, 'TL_efficiency_50_calibDacTL_63'], df.loc[selection, 'TL_efficiency_50_calibDacTL_32'], color='tab:orange')
    #     return (ax0,)
    # ani = animation.FuncAnimation(fig, animate, repeat=True, frames=len(IbCalibDAC) - 1, interval=20)
    # # To save the animation using Pillow as a gif
    # # writer = animation.PillowWriter(fps=15,
    # #                                 metadata=dict(artist='Me'),
    # #                                 bitrate=1800)
    # # ani.save('scatter.gif', writer=writer)
    # plt.show()


    # FIT ib calib dac master
    ib_calib_dac_list = np.arange(0, 16)
    Vds = np.array([697,314,291,279,268,262,256,252,245,242,239,237,233,232,229,228])*1e-3
    Vbias_1V = 0.983
    Imaster =  (Vbias_1V-Vds)/24.46e3


    # plt.scatter(ib_calib_dac_list, Imaster, marker='.') #, label = 'Fit K= %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))
    plt.scatter(ib_calib_dac_list, Vds, marker='.') #, label = 'Fit K= %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))
    mu_cox = 2e-4
    L = 500e-9
    W0 = 400e-6
    Vth = 0.23
    R = 50e3
    Vds_fit = []

    for ib_calib_dac in ib_calib_dac_list:
        W = W0*ib_calib_dac
        K = 1/2*mu_cox*W/L

        p = [-K, (-1/R+2*Vth*K), Vbias_1V/R-K*(Vth**2)]   # ax^2+bx+c = 0
        print(np.roots(p))
        Vds_fit.append(np.roots(p)[0])

    Vds_fit = np.array(Vds_fit)
    # Imaster_fit = K**(Vds_fit-Vth)**2
    Imaster_fit = (Vbias_1V-Vds_fit)/50e3
    plt.plot(ib_calib_dac_list, Vds_fit, ls='dashed') #, label = 'Fit K= %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))

    # def Vds_function(ib_calib_dac, Kn, Vth):
    #     W = W0*ib_calib_dac
    #     K = Kn*W
    #     a = -K
    #     b = -1/R+2*Vth*K
    #     c = Vbias_1V/R-K*(Vth**2)
    #     # ax^2+bx+c = 0
    #     delta = b**2-4*a*c
    #     Vds1 = (-b-np.sqrt(delta))/2/a
    #     return Vds1
    # fitParam, cov = curve_fit(Vds_function, ib_calib_dac_list[1:], Vds[:1])
    # plt.plot(ib_calib_dac_list[1:], Vds_function(ib_calib_dac_list[1:], *fitParam), ls='dashed', label='fit') #, label = 'Fit K= %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))


    def Vds_function(ib_calib_dac, Kn, Vth):
        W = W0*ib_calib_dac
        K = Kn*W
        a = -K
        b = -1/R+2*Vth*K
        c = Vbias_1V/R-K*(Vth**2)
        # ax^2+bx+c = 0
        delta = b**2-4*a*c
        Vds1 = (-b-np.sqrt(delta))/2/a
        return Vds1
    fitParam, cov = curve_fit(Vds_function, ib_calib_dac_list[1:], Vds[:1])

    # scipy.optimize.brentq(
    #     f, 0.0, 100.0, args=(77.0 / 27.0, 1.0, 1.0, 10.0))

    plt.grid()
    # plt.show()
    plt.close()

    # Vds = Vds[1:]
    # def fit_MOS_current(ib_calib, Vth, K):
    #     # K = 1/2 * µn * Cox / L
    #     # In saturation Vds>=(Vgs-Vt)
    #     # Vds_i = Vds[ib_calib]
    #     W = 400e-6*ib_calib
    #     Ids = K*W*(Vds-Vth)**2
    #     return Ids
    #
    # plt.figure()
    # Ids = Imaster[1:]
    # fitParam, cov = curve_fit(fit_MOS_current, ib_calib_dac_list, Ids)
    # plt.scatter(Vds, Ids) #, label = 'Fit K= %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))
    # plt.plot(Vds, fit_MOS_current(ib_calib_dac, *fitParam), ls='dashed') #, label = 'Fit K= %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))
    # plt.grid()
    # plt.show()


    max_col = 'TL_efficiency_50_calibDacTL_%d'%(max(calib_dac_list))
    min_col = 'TL_efficiency_50_calibDacTL_%d'%(min(calib_dac_list))
    df_pivot_mean = df.pivot_table(index='IbCalibDAC', values=[max_col, min_col],  aggfunc='mean')
    plt.plot(df_pivot_mean.index, df_pivot_mean[max_col], label='calib DAC = %d'%(max(calib_dac_list)))
    plt.plot(df_pivot_mean.index, df_pivot_mean[min_col], label='calib DAC = %d'%(min(calib_dac_list)))


    # FIT
    ib_calib_dac_serie = df_pivot_mean.index
    global_threshold = df_pivot_mean[max_col].iloc[-1] # the value with the highest ibcalibdac in the dataset
    a = df_pivot_mean[min_col].iloc[-1]
    ib_calib_dac = df_pivot_mean.index[-1]
    c = (20e3*5e-6*(63-0))/(400e-6*ib_calib_dac)
    Im = (global_threshold-a)/c
    p0 = [Im, global_threshold]
    fitParam, cov = curve_fit(fit_local_discri_dac, ib_calib_dac_serie[-9:], df_pivot_mean[min_col].iloc[-9:].values, p0=p0)
    yfit = fit_local_discri_dac(ib_calib_dac_serie, *fitParam)
    plt.plot(ib_calib_dac_serie, yfit, ls='dashed', label = 'Fit Imaster = %.2f [global dac/ohm]  global threshold = %d [dac]'%(fitParam[0]*1e6, fitParam[1]))

    # MEASURE
    # Having measured Ib_calib_dac for B4 with for Vbias_1V = code 8 (983 mV) for ib_calib_dac in range(1, 16)
    calib_dac_TL = 32
    Wch = 5e-6  # current source slave
    Wmaster = 400e-6  # current source master
    R = 20e3
    local_threshold_in_global_unit_list = []
    coef_voltage_per_global_dac = 233e-6 # V/dacUnit (measured)
    extra_coef = 1
    # ib_calib_dac = 15
    # Ich = Wch * (63 - calib_dac_TL) / (Wmaster * ib_calib_dac) * Imaster[-1]
    # coef_voltage_per_global_dac = (-Ich * R) / (a - global_threshold)

    for ib_calib_dac,Im in enumerate(Imaster):
        if ib_calib_dac==0:
            continue
        Ich = Im * Wch * (63 - calib_dac_TL) / (Wmaster * ib_calib_dac)
        local_threshold_in_global_unit = global_threshold - (Ich * R)/coef_voltage_per_global_dac*extra_coef
        local_threshold_in_global_unit_list.append(local_threshold_in_global_unit)
    plt.plot(range(1,16), local_threshold_in_global_unit_list, label='With measured Imaster and %.1f µV/dacu'%(coef_voltage_per_global_dac*1e6))

    plt.legend()
    plt.xlabel("IbCalibDAC (4b)")
    plt.ylabel("Threshold [dac]")
    plt.grid()
    plt.tight_layout()
    plt.savefig(output_folder + "mean_local_threshold_vs_IbCalibDAC.png")
    plt.show()
    plt.close()



    # df_pivot = df.pivot_table(index='IbCalibDAC', values='TL_efficiency_50_calibDacTL_63',  aggfunc=['min', 'max', 'std'])
    # threshold_span = df_pivot['max'].TL_efficiency_50_calibDacTL_63 - df_pivot['min'].TL_efficiency_50_calibDacTL_63
    # IbCalibDAC = df_pivot.index
    # plt.plot(IbCalibDAC, df_pivot['std'].TL_efficiency_50_calibDacTL_63, marker='*', label='Threshold std over channels')
    # plt.plot(IbCalibDAC, threshold_span, marker='*', label='Threshold span (=MAX-MIN) over channels')
    # plt.plot(IbCalibDAC, df_pivot['min'].TL_efficiency_50_calibDacTL_63, label='min')
    # plt.plot(IbCalibDAC, df_pivot['max'].TL_efficiency_50_calibDacTL_63, label='max')
    # plt.plot(IbCalibDAC, (df_pivot_mean.DAC_ratio)*107.451163/0.854867, label='min extrapolated')
    # plt.xlabel("IbCalibDAC")
    # plt.grid()
    # plt.legend()
    # plt.ylabel("Threshold dispersion [DAC global]")
    # plt.title("Threshold dispersion (without alignment) versus IbCalibDAC")
    # plt.savefig(output_folder + "threshold_dispersion_vs_IbCalibDAC.png")

    plt.show()

    pass

def fit_local_discri_dac(ib_calib_dac, Im, global_threshold):
    calib_dac_TL = 0
    Wch = 5e-6      # current source slave
    Wmaster = 400e-6 # current source master
    coef_voltage_per_global_dac = 233e-6  # V/dacUnit (measured)
    Ich = Wch*(63-calib_dac_TL)/(Wmaster*ib_calib_dac)*Im
    R = 20e3
    local_threshold_in_global_unit = global_threshold - Ich*R/coef_voltage_per_global_dac
    return local_threshold_in_global_unit


if __name__ == '__main__':
    folder = "../output/B4_TPR104/threshold_scan/18/raw/"
    # threshold_scan(folder)
    # scurve(folder+"/*scurve.csv")
    # plot_estimated_thres("output/threshold_scan/all/7*.csv")
    # plot_scurve("../output/discri/scurve/raw/1/")
    # plot_IbCalibDAC()
    plot_calibDAC6b_linearity("../output/B4_TPR104/calibDAC6b/0/raw/")
