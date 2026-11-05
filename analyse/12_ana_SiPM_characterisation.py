import glob
import re


from src.temporoc3 import *
import src.tools as tools
import pandas as pd

import math
import os
import numpy as np
import uiroc.device as device
from src.tools import *
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Qt5Agg')



def threshold_scan(search_folder):
    print(search_folder)
    folder = os.path.dirname(search_folder)
    # csv_files = glob.glob(search_folder)

    folder_index_str = re.findall("(?<=raw/)[0-9]+", folder)
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    board = config['board'][0]

    output_folder = folder + '/../../' + folder_index_str
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    csv_files = [search_folder+'/B%d_threshold_scan.csv'%board]

    for csv_file in csv_files:

        #  scurves
        filepath_df_scurve = csv_file.replace('_threshold_scan.csv', '_scurve.csv')
        filepath_df_estimated_threshold = csv_file.replace('_threshold_scan.csv', '_estimated_threshold.csv')

        # efficiency_df = pd.read_csv(filepath_df_scurve)
        # threshold_df = pd.read_csv(filepath_df_estimated_threshold)

        # threshold scan
        filepath_df_threshold_scan = csv_file #.replace(folder_index_str + '_B', '0_B')
        df = pd.read_csv(filepath_df_threshold_scan)

        for channel in config['enable_TL_ASIC_ch']:
            plt.subplots(2, 1, figsize=(10, 8), sharex='col')

            # #  scurves
            # selection = (efficiency_df.channel == channel)
            # plt.subplot(2, 1, 1)
            #
            # for gi, gain in enumerate(['low', 'high']):
            #     efficiency_df.sort_values(by=[gain+'_thres_dac'], inplace=True)
            #     ax = plt.plot(efficiency_df.loc[selection, gain+'_thres_dac'], efficiency_df.loc[selection, gain+'_efficiency'], marker='*', label=gain)  #label='ch%d' % channel,
            #     plt.axvline(threshold_df.loc[(threshold_df.channel==channel), gain+'_thres_dac'].values[0], color=ax[0].get_color(), linestyle='dashed')
            #
            # plt.grid()
            # plt.legend()
            # plt.title('Average latched trigger state measured 100 times and 20 ns after reset')

            # threshold scan
            selection = df.channel == channel

            plt.subplot(2, 1, 2)
            for gi, gain in enumerate(['TL', 'TH']):


                not_nan_selection = ~(df.loc[:, gain + '_dac'].isna())
                df.sort_values(by=[gain+'_dac'], inplace=True)
                thres_dac = df.loc[selection & not_nan_selection, gain+'_dac']
                trigger_freq = df.loc[selection & not_nan_selection, gain+'_freq']

                # if not((counts > 0.5*max(counts)).all() | (counts < 0.1*max(counts)).all()):
                #     # try to fit
                #     try:
                #         p0 = [thres_dac.iloc[np.argmax(counts)], 2, max(counts)]
                #         fitParam, cov = curve_fit(modelGauss, thres_dac, counts, p0=p0)
                #         meanHisto = fitParam[0]
                #         sigmaHisto = fitParam[1]
                #         ampHisto = fitParam[2]
                #         xmin = meanHisto - 2 * sigmaHisto
                #         xmax = meanHisto + 2 * sigmaHisto
                #         xfit = np.arange(xmin, xmax, (xmax - xmin) / 20)
                #         yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)
                #
                #         # thres_dac = (thres_dac-1/2).tolist()+[thres_dac[-1:].iloc[0]+1/2]
                #
                #         ax = plt.stairs(thres_dac[:-1], counts, label=" mean %.1f ps  RMS = %.1f ps" % (meanHisto, sigmaHisto))
                #         plt.plot(xfit, yfit, linestyle='--', color=ax.get_edgecolor(),
                #                  label=' mean %.1f ps  sigma = %.1f ps ' % (meanHisto, sigmaHisto))
                #         plt.xlabel("Threshold [dac]")
                #
                #         plt.ylabel('Count')
                #         plt.grid()
                #         plt.legend()
                #     except RuntimeError as e:
                #
                #         print("Fail to fit")
                #         print(e)

                plt.plot(thres_dac, trigger_freq, label=gain, marker='+') #

            plt.yscale("log")
            plt.grid()
            plt.legend()
            plt.title('Trigger frequency counting rising edges (capped at 400 MHz due to firmware)')
            plt.suptitle("Channel %d"%channel)
            plt.tight_layout()
            plt.savefig(folder+'ch%d.png'%channel)
            plt.show()
            # plt.close()


def threshold_scan_sweep_param(search_folder):
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

    csv_files = [search_folder+'/B%d_threshold_scan.csv'%board]

    for filepath_df_threshold_scan in csv_files:

        # threshold scan
        df = pd.read_csv(filepath_df_threshold_scan)

        df['hv'] = df.hv_voltage.astype(int)


        for channel in np.unique(df.channel): #config['enable_TL_ASIC_ch']:
            for patGain in np.unique(df.patGain):
                plt.figure()
                for hv in np.unique(df.hv):

                    for patComp in np.unique(df.patComp):

                        selection = (df.channel == channel) & (df.patGain==patGain) & (df.patComp==patComp) & (df.hv==hv)

                        for gi, gain in enumerate(['TL']): # , 'TH'

                            not_nan_selection = ~(df.loc[:, gain + '_dac'].isna())
                            df.sort_values(by=[gain+'_dac'], inplace=True)
                            thres_dac = df.loc[selection & not_nan_selection, gain+'_dac']
                            trigger_freq = df.loc[selection & not_nan_selection, gain+'_freq']
                            if hv>53: #breakdown
                                plt.plot(thres_dac, trigger_freq, label="%d, %d, %d, %d"%(channel, hv,patGain, patComp), marker='+')

                plt.yscale("log")
                plt.grid()
                plt.legend()
                plt.title('Trigger frequency counting rising edges (capped at 400 MHz due to firmware)   ')
                plt.suptitle("legend: ch, hv, patGain, patComp"%channel)
                plt.tight_layout()
                # plt.savefig(output_folder+'ch%d.png'%channel)
        plt.show()


if __name__ == '__main__':
    # threshold_scan("../output/SiPM_characterisation/raw/14/")
    threshold_scan_sweep_param("../output/SiPM_characterisation/raw/25/")
