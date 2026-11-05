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

import scipy.optimize as opt
import pandas as pd
import matplotlib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt


from src.utils import *

# matplotlib.use('Qt5Agg')
# matplotlib.use('QtAgg')
matplotlib.use('Qt5Agg')

from alive_progress import alive_bar

font = {'size'   : 10}
matplotlib.rc('font', **font)

def analyse_scope_results(search_folder):
    folder = os.path.dirname(search_folder)

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    files = glob.glob(search_folder + '/hv*.csv')

    board = config['board'][0]

    df = pd.DataFrame()

    res = {'file':[], 'CTR_FWHM':[], 'CTR_fit':[],
           'NRJ_res_TOT_width_master':[], 'NRJ_res_TOT_width_slave':[],
           'NRJ_res_LG_sh_amplitude_master':[], 'NRJ_res_LG_sh_amplitude_slave':[]}
    # resolution in %
    # CTR in ps FWHM

    filename = os.path.basename(files[0])
    save_folder = config['save_folder'] + '/../output/'
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    df_filepath = save_folder + "df.feather"
    stats_filepath = save_folder + "stats.csv"

    for file in files:
        df_tmp = pd.read_csv(file)

        df_tmp.dropna(inplace=True)

        parameters_swept = os.path.basename(file).split('_')[::2]
        # parameters_swept = config['parameters_swept']
        for param_name in parameters_swept:
            param_value = int(re.findall("(?<="+param_name+"_)[0-9]+", file)[0])
            df_tmp[param_name] = param_value
            if param_name not in res:
                res[param_name] = []
            res[param_name].append(param_value)

        convert_unit(df_tmp)
        filename_without_extension = os.path.splitext(os.path.basename(file))[0]

        energy_resolution = energy_spectrum(df_tmp, filename_without_extension, save_folder, config)
        time_resolution, fit_function = CTR(df_tmp, filename_without_extension, save_folder, config)

        res['file'].append(file)
        res['CTR_FWHM'].append(time_resolution)
        res['CTR_fit'].append(fit_function)
        res['NRJ_res_LG_sh_amplitude_master'].append(energy_resolution[0])
        res['NRJ_res_LG_sh_amplitude_slave'].append(energy_resolution[1])
        res['NRJ_res_TOT_width_master'].append(energy_resolution[2])
        res['NRJ_res_TOT_width_slave'].append(energy_resolution[3])

        df = pd.concat([df, df_tmp])
    pass

    res_df = pd.DataFrame(res)
    res_df.to_csv(stats_filepath, index=False)
    df.to_feather(df_filepath)
    print("Done")

def convert_unit(df):
    df['deltaT'] *= -1e9
    df['LG_sh_amplitude_master'] *= 1e3
    df['LG_sh_amplitude_slave'] *= 1e3
    df['TOT_width_master'] *= 1e9
    df['TOT_width_slave'] *= 1e9

def CTR(df, filename, save_folder, config):
    plt.figure(figsize=(11, 7))

    counts, bins = np.histogram(df.loc[:, 'deltaT'], density=False, bins=300)
    # plt.stairs(counts, bins, color="darkcyan", fill=True, label='# %d'%len(df))
    plt.hist(bins[:-1], bins, weights=counts, align='left', color="darkcyan", fill=True, label='# %d'%len(df))

    selection = df['LG_sh_amplitude_selection'] # TOT_width
    serie = df.loc[selection, 'deltaT']
    counts, bins = np.histogram(serie, density=False, bins=bins)

    plt.xlabel('Master-Slave time difference [ns]')
    plt.ylabel('Count')
    # cornflowerblue

    # plt.stairs(counts, bins, color="darkturquoise", fill=True, label='selection : %d (%d %%)'%(len(serie), len(serie)/len(df)*100))
    plt.hist(bins[:-1], bins, weights=counts, align='left', color="darkturquoise", fill=True, label='Energy selection : %d (%d %%)'%(len(serie), len(serie)/len(df)*100))
    method = ''
    try:
        # GAUSSIAN
        p0 = [bins[np.argmax(counts)], 0.05, max(counts)]
        fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)
        perr = np.sqrt(np.diag(cov))

        # GAUSSIAN-EXP
        p0 = [bins[np.argmax(counts)], 0.05, max(counts) / 2.718, 5]
        fitParam2, cov2 = curve_fit(modelGaussExp, bins[:-1], counts, p0=p0) #, full_output=True)
        perr2 = np.sqrt(np.diag(cov2))

        if perr[1] < perr2[1]: # GAUSSIAN is better
            method='Gaussian'
            mu = fitParam[0]
            sigmaHisto = fitParam[1]
            ampHisto = fitParam[2]
            xmin = mu - 2 * sigmaHisto
            xmax = mu + 2 * sigmaHisto
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGauss(xfit, mu, sigmaHisto, ampHisto)

            # resolution_FWHM2 = 2.35 * sigmaHisto * 1e3
            r1, r2, resolution_FWHM = half_max_x(xfit, yfit)

            plt.plot(xfit, yfit, linestyle='-', color='white',
                     label=r'Gaussian : CTR = %.0f ps FWHM' % resolution_FWHM)

        else: # GAUSSIAN-EXP is better
            method='Gaussian-exp'
            mu = fitParam2[0]
            sigma = fitParam2[1]
            amp = fitParam2[2]
            lambd = fitParam2[3]
            xmin = mu - 20 * sigma
            xmax = mu + 20 * sigma
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGaussExp(xfit, mu, sigma, amp, lambd)

            r1, r2, resolution_FWHM = half_max_x(xfit, yfit)

            plt.plot(xfit, yfit, linestyle='--', color='white',
                     label=r'Gaussian-Exp : CTR = %.0f ps FWHM' % resolution_FWHM) #$\mu$ = %.0f ns

        # print(p0, *fitParam2)
    except RuntimeError as e:
        print("Fail to fit")
        print(e)

    plt.grid()
    plt.legend()
    chA = config['enable_TL_ASIC_ch'][0][0]
    chB = config['enable_TL_ASIC_ch'][1][0]
    plt.suptitle('Coincident time resolution for ch %d (master) - ch %d (slave) %s '%(chA, chB, filename))
    plt.tight_layout()

    plt.savefig(save_folder+'deltaT'+filename+'.png')
    plt.xlim([mu-resolution_FWHM/200, mu+resolution_FWHM/200])
    # plt.show()
    plt.savefig(save_folder+'deltaT_zoom'+filename+'.png')

    plt.close()
    return resolution_FWHM, method

