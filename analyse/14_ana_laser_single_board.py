import glob
import itertools
import os
import pickle, time
import re

import scipy
from scipy import signal, datasets, ndimage, fftpack

import numpy as np
from scipy.optimize import curve_fit
import yaml
from scipy.stats import gaussian_kde

import src.temporoc3

import scipy.optimize as opt
import pandas as pd
import matplotlib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt

from analyse.common_analysis import plot_adc_sum

# matplotlib.use('Qt5Agg')
# matplotlib.use('QtAgg')
matplotlib.use('Qt5Agg')
from common_analysis_TDC import *
from common_analyse_ADC import *

from alive_progress import alive_bar

font = {'size'   : 10}
matplotlib.rc('font', **font)


def analyse_laser_single_board(root_folder, search_folder, time_conversion_method='DNL', do_selection=True):

    config = read_config(root_folder, search_folder)
    df = analyse_init(search_folder, config, merge_clusters_based_on=None)

    if len(df)==0:
        print("No data")
        exit(0)

    board = 1
    channel = 42

    for time_conversion_method in ['lsb_fromCAL']:  # , 'DNL_TOA']: # 'DNL_TOA_CAL'
        # for time_conversion_method in ['lsb_fromCA_moving_avg'] : #, 'DNL_TOA']: # 'DNL_TOA_CAL'
        # for time_conversion_method in ['DNL_TOA_fraction']:  # , 'DNL_TOA']: # 'DNL_TOA_CAL'
        # for time_conversion_method in ['DNL_TOA']:

        compute_ps_time_within_one_msb_cpt(df, config, channel, board, time_conversion_method)

        plot_CTR(df, config, channel, board, time_conversion_method)

def plot_CTR(df, config, channel, board, time_conversion_method):

    ch_suffix = '_low_ch%d_B%d' % (channel, board)
    non_null_selection = df['tdc_data_valid' + ch_suffix]

    non_null_selection_count = non_null_selection.value_counts()[non_null_selection.value_counts().index == True].values
    non_null_selection_count = non_null_selection_count[0] if non_null_selection_count else 0
    print(
        "Non null %d  %d %%" % (non_null_selection_count, non_null_selection_count / len(df) * 100))



    plt.figure()
    selection = non_null_selection #& (df['dt'] < 23) & (df['dt'] > 19)

    dt = df.loc[selection, 'toa_ns'+ch_suffix]
    step = 0.04 # ns
    # step = 1 # lsb
    bins = np.arange(dt.min(), dt.max()+1, step)  # lsb
    counts, bins = np.histogram(dt, bins=bins)
    # plt.stairs(counts, bins, fill=True, label='dt' + ch_suffixA + ch_suffixB)
    plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True, label='toa_ns'+ch_suffix)
    plt.grid()
    plt.yscale('log')
    plt.savefig(config['output_folder'] + "TR"+ch_suffix+'_'+time_conversion_method+'.png')
    plt.show()

    method = ''
    try:
        # GAUSSIAN
        p0 = [bins[np.argmax(counts)], 0.05, max(counts)]
        fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)
        perr = np.sqrt(np.diag(cov))

        # GAUSSIAN-EXP
        p0 = [bins[np.argmax(counts)], 0.05, max(counts) / 2.718, 5]
        fitParam2, cov2 = curve_fit(modelGaussExp, bins[:-1], counts, p0=p0)  # , full_output=True)
        perr2 = np.sqrt(np.diag(cov2))

        if perr[1] < perr2[1]:  # GAUSSIAN is better
            method = 'Gaussian'
            mu = fitParam[0]
            sigmaHisto = fitParam[1]
            ampHisto = fitParam[2]
            xmin = mu - 5 * sigmaHisto
            xmax = mu + 5 * sigmaHisto
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGauss(xfit, mu, sigmaHisto, ampHisto)

            # resolution_FWHM2 = 2.35 * sigmaHisto * 1e3
            r1, r2, resolution_FWHM = half_max_x(xfit, yfit)

            plt.plot(xfit, yfit, linestyle='-', color='red',
                     label=r'Gaussian : CTR = %.0f ps FWHM' % (resolution_FWHM*1e3))

        else:  # GAUSSIAN-EXP is better
            method = 'Gaussian-exp'
            mu = fitParam2[0]
            sigma = fitParam2[1]
            amp = fitParam2[2]
            lambd = fitParam2[3]
            xmin = mu - 20 * sigma
            xmax = mu + 20 * sigma
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGaussExp(xfit, mu, sigma, amp, lambd)

            r1, r2, resolution_FWHM = half_max_x(xfit, yfit)

            plt.plot(xfit, yfit, linestyle='--', color='red',
                     label=r'Gaussian-Exp : CTR = %.0f ps FWHM' % (resolution_FWHM*1e3))  # $\mu$ = %.0f ns

        # print(p0, *fitParam2)
    except RuntimeError as e:
        print("Fail to fit")
        print(e)

    plt.legend()
    plt.show()
    plt.savefig(config['output_folder'] + "CTR"+ch_suffix+'_'+time_conversion_method+'.png')
    plt.close()


if __name__ == '__main__':
    root_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    search_folder = root_folder + "Hamamatsu/laser/0/raw/"
    analyse_laser_single_board(root_folder, search_folder)
