import re, os, glob

import numpy as np
import pandas as pd
import yaml
from matplotlib import pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
from common_analysis_TDC import *
from common_analyse_ADC import *

def plot_Na22_spectrum(search_folder):

    df, output_folder, save_filepath, config, folder_index_str, board, files = analyse_init_internal_adc(search_folder)
    injected_channel_list = config['enable_TL_ASIC_ch']
    channel_gain_list = ['low'] #'high'

    for channel in injected_channel_list:
        for gi, gain in enumerate(channel_gain_list):
            plt.figure(figsize=(10, 8))
            channel = channel%16
            plt.title("Na22 spectrum for ch%d %s"%(channel, gain))

            serie = df.loc[:, 'adc_%s_ch%d' % (gain, channel)]

            counts, bins = np.histogram(serie, bins=80) #np.arange(0, 1024, 1)) #, density=True)
            plt.stairs(counts, bins, fill=True) # align='left', edgecolor='white', linewidth=2
            # plt.plot(bins[:-1],counts) # align='left', edgecolor='white', linewidth=2

            Expected_Mean = bins[np.argmax(counts)]
            low_limit = 125
            fit_selection = df.loc[:, 'adc_%s_ch%d' % (gain, channel)]>low_limit
            fitted_serie = df.loc[fit_selection, 'adc_%s_ch%d' % (gain, channel)]
            counts, bins = np.histogram(fitted_serie, bins=50) #, density=True)
            plt.axvline(low_limit, color='r', linestyle='--')
            # plt.stairs(counts, bins, fill=True) # align='left', edgecolor='white', linewidth=2

            try:
                p0 = [bins[np.argmax(counts)], 10, max(counts)]
                # p0 = [Expected_Mean, 10, max(counts)]
                print(p0)
                fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0) #, bounds= [(250, 1023)])
                meanHisto = fitParam[0]
                sigmaHisto = fitParam[1]
                ampHisto = fitParam[2]
                print(fitParam)

                xmin = meanHisto - 3 * sigmaHisto
                xmax = meanHisto + 3 * sigmaHisto
                xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
                yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)

                plt.plot(xfit, yfit, linestyle='--', color='red', label='Fit mean %.2f ADC  sigma = %.2f ADC  Resolution %.1f %%' % (meanHisto, sigmaHisto, sigmaHisto/meanHisto*100))

            except RuntimeError as e:
                print("Fail to fit")
                print(e)

            plt.xlabel('ADC [lsb]')
            plt.ylabel('Count')
            plt.grid()
            plt.legend()  # ncols=4
            plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in files]), xy=(5, 7),
                         xycoords='axes pixels')
            plt.tight_layout()
            plt.savefig(output_folder + "Na22_spectrum_ch%d_%s.png"%(channel, gain))
    plt.show()
    plt.close()



if __name__ == "__main__":

    # for i in range(5):
    #     plot_Na22_spectrum("output/Na22_spectra/raw/%d/"%i)
    plot_Na22_spectrum("../output/Na22_spectra/raw/1/")