def energy_spectrum(df, filename, save_folder, config):
    # master and slave
    plt.subplots(2, 2, sharex='col', figsize=(15, 8))

    energy_unit = ['mV', 'ns']
    energy_resolution = []
    for mi, measure in enumerate(['LG_sh_amplitude', 'TOT_width']):
        for si, side in enumerate(['master', 'slave']):  # row
            plt.subplot(2, 2, mi+2*si+1)
            label = measure+'_'+side

            counts, bins = np.histogram(df[label], density=False, bins=100)

            if si==1:
                plt.xlabel(measure+' ['+energy_unit[mi]+']')
            plt.ylabel('Count')

            plt.stairs(counts, bins, color="darkcyan", label=side)
            try:
                arg_max = np.argmax(counts)
                if measure=='LG_sh_amplitude':
                    # p0 = [bins[:-1][bins[:-1]>cut_value][np.argmax(counts[bins[:-1]>cut_value])], 30, max(counts[bins[:-1]>cut_value])]
                    # fitParam, cov = curve_fit(modelGauss, bins[:-1][bins[:-1]>cut_value], counts[bins[:-1]>cut_value], p0=p0)
                    expected_sigma = 50

                else: # TOT
                    expected_sigma = 2

                cut_value_min = bins[:-1][arg_max] - expected_sigma
                cut_value_max = bins[:-1][arg_max] + expected_sigma
                selection = (bins[:-1]>cut_value_min) & (bins[:-1]<cut_value_max)
                p0 = [bins[arg_max], expected_sigma, max(counts)]
                fitParam, cov = curve_fit(modelGauss, bins[:-1][selection], counts[selection], p0=p0)

                meanHisto = fitParam[0]
                sigmaHisto = fitParam[1]
                ampHisto = fitParam[2]
                xmin = meanHisto - 2 * sigmaHisto
                xmax = meanHisto + 2 * sigmaHisto
                xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
                yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)

                resolution_FWHM = 2.35 * sigmaHisto / meanHisto * 100
                plt.plot(xfit, yfit, linestyle='-', color='darkblue',
                         label=r'$\mu$ = %.0f %s  $\Delta$E/E = %.1f %% FWHM' % (meanHisto, energy_unit[mi], resolution_FWHM))

                df[measure+'_selection'] = (df[label] < xmax) & (df[label] > xmin)

                energy_resolution.append(resolution_FWHM)

            except RuntimeError as e:
                print("Fail to fit")
                print(e)
                energy_resolution.append(-1)

            plt.grid()
            plt.legend()


    chA = config['enable_TL_ASIC_ch'][0][0]
    chB = config['enable_TL_ASIC_ch'][1][0]

    plt.suptitle('Energy resolution for ch %d (master) - ch %d (slave) %s assuming Gaussian'%(chA, chB, filename))
    plt.tight_layout()

    plt.savefig(save_folder+'energy_spectrum_'+filename+'.png')
    # plt.show()
    plt.close()

    return energy_resolution



def analyse_stats(search_folder):

    file = search_folder+'stats.csv'
    df = pd.read_csv(file)

    parameters_swept = os.path.basename(df.iloc[0]['file']).split('_')[::2]
    for param_name in parameters_swept:
        res = []
        for i in range(len(df)):
            param_value = int(re.findall("(?<=" + param_name + "_)[0-9]+", df.iloc[i]['file'])[0])
            res.append(param_value)
        df[param_name] = res

    df.sort_values(by='patGain', inplace=True)
    plt.plot(df.loc[df.patComp==0, 'patGain'], df.loc[df.patComp==0, 'CTR_FWHM'])
    # plt.plot(df.loc[df.patComp==0, 'patGain'], df.loc[df.patComp==0, 'CTR_fit'])
    plt.show()





if __name__ == "__main__":
    # analyse_scope_results("../output/coincidence/scope_22Na/4/raw/")
    analyse_stats("../output/coincidence/scope_22Na/4/output/")
