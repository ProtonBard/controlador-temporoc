import glob
import itertools
import math
import os
import pickle, time
import re

import scipy
from scipy import signal, datasets, ndimage, fftpack, stats

import numpy as np
from scipy.optimize import curve_fit
import yaml
from scipy.optimize.optimize import OptimizeWarning
from scipy.stats import gaussian_kde

import src.temporoc3

import scipy.optimize as opt
import pandas as pd
import matplotlib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import src.CONSTANTS
from analyse.common_data_decoding import *

matplotlib.use('Qt5Agg')
from common_analysis_TDC import *
from alive_progress import alive_bar

font = {'size'   : 10}
matplotlib.rc('font', **font)

def analyse_linearity_internal_tdc(search_folder):
    print(search_folder)
    channel = int(re.findall("(?<=ch_)[0-9]+", search_folder)[0])
    channel_gain = 'low'

    # df_filename, output_search_folder, df = build_df_from_multi_delay(search_folder, channel=2, channel_gain='low')

    files = glob.glob(search_folder)
    # incorporate delay within df

    df_filename = os.path.basename(files[0])
    df_filename = df_filename.split("_delay")[0]  # no mention of delay
    board = int(re.findall("(?<=_B)[0-9]+", df_filename)[0])

    folder_index_str = re.findall("[0-9]+(?=_B)", df_filename)
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(files[0])
    config_file = folder+'config.pkl'
    if os.path.exists(config_file):
        with open(config_file, 'rb') as f:
            loaded_dict = pickle.load(f)

    output_folder = os.path.dirname(files[0]) + '/../' + folder_index_str + '/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    save_filepath = output_folder + df_filename
    df_filepath = save_filepath + ".csv"
    df2_filepath = save_filepath + "2.csv"
    stats_filepath = save_filepath + "_stats.csv"

    hitFreq = int(re.findall("(?<=hit_)[0-9]+", df_filename)[0])
    if hitFreq != 78125:
        hitFreq = 78125
        print("wrong hitFreq in file...")
    hitPeriod_in_320MHz_ck_cycles = int(1 / hitFreq / 3.125e-9)



    if os.path.exists(stats_filepath):
        stats = pd.read_csv(stats_filepath)
        if os.path.exists(df_filepath):
            df = pd.read_csv(df_filepath)
        elif os.path.exists(df2_filepath):
            df = pd.read_csv(df2_filepath)
        else:
            print("Missing dataframe.")
            exit(0)

        stats['not_received_frames'] = stats.asked_event_count - stats.raw_event_count
        status_columns = [col for col in stats.columns if 'status' in col]
        df_mean = pd.pivot_table(stats, values=['exploitable_event_count']+status_columns+['not_received_frames'], index='readout_mode', aggfunc='sum')
        results = df_mean.T.to_dict('list')
        category_names_stats = ['exploitable_event'] + [col for col in stats.columns if 'status' in col] + ['frames not received']
        # frames not decoded correctly

        labels = list(results.keys())
        data = np.array(list(results.values()))
        data = data / data.sum(axis=1).reshape(-1, 1) * 100

        data_cum = data.cumsum(axis=1)  # + offset

        category_colors = plt.colormaps['RdYlGn'](
            np.linspace(0.85, 0.15, data.shape[1]))

        fig, ax = plt.subplots(figsize=(9.2, 5))
        ax.invert_yaxis()
        ax.xaxis.set_visible(False)
        ax.set_xlim(0, np.sum(data, axis=1).max())

        for i, (colname, color) in enumerate(zip(category_names_stats, category_colors)):
            widths = data[:, i]
            starts = data_cum[:, i] - widths
            rects = ax.barh(labels, widths, left=starts, height=0.5,
                            label=colname, color=color)

            r, g, b, _ = color
            text_color = 'white' if r * g * b < 0.2 else 'darkgrey'
            ax.bar_label(rects, fmt='%d', label_type='center', color=text_color)
        ax.legend(ncols=len(category_names_stats), bbox_to_anchor=(0, 1),
                  loc='lower left', fontsize='small')
        plt.grid()
        plt.tight_layout()
        plt.savefig(output_folder + "/data_quality.png")
        plt.close()

    else:
        df = pd.DataFrame()
        stats_dict = {'raw_event_count': [],
                      'asked_event_count': [],
                      'readout_mode': [],
                      'exploitable_event_count': [],
                      'file': [],
                      'delay': [],
                      'hit_freq': [],
                      'hitPeriod_in320MHz': []}

        for file in files:
            print(file)
            df_tmp = build_dataframe_from_file(file)

            stats_dict['raw_event_count'].append(len(df_tmp))
            cluster = re.findall("(?<=cluster_)[0-9]+", file)
            if cluster:
                cluster = int(cluster[0])
            else:
                cluster = 0


            df_tmp = remove_status_erroneous_frames(len(df), df_tmp, stats_dict)
            df_tmp = decode_TDC_data(df_tmp, cluster)

            stats_dict['exploitable_event_count'].append(len(df_tmp))
            readout_mode = re.findall("(?<=mode_)[a-z_]+", file)[0].split('__')[0]
            stats_dict['readout_mode'].append(readout_mode)
            expected_frame_count = int(re.findall("(?<=N_)[0-9]+", file)[0])
            stats_dict['asked_event_count'].append(expected_frame_count)

            stats_dict['hit_freq'].append(hitFreq)
            stats_dict['hitPeriod_in320MHz'].append(hitPeriod_in_320MHz_ck_cycles)

            stats_dict['file'].append(os.path.basename(file))
            delay = int(re.findall("(?<=delay)[0-9]+", file)[0])
            stats_dict['delay'].append(delay)
            df_tmp['delay'] = delay
            df_tmp['modeRO'] = readout_mode


            # # method 3 chosen
            # df_tmp['CALcoarse'] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 15)  # 4 bits
            # df_tmp['CALfine'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000) >> 9)  # 5 bits
            # df_tmp['TOAcoarse'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000) >> 5)  # 4 bits
            # df_tmp['TOAfine'] = tdc_value.apply(lambda x: x & 0b1_1111)  # 5 bits

            # df_tmp['TOAcoarse2'] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 15)  # 4 bits
            # df_tmp['TOAfine2'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000) >> 9)  # 5 bits
            # df_tmp['CALcoarse2'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000) >> 5)  # 4 bits
            # df_tmp['CALfine2'] = tdc_value.apply(lambda x: x & 0b1_1111)  # 5 bits
            # df_tmp['toa2'] = df_tmp.TOAfine2 + 31 * df_tmp.TOAcoarse2
            # df_tmp['cal2'] = df_tmp.CALfine2 + 31 * df_tmp.CALcoarse2
            # df_tmp['delta2'] = df_tmp.cal2 - df_tmp.toa2
            # df_tmp['toa_ns2'] = df_tmp.toa2 * 2 * 3.125 / np.abs(df_tmp.delta2)
            # # print("method 2 :")
            # # print(df_tmp[t])



            # # best
            # df_tmp['CALcoarse3'] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 15)  # 4 bits
            # df_tmp['CALfine3'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000) >> 9)  # 5 bits
            # df_tmp['TOAcoarse3'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000) >> 5)  # 4 bits
            # df_tmp['TOAfine3'] = tdc_value.apply(lambda x: x & 0b1_1111)  # 5 bits
            # df_tmp['toa3'] = df_tmp.TOAfine3 + 31 * df_tmp.TOAcoarse3
            # df_tmp['cal3'] = df_tmp.CALfine3 + 31 * df_tmp.CALcoarse3
            # df_tmp['delta3'] = df_tmp.cal3 - df_tmp.toa3
            # df_tmp['toa_ns3'] = df_tmp.toa3 * 2*3.125/np.abs(df_tmp.delta3)



            # selection1 = df_tmp.TOAcoarse>df_tmp.CALcoarse
            # df_tmp.loc[selection1, 'CALcoarse'] = df_tmp.loc[selection1, 'CALcoarse'] + 16

            # selection1 = df_tmp.TOAcoarse>df_tmp.CALcoarse
            # df_tmp.loc[selection1, 'CALcoarse'] = df_tmp.loc[selection1, 'CALcoarse'] + 16

            suffix = '_%s_ch%d' % (channel_gain, channel)
            df_tmp['toa'+suffix] = df_tmp['TOAfine'+suffix] + 31 * df_tmp['TOAcoarse'+suffix]
            df_tmp['cal'+suffix] = df_tmp['CALfine'+suffix] + 31 * df_tmp['CALcoarse'+suffix]
            df_tmp['delta'+suffix] = df_tmp['cal'+suffix] - df_tmp['toa'+suffix]
            df_tmp['lsb_fromCAL'+suffix] = np.abs(2 * 3.125 / df_tmp['delta'+suffix])
            df_tmp['toa_ns'+suffix] = df_tmp['toa'+suffix] * df_tmp['lsb_fromCAL'+suffix]

            # print(df_tmp.loc[:, ['status', 'TOAcoarse', 'CALcoarse', 'TOAfine', 'CALfine']].drop_duplicates())

            # df_tmp['selection_per_delay'] = df_tmp['msb_cpt_modulo_hit_period'] == modulo_val[np.where(modulo_count == max(modulo_count))][0]


            # print(df_tmp.loc[:, ['toa', 'cal', 'TOAcoarse', 'TOAfine', 'CALcoarse', 'CALfine', 'delta']].value_counts())
            # plt.plot(df_tmp.index, df_tmp.TOAcoarse, label='TOAcoarse', marker = 'o')
            # plt.plot(df_tmp.index, df_tmp.CALcoarse, label='CALcoarse', marker = 'o')
            # plt.legend()
            # plt.show()

            # df_tmp = df_tmp.loc[:, 'tdc_low_ch%d'%channel].value_counts()
            # res['delay'].append(str(delay).zfill(2))
            # res['tdc'].append(str(df_tmp.loc[df_tmp==df_tmp.max()].index.tolist()[0]).zfill(6))
            # res['bin'].append(bin(df_tmp.loc[df_tmp==df_tmp.max()].index.tolist()[0])[2:].zfill(18))

            df = pd.concat([df_tmp, df])

        df.to_csv(df_filepath, index=False)
        stats = pd.DataFrame(stats_dict)
        stats.to_csv(stats_filepath, index=False)

    # dfa = pd.DataFrame(res)
    # dfa.sort_values('delay', inplace=True)
    # dfa.to_csv('file.txt', index=False)
    # dfb = dfa.iloc[::10, :]
    if not os.path.exists(df2_filepath):
        results_TDC_data={}
        results_CPT_data = {}


        # df = df[df.modeRO == modeRO].reset_index(drop=True)
        if 'delaybox_step' in folder:
            methodA=False
            if methodA:
                df['real_time_ns'] = df.delay * 0.01 # ns
            else:
                df_correction = pd.read_csv("output/tdc_scan/standalone_tdc/delaybox_step/oscillo_delay/ref_B%d.csv"%board)
                df = df.merge(df_correction, on='delay', how='inner')
                df['real_time_ns'] = df.oscilloDelay_mean/1e3

        # df = df[df['selection_per_delay']]


        # df.loc[(df.toa < 200) & (df.toa > 100), ['toa', 'cal', 'TOAcoarse', 'CALcoarse', 'delta']].drop_duplicates()

        # selection1 = df.toa>df.cal
        # selection2 = np.abs(df.toa - df.cal) < 50
        # df.loc[selection1, 'CALcoarse'] = df.loc[selection1, 'CALcoarse'] + 16
        # df.loc[selection2, 'TOAcoarse'] = df.loc[selection2, 'TOAcoarse'] + 16
        # df['cal'] = df.CALcoarse*31 + df.CALfine
        # df['delta'] = df.cal - df.toa
        # df['lsb_fromCAL'] = np.abs(2 * 3.125 / df.delta)
        # df['toa_ns'] = df.toa * df.lsb_fromCAL

        # selection = df['toa']>200
        # selection = (df['delta']>-400) & (df['delta']<-340)

        # selection_count = selection.value_counts()[selection.value_counts().index == True].values
        # selection_count = selection_count[0] if selection_count else 0
        # print(selection_count, len(df))
        # selection = df.selection_per_delay


        # selection = (df['cpt_low_ch%d' % channel] == np.max(df['cpt_low_ch%d' % channel]))
        # selection = (df['delta'] < 400) & (df['delta'] > 300)
        # selection = (df['delta'] < 0)

        # selection1 = ((df.CALcoarse-df.TOAcoarse) >= 8)
        # selection2 = ((df.TOAcoarse - df.CALcoarse) >= 0)
        # df.loc[selection1, 'CALcoarse'] -= 8
        # df.loc[selection2, 'TOAcoarse'] -= 8

        suffix = '_%s_ch%d' % (channel_gain, channel)

        # apply_correction = True
        # if apply_correction:
        TOAc_corrected_selection = df['TOAcoarse' + suffix] > 6
        df.loc[TOAc_corrected_selection, 'TOAcoarse'+suffix] -= 8

        CALc_corrected_selection = ((df['CALcoarse' + suffix] - df['TOAcoarse' + suffix]) >= 8)
        df.loc[CALc_corrected_selection, 'CALcoarse'+suffix] -= 8
        selection_corrected = TOAc_corrected_selection | CALc_corrected_selection


        df.loc[:,'toa'+suffix] = df['TOAfine' + suffix] + 31 * df['TOAcoarse' + suffix]
        df.loc[:,'cal'+suffix] = df['CALfine' + suffix] + 31 * df['CALcoarse' + suffix]
        df.loc[:,'delta'+suffix] = df['cal' + suffix] - df['toa' + suffix]
        df.loc[:,'lsb_fromCAL'+suffix] = np.abs(2 * 3.125 / df['delta' + suffix])


        df.loc[:, 'full_toa'+suffix] =  df['CPT'+suffix] + df['toa'+suffix]


        modeRO_list = np.unique(df.modeRO)
        for i, modeRO in enumerate(modeRO_list):

            ROmode_selection = df.modeRO == modeRO

            plt.figure(0, figsize=(10, 8))
            non_null_delta_per_ROmode = (df.loc[ROmode_selection, 'delta' + suffix] != 0) & ROmode_selection

            for fi, col in enumerate(['lsb_fromCAL' + suffix, 'delta'+suffix]):
                serie = df.loc[non_null_delta_per_ROmode, col]
                if col=='lsb_fromCAL' + suffix:
                    serie *= 1e3
                counts, bins = np.histogram(serie)
                lsb_std = np.std(serie)
                lsb_mean = np.mean(serie)
                plt.subplot(1, 2, fi+1)
                plt.title(col)

                # xmin = np.mean(serie) - 3 * lsb_std
                # xmax = np.mean(serie) + 3 * lsb_std
                try:
                    p0 = [bins[np.argmax(counts)], lsb_std, max(counts)]
                    fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)
                    meanHisto = fitParam[0]
                    sigmaHisto = fitParam[1]
                    ampHisto = fitParam[2]
                    xmin = meanHisto - 2 * sigmaHisto
                    xmax = meanHisto + 2 * sigmaHisto
                    xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
                    yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)

                    if col == 'lsb_fromCAL' + suffix:
                        ax = plt.stairs(counts, bins,
                                        label=modeRO + " mean %.1f ps  RMS = %.1f ps" % (lsb_mean, lsb_std))
                        plt.plot(xfit, yfit, linestyle='--', color=ax.get_edgecolor(), label=' mean %.1f ps  sigma = %.1f ps ' % (meanHisto, sigmaHisto))
                        plt.xlabel("TDC lsb [ps]")
                    else:
                        ax = plt.stairs(counts, bins,
                                        label=modeRO + " mean %.1f lsb  RMS = %.1f lsb" % (lsb_mean, lsb_std))
                        plt.plot(xfit, yfit, linestyle='--', color=ax.get_edgecolor(), label=' mean %.1f lsb  sigma = %.1f lsb ' % (meanHisto, sigmaHisto))
                        plt.xlabel("TDC delta [lsb] = TOA-CAL = 2 * 3.125 ns")
                    plt.ylabel('Count')
                    plt.grid()
                    plt.legend()
                except RuntimeError as e:

                    print("Fail to fit")
                    print(e)


            good_tdc_selection0 = (df.loc[ROmode_selection, 'delta'+suffix] > xmin) & (df.loc[ROmode_selection, 'delta'+suffix] < xmax)
            # good_tdc_selection0 = (df.loc[ROmode_selection, 'lsb_fromCAL'+suffix] > xmin/1e3) & (df.loc[ROmode_selection, 'lsb_fromCAL'+suffix] < xmax/1e3)
            good_tdc_selection = good_tdc_selection0 & ROmode_selection

            df.loc[ROmode_selection,'toa_ns'+suffix] = df.loc[ROmode_selection, 'toa' + suffix] * lsb_mean

            bad_tdc_selection = (~good_tdc_selection0) & ROmode_selection
            bad_tdc_count = bad_tdc_selection.value_counts()[bad_tdc_selection.value_counts().index == True].values
            bad_tdc_count = bad_tdc_count[0] if bad_tdc_count.size>0 else 0

            plt.figure(i+1, figsize=(10, 8))
            for i, field in enumerate(
                    [['TOAcoarse' + suffix, 'TOAfine' + suffix], ['CALcoarse' + suffix, 'CALfine' + suffix],
                     ['delta' + suffix, 'toa' + suffix]]):
                for j, field2 in enumerate(field):
                    plt.subplot(2, 3, i + 1 + 3 * j)

                    plt.scatter(df.loc[good_tdc_selection, 'real_time_ns'],
                                df.loc[good_tdc_selection, '%s' % field2],
                                marker='x',linewidths=1, label='Consistent lsb')
                    plt.scatter(df.loc[bad_tdc_selection, 'real_time_ns'], df.loc[bad_tdc_selection, '%s' % field2],
                                marker='.', label='Out-of-range lsb')

                    plt.title(field2)
                    if field2=='delta'+suffix:

                        plt.axhline(meanHisto, color='red', linestyle='solid', linewidth=1)
                        t0 = df.loc[good_tdc_selection, 'real_time_ns'].min()
                        plt.text(t0, meanHisto, "average lsb =  %.1f ps "%(6250/meanHisto), color='red', path_effects=[pe.withStroke(linewidth=2, foreground="white")])

                        plt.axhline(xmin, color='red', linestyle='--', linewidth=1)
                        plt.axhline(xmax, color='red', linestyle='--', linewidth=1)

                        plt.text(t0, xmin, r"lsb +2$\sigma$ = %.0f ps"%(6250/xmin), color='red', path_effects=[pe.withStroke(linewidth=2, foreground="white")])
                        plt.text(t0, xmax, r"lsb -2$\sigma$ = %.0f ps"%(6250/xmax), color='red', path_effects=[pe.withStroke(linewidth=2, foreground="white")])

                    if field2=='toa' + suffix:
                        time_selection = (df.loc[ROmode_selection, 'real_time_ns'] < 13) & good_tdc_selection

                        fitParam, cov = opt.curve_fit(modelFitLinear, df.loc[time_selection, 'real_time_ns'],
                                                      df.loc[time_selection, 'toa' + suffix])
                        # delayOffset = fitParam[1]
                        lsb = 1 / fitParam[0]

                        # df.loc[time_selection, 'toa_fit' + suffix]
                        yfit = modelFitLinear(df.loc[time_selection, 'real_time_ns'], *fitParam)
                        plt.plot(df.loc[time_selection, 'real_time_ns'], yfit,
                                 '--', linewidth=1, color='red',
                                 label='Fit : TDC lsb : %.1f ps' % (lsb * 1e3))

                        plt.legend()
                    plt.ylabel("[lsb]")
                    plt.grid()
                plt.xlabel("Real time [ns]")

            # lines_labels = [ax.get_legend_handles_labels() for ax in fig.axes]
            # lines, labels = [sum(lol, []) for lol in zip(*lines_labels)]
            # labels = ['Consistent lsb', 'Out-of-range lsb']
            # lines = lines[:2]
            # plt.figlegend(lines, labels, loc='upper center', ncol=4)

            plt.suptitle("TDC linearity with a step of 10 ps (supposely) " + modeRO)
            plt.tight_layout()
            plt.savefig(output_folder+"detail_%s.png"%modeRO)
            # plt.show()
            # pass
            # plt.close()

            # plt.show()

            tdc_corrected_and_good = selection_corrected & good_tdc_selection
            tdc_corrected_and_good_count = tdc_corrected_and_good.value_counts()[tdc_corrected_and_good.value_counts().index == True].values[0]

            not_corrected = (~selection_corrected) & good_tdc_selection
            not_corrected_count = not_corrected.value_counts()[not_corrected.value_counts().index == True].values
            not_corrected_count = not_corrected_count[0] if not_corrected_count.size>0 else 0

            TOAc_CALc_corrected = TOAc_corrected_selection & CALc_corrected_selection & good_tdc_selection
            TOAc_CALc_corrected_count = TOAc_CALc_corrected.value_counts()[TOAc_CALc_corrected.value_counts().index == True].values
            TOAc_CALc_corrected_count = TOAc_CALc_corrected_count[0] if TOAc_CALc_corrected_count.size>0 else 0

            TOAc_corrected_count = (TOAc_corrected_selection & good_tdc_selection).value_counts()[(TOAc_corrected_selection & good_tdc_selection).value_counts().index == True].values
            TOAc_corrected_count = TOAc_corrected_count[0] if TOAc_corrected_count.size>0 else 0
            CALc_corrected_count = (CALc_corrected_selection & good_tdc_selection).value_counts()[(CALc_corrected_selection & good_tdc_selection).value_counts().index == True].values
            CALc_corrected_count = CALc_corrected_count[0] if CALc_corrected_count.size>0 else 0

            exploitable_event_count = len(df)

            asked_event_count = np.sum(stats['asked_event_count'])
            # print("%d (%d %%) exploitable events out of %d expected "%(exploitable_event_count, exploitable_event_count/asked_event_count*100, asked_event_count))
            # print("%d (%d %%) good TDC out of exploitable events"%(tdc_good_count, tdc_good_count/exploitable_event_count*100))
            # print("\t↳ %d (%d %%) first time good" % (first_time_good_count, first_time_good_count/tdc_good_count*100))
            # print("\t\t↳ %d (%d %%) TOA or CAL coarse corrected anyway" % (first_time_good_corrected_count, first_time_good_corrected_count/first_time_good_count*100))
            # print("\t↳ %d (%d %%) first time bad" % (first_time_bad_count, first_time_bad_count/exploitable_event_count*100))
            # print("\t↳ %d (%d %%) TOA coarse corrected" %(TOAc_corrected_count, TOAc_corrected_count/exploitable_event_count*100))
            # print("\t↳ %d (%d %%) CAL coarse corrected" %(CALc_corrected_count, CALc_corrected_count/exploitable_event_count*100))
            # print("\t↳ %d (%d %%) TOA or CAL coarse corrected and good" %(tdc_corrected_and_good_count, tdc_corrected_and_good_count/exploitable_event_count*100))








            # dfa = df.loc[:, ['delay', 'cpt_low_ch%d'%channel, 'TOAcoarse', 'CALcoarse']].value_counts()
            # dfa = df.loc[:, ['delay', 'TOAcoarse', 'CALcoarse']].value_counts()
            # dfb =  df.loc[:, ['delay', 'TOAcoarse', 'CALcoarse']].drop_duplicates()

            df['CPT_modulo_hit_period'+suffix] = df['CPT'+suffix] % hitPeriod_in_320MHz_ck_cycles
            # modulo_val, modulo_count = np.unique(df.msb_cpt_modulo_hit_period, return_counts=True)
            # print(modulo_val, modulo_count)
            # print(df.loc[:, ['delta0', 'delta1', 'delta2', 'delta3', 'msb_cpt_modulo_4096']].drop_duplicates())

            # a = df.msb_cpt.apply(lambda x: x << 4) + df['cpt_%s_ch%d' % (channel_gain, channel)]
            # a = df.msb_cpt
            # if np.unique(df.msb_cpt_modulo_hit_period).size > 1:
            #     df['selection_per_delay'] = False
            # else:
            #     df['selection_per_delay'] = True

            # print(np.diff(np.unique(df.msb_cpt_modulo_hit_period), 1))
            # print(np.unique(df.msb_cpt_modulo_hit_period))

            # df['msb_cpt%4096'+suffix]= df['msb_cpt'+suffix]%4096


            for delay in np.unique(df.loc[df.modeRO==modeRO,'delay']):
                one_delay_selection = (df.delay == delay) & ROmode_selection

                clock_phases = df.loc[one_delay_selection & good_tdc_selection, 'CPT_modulo_hit_period'+suffix].value_counts()
                if clock_phases.size>0:
                    dominant_clock_phase = clock_phases[clock_phases == np.max(clock_phases)].index[0]
                    event_with_dominant_ck_phase = df.loc[one_delay_selection, 'CPT_modulo_hit_period'+suffix] == dominant_clock_phase
                    clock_phase_above_modulo = (df.loc[event_with_dominant_ck_phase & one_delay_selection & good_tdc_selection, 'CPT'+suffix]//hitPeriod_in_320MHz_ck_cycles).min()
                    clock_phase_above_modulo = clock_phase_above_modulo * hitPeriod_in_320MHz_ck_cycles
                    # clock_phase_above_modulo = (df.loc[event_with_dominant_ck_phase & one_delay_selection & good_tdc_selection, 'CPT']//hitPeriod_in_320MHz_ck_cycles).iloc[3]
                    # clock_phase_above_modulo =  (clock_phase_above_modulo-3) * hitPeriod_in_320MHz_ck_cycles

                    expected_CPT = df.loc[one_delay_selection, 'index']*hitPeriod_in_320MHz_ck_cycles + dominant_clock_phase + clock_phase_above_modulo
                    # df['CPT//4096'] = df.CPT // 4096
                    # df.loc[one_delay_selection & good_tdc_selection, ['index', 'expected_CPT','CPT', 'CPT_modulo_hit_period', 'CPT//4096']]

                    df.loc[one_delay_selection, 'good_cpt_selection'] = df.loc[one_delay_selection, 'CPT'+suffix] == expected_CPT
                else:
                    df.loc[one_delay_selection, 'good_cpt_selection'] = False

            good_cpt_good_tdc_selection = df.loc[ROmode_selection, 'good_cpt_selection'] & good_tdc_selection
            bad_cpt_good_tdc_selection = ~df.loc[ROmode_selection, 'good_cpt_selection'] & good_tdc_selection
            good_cpt_bad_tdc_selection = df.loc[ROmode_selection, 'good_cpt_selection'] & ~good_tdc_selection
            bad_cpt_bad_tdc_selection = ~df.loc[ROmode_selection, 'good_cpt_selection'] & ~good_tdc_selection

            good_cpt_good_tdc_count = good_cpt_good_tdc_selection.value_counts()[good_cpt_good_tdc_selection.value_counts().index == True].values
            good_cpt_good_tdc_count = good_cpt_good_tdc_count[0] if good_cpt_good_tdc_count.size>0 else 0

            bad_cpt_good_tdc_count = bad_cpt_good_tdc_selection.value_counts()[bad_cpt_good_tdc_selection.value_counts().index == True].values
            bad_cpt_good_tdc_count = bad_cpt_good_tdc_count[0] if bad_cpt_good_tdc_count.size>0 else 0

            good_cpt_bad_tdc_count = good_cpt_bad_tdc_selection.value_counts()[good_cpt_bad_tdc_selection.value_counts().index == True].values
            good_cpt_bad_tdc_count = good_cpt_bad_tdc_count[0] if good_cpt_bad_tdc_count.size>0 else 0
            bad_cpt_bad_tdc_count = bad_cpt_bad_tdc_selection.value_counts()[bad_cpt_bad_tdc_selection.value_counts().index == True].values
            bad_cpt_bad_tdc_count = bad_cpt_bad_tdc_count[0] if bad_cpt_bad_tdc_count.size>0 else 0

            # print("\n%d (%d %%) good TDC out of exploitable events" % (tdc_good_count, tdc_good_count / exploitable_event_count * 100))
            # print("\t↳ %d (%d %%) good_cpt" % ( good_cpt_good_tdc_count, good_cpt_good_tdc_count / tdc_good_count * 100))
            # print("\t↳ %d (%d %%) bad_cpt" % ( bad_cpt_good_tdc_count, bad_cpt_good_tdc_count / tdc_good_count * 100))
            # tdc_bad_count = exploitable_event_count-tdc_good_count
            # print("\n%d bad tdc events "%tdc_bad_count)
            # print("\t↳%d (%d %%) good_cpt" % (good_cpt_bad_tdc_count, good_cpt_bad_tdc_count / tdc_bad_count * 100))
            # print("\t↳%d (%d %%) bad_cpt" % (bad_cpt_bad_tdc_count, bad_cpt_bad_tdc_count / tdc_bad_count * 100))


            df.loc[ROmode_selection, 'good_cpt_good_tdc_selection'] = good_cpt_good_tdc_selection
            df.loc[ROmode_selection, 'bad_cpt_good_tdc_selection'] = bad_cpt_good_tdc_selection
            df.loc[ROmode_selection, 'good_cpt_bad_tdc_selection'] = good_cpt_bad_tdc_selection
            df.loc[ROmode_selection, 'bad_cpt_bad_tdc_selection'] = bad_cpt_bad_tdc_selection

            results_TDC_data[modeRO] = [not_corrected_count, TOAc_corrected_count, CALc_corrected_count, TOAc_CALc_corrected_count, bad_tdc_count]
            results_CPT_data[modeRO] = [good_cpt_good_tdc_count, bad_cpt_good_tdc_count, good_cpt_bad_tdc_count, bad_cpt_bad_tdc_count]

        field = 'cpt_low_ch%d'%channel
        field = 'CPT'+suffix
        # field='msb_cpt'
        # field = 'msb_cpt%4096'
        # field = 'CPT_modulo_hit_period'
        # plt.figure(1, figsize=(10, 8))
        #
        # plt.scatter(df.loc[good_cpt_good_tdc_selection, 'index'], df.loc[good_cpt_good_tdc_selection, field], marker='x',
        #             label=field + ' selection')
        # plt.scatter(df.loc[bad_cpt_good_tdc_selection, 'index'], df.loc[bad_cpt_good_tdc_selection, field], marker='.',
        #             label=field + 'not selection')
        # plt.scatter(df.loc[good_cpt_bad_tdc_selection, 'index'], df.loc[good_cpt_bad_tdc_selection, field], marker='.',
        #             label=field + 'bad selection')
        # plt.scatter(df.loc[bad_cpt_good_tdc_selection, 'index'], df.loc[bad_cpt_good_tdc_selection, field], marker='.',
        #             label=field + 'bad selection')
        #
        # # plt.scatter(df.loc[~good_tdc_selection, 'index'], df.loc[~good_tdc_selection, field], marker='.',
        # #             label=field + 'not selection')
        # plt.grid()
        # plt.legend()
        # # plt.show()

        df.to_csv(df2_filepath, index=False)

        plt.figure(0)
        plt.suptitle("LSB from TDC itself")
        plt.tight_layout()
        plt.savefig(output_folder + "/histo_lsb.png")

        category_names_TDC_data = ['First time good', 'TOAc_corrected', 'CALc_corrected', 'TOAc_CALc_corrected',
                                   'lost cause']
        category_names_CPT_data = ['good_cpt_good_tdc', 'bad_cpt_good_tdc', 'good_cpt_bad_tdc', 'bad_cpt_bad_tdc']
        figname_list = ['TDC_data_quality', 'CPT_data_quality']

        for category_names, results, figname in zip([category_names_TDC_data, category_names_CPT_data],
                                                    [results_TDC_data, results_CPT_data], figname_list):

            labels = list(results.keys())
            data = np.array(list(results.values()))
            data = data / data.sum(axis=1).reshape(-1, 1) * 100

            data_cum = data.cumsum(axis=1)  # + offset

            category_colors = plt.colormaps['RdYlGn'](
                np.linspace(0.85, 0.15, data.shape[1]))

            fig, ax = plt.subplots(figsize=(9.2, 5))
            ax.invert_yaxis()
            ax.xaxis.set_visible(False)
            ax.set_xlim(0, np.sum(data, axis=1).max())

            for i, (colname, color) in enumerate(zip(category_names, category_colors)):
                widths = data[:, i]
                starts = data_cum[:, i] - widths
                rects = ax.barh(labels, widths, left=starts, height=0.5,
                                label=colname, color=color)

                r, g, b, _ = color
                text_color = 'white' if r * g * b < 0.5 else 'darkgrey'
                ax.bar_label(rects, fmt='%d %%', label_type='center', color=text_color)
            ax.legend(ncols=len(category_names), bbox_to_anchor=(0, 1),
                      loc='lower left', fontsize='small')
            plt.tight_layout()
            plt.grid()
            plt.savefig(output_folder + "/%s.png" % figname)


    else:
        df = pd.read_csv(df2_filepath)
        suffix = '_%s_ch%d' % (channel_gain, channel)
        df.loc[:, 'full_toa' + suffix] = (df['CPT' + suffix]%4096) + df['toa' + suffix]

    figure_start_index = len(np.unique(df.modeRO))
    plt.figure(figure_start_index+3, figsize=(10, 8))
    suffix = '_%s_ch%d' % (channel_gain, channel)
    for pi, field in enumerate(['toa'+suffix, 'full_toa'+suffix]):
        plt.subplot(1, 2, pi+1)
        for modeRO in np.unique(df.modeRO):
            if (modeRO=='lg_adc_low_tdc') | (modeRO =='hg_adc_low_tdc')  | (modeRO =='low_tdc'):  #| (modeRO =='full_adc_tdc')
                continue
            selection = df.good_cpt_good_tdc_selection & (df.modeRO == modeRO)
            # selection = (df.good_cpt_good_tdc_selection | df.bad_cpt_good_tdc_selection) & (df.modeRO == modeRO)
            plt.scatter(df.loc[selection, 'real_time_ns'], df.loc[selection, field], label=modeRO)
        plt.title(field)
        plt.legend()
        plt.ylabel("lsb")
        plt.grid()
        plt.xlabel("Real time [ns]")

    plt.suptitle("TDC linearity with a step of 10 ps (supposely) ")
    plt.tight_layout()
    plt.show()

    pass

def check_time_and_msb_cpt_overflow_simultaneously(df, config):
    board=config['board'][0]

    plt.subplots(3,1, sharex=True)
    plt.suptitle("Check if overflow time and msb_cpt occur at the same time !")
    plt.subplot(3, 1, 1)
    plt.title("time : overflow msb_cpt counter")
    plt.scatter(df.index, df['time_B1'].diff(), label="time diff")
    plt.scatter(df.index, df['time_B1'])
    plt.grid()
    plt.legend()
    plt.subplot(3, 1, 2)
    plt.title("CPT")
    plt.scatter(df.index, df['CPT_B%d' % board].diff(), label="diff", marker='x')
    plt.scatter(df.index, df['CPT_B%d' % board])
    plt.grid()
    plt.legend()
    plt.subplot(3, 1, 3)
    plt.title("msb_cpt")
    plt.scatter(df.index, df['msb_cpt_B%d' % board].diff(), label="diff", marker='x')
    plt.scatter(df.index, df['msb_cpt_B%d' % board])
    plt.grid()
    plt.legend()

    plt.tight_layout()
    plt.show()

def check_hit_periodicity(df):
    ch = 43
    gain = 'low'
    board = 1
    channel_suffix = '_%s_ch%d_B%d' % (gain, ch, board)

    selection = df['tdc_data_valid' + channel_suffix]

    print(df.loc[selection, 'toa_ns'+channel_suffix].diff().value_counts())

    plt.figure()
    plt.title('toa_ns %.3f ns'%(df['toa_ns' + channel_suffix].diff()[selection].median()))
    plt.scatter(df.index[selection], df['toa_ns' + channel_suffix].diff()[selection])
    plt.grid()
    plt.legend()
    plt.show()



def plot_non_linearity(df_pivot_mean, config):

    channel = 43
    channel_gain = 'low'
    board = 1
    suffix = '_%s_ch%d_B%d' % (channel_gain, channel, board)

    xvar = 'toa' + suffix
    yvar = 'real_time_ns'

    # df_pivot_mean = pd.pivot_table(subset, values=yvar, index=xvar, aggfunc="mean").reset_index()

    try:
        fitParam, cov = opt.curve_fit(modelFitLinear, df_pivot_mean[xvar], df_pivot_mean[yvar])
    except:
        fitParam = [0, 0]
    slope = fitParam[0]
    # delayOffset = fitParam[1]
    lsb = abs(slope)

    yfit = modelFitLinear(df_pivot_mean[xvar], *fitParam)
    inl = (yfit - df_pivot_mean[yvar]) / lsb

    plt.subplots(1,2, figsize=(15,7), sharex=True)
    plt.subplot(121)

    plt.plot(df_pivot_mean[xvar], yfit, '--', linewidth=1, color='black')

    plt.scatter(df_pivot_mean[xvar], df_pivot_mean[yvar], s=2,
                label='Fit averaged data\nLSB = %.2f ps' % (lsb * 1e3))  # color=ax1[0].get_color()
    # plt.scatter(df_pivot_mean[xvar], df_pivot_mean['real_time_ns'], s=2, label='real time')

    plt.subplot(122)
    plt.plot(df_pivot_mean[xvar], inl, marker='.',
             label='INL rms={:.2f} lsb/{:.0f} ps\n  min/max {:.2f}/{:.2f} fit lsb\n = {:.0f}/{:.0f} ps'
             .format(np.std(inl), np.std(inl) * lsb * 1e3, np.nanmin(inl), np.nanmax(inl), np.nanmin(inl) * lsb * 1e3,
                     np.nanmax(inl) * lsb * 1e3))
    # # +'\n'+'Excluding |INL| > %d'%inl_cut)

    plt.subplot(121)
    plt.ylabel("Time [ns]")
    plt.title("TDC TOA linearity for channel %d %s" % (channel, channel_gain))
    plt.xlabel("TOA [LSB]")
    plt.grid()
    plt.legend()

    plt.subplot(122)
    plt.xlabel("TOA [LSB]")
    plt.ylabel("INL [LSB]")
    plt.title("Integral non-linearity for channel %d %s" % (channel, channel_gain))
    plt.grid()
    plt.legend()
    plt.suptitle(config['datapath_to_display'])

    # mng = plt.get_current_fig_manager()
    # mng.full_screen_toggle()
    plt.tight_layout()

    output_folder = config['save_folder'] + '/../inl/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    plt.savefig(output_folder + "inl_ch%d_%s.png" % (channel, channel_gain))
    # plt.close()
    plt.show()
    return lsb

def analyse_custom_step(root_folder, search_folder):

    config = read_config(root_folder, search_folder)
    df = analyse_init(search_folder, config)

    if len(df) == 0:
        print("No data")
        exit(0)

    for time_conversion_method in ['lsb_fromCAL']: #, 'lsb_fromCAL_moving_avg', 'DNL_TOA_fraction']:
        compute_abs_ps_time_for_all_channels(df, config, time_conversion_method=time_conversion_method)

    df = adjoin_real_time(df, config)

    # check_time_and_msb_cpt_overflow_simultaneously(df, config)

    # check_hit_periodicity(df)

    # df = select_monotonous_data_internal_TDC(df, config)
    # plot_non_linearities_internal(df, config)

    ch = 43
    gain = 'low'
    board = config['board'][0]
    channel_suffix = '_%s_ch%d_B%d' % (gain, ch, board)
    selection = df['tdc_data_valid' + channel_suffix]


    # Monotonous selection
    # if config['real_time_ns_min'] != 'None' :
    #     real_time_ns_min = config['real_time_ns_min']
    # else:
    #     real_time_ns_min = df['real_time_ns'].min()
    #
    # if config['real_time_ns_max'] != 'None':
    #     real_time_ns_max = config['real_time_ns_max']
    # else:
    #     real_time_ns_max = df['real_time_ns'].max()
    # time_selection = selection & (df['real_time_ns'] < real_time_ns_max) & (df['real_time_ns'] > real_time_ns_min)

    time_selection = selection

    plt.scatter(df.loc[time_selection, 'real_time_ns'], df.loc[time_selection, 'toa' + channel_suffix], label='selection')
    plt.grid()
    plt.legend()
    plt.show()

    # plot_non_linearities_internal(df[time_selection], config)

    lsb = plot_non_linearity(df[time_selection], config)
    plot_lsb_vs_time_for_all_ch(df, config)


    df2_filepath = output_folder + "2.feather"
    if not os.path.exists(df2_filepath):

        drop_not_injected_channels(df, config)
        # drop_not_injected_gain(df, config)
        drop_adc_columns(df)

        df.to_feather(df2_filepath)
    else:
        df = pd.read_feather(df2_filepath)

    tempo_dig_ck = config['config_B%d' % board]['tempo_dig_ck']
    config['rangeTDCtoa_ps'] = 1e6/tempo_dig_ck
    config['toa_stats_filepath'] = config['output_folder'] + '/B%d_tdc_CAL_stats_per_channel.csv' % config['board'][0]

    # plot_tdc_linearity(df, config, output_folder, folder_suffix='raw', tvar='delay')
    # df = correct_TDC_data(df, config)
    # plot_tdc_linearity(df, config, output_folder, folder_suffix='corrected', tvar='delay')
    plot_tdc_linearity(df, config, output_folder, folder_suffix='real_time', row=1, col=['toa', 'cal'])  # 'full_toa',

    # analyse_calib_lsb(df, config, output_folder)
    # analyse_jitter(df, config, output_folder)

    # plot_lsb_vs_time_for_all_ch(df, config, plot=True)




    pass


def analyse_multichannel_custom_step_internal_tdc(search_folder):

    df, output_folder, save_filepath, config, folder_index_str, board, files = analyse_init_internal_tdc(search_folder)

    # focus on one cluster only
    # df = df[df.cluster == 0]

    df2_filepath = save_filepath + "_2.feather"
    df3_filepath = save_filepath + "_3.feather"

    # Step 2 : analyse calib lsb
    if os.path.exists(df2_filepath):
        df = pd.read_feather(df2_filepath)
    else:
        for injected_ch in config['enable_TL_ASIC_ch']:
            channel_gain = 'high'
            cluster = injected_ch // 16
            cluster_channel = injected_ch % 16
            ch_gain_suffix_at_cluster_level = '_%s_ch%d' % (channel_gain, cluster_channel)
            cluster_selection = (df.cluster == cluster)

            plt.plot(df.loc[cluster_selection, 'index'], df.loc[cluster_selection, 'toa' + ch_gain_suffix_at_cluster_level], label="%d"%injected_ch)
        plt.legend()
        plt.grid()
        plt.show()


        # channel selection
        channel = 43
        channel_gain = 'high'
        cluster = channel // 16
        cluster_channel = channel % 16
        ch_gain_suffix_at_cluster_level = '_%s_ch%d' % (channel_gain, cluster_channel)
        cluster_selection = (df.cluster == cluster)

        # Collect info for time conversion
        PLL_config_file = config['PLL_config_file'][0]
        tempo_dig_clock = float(re.findall("(?<=tdc_ck_)[0-9]+[.]?[0-9]+", PLL_config_file)[0])
        hit_freq = config['hit_freq'][0]


        # Filter based on super coarse counter diff
        df['diff' + ch_gain_suffix_at_cluster_level] = df.loc[
            cluster_selection, 'CPT' + ch_gain_suffix_at_cluster_level].diff()
        print(df['diff' + ch_gain_suffix_at_cluster_level].value_counts())
        if 'ck_cycles_in_between_2_hits' in config.keys():
            ck_cycles_in_between_2_hits = config['ck_cycles_in_between_2_hits'][0]
        else:
            ck_cycles_in_between_2_hits = find_ck_cycles_in_between_2_hits(hit_freq, tempo_dig_clock)

        # markers = ['x', 'o']
        # for i, iter in enumerate(np.unique(df['iter'])):
        #     plt.scatter(df.loc[:, 'index'],
        #                 df.loc[:, 'toa' + ch_gain_suffix_at_cluster_level], marker=markers[i])
        #
        #     plt.grid()
        #     plt.show()

        df = df[df['diff' + ch_gain_suffix_at_cluster_level] == ck_cycles_in_between_2_hits]


        # Re-align time data based on tdc data correlation
        # df = df[(df.iter==0) | (df.iter==8)]
        for iter in np.unique(df['iter']):
            df.loc[df.iter == iter, 'index'] -= df.loc[df.iter == iter, 'index'].min()

        df = df[(df.iter==9) | (df.iter==8)]
        df['diff'] = df['index'].diff() #.fillna(0).astype('int')


        for iter in [9]: #np.unique(df['iter']):
            a = df.loc[df.iter != iter, 'toa'+ch_gain_suffix_at_cluster_level].values #toa_with_1b_cpt
            a_index = df.loc[df.iter != iter, 'index'].values

            index_offset = 0
            for index, row in df.loc[df.iter != iter].reset_index().iterrows():
                if (row['diff'] != 2) & ~np.isnan(row['diff']):
                    a = np.insert(a, index+index_offset, [a[index+index_offset-1]]*(int(row['diff']/2)-1), axis=0)
                    new_a_index = [a_index[index+index_offset-1]+2*i+2 for i in range(int(row['diff'] / 2)-1)]
                    a_index = np.insert(a_index, index+index_offset, new_a_index, axis=0)
                    index_offset += len(new_a_index)
                    pass

            b = df.loc[df.iter == iter, 'toa'+ch_gain_suffix_at_cluster_level].values
            b_index = df.loc[df.iter == iter, 'index'].values
            np.diff(b_index)

            index_offset = 0
            for index, row in df.loc[df.iter == iter].reset_index().iterrows():
                if (row['diff'] != 2) & ~np.isnan(row['diff']):
                    new_b = [b[index+index_offset-1]]*(int(row['diff']/2)-1)
                    new_b_index = [b_index[index+index_offset-1]+2*i+2 for i in range(int(row['diff'] / 2)-1)]

                    b = np.insert(b, index+index_offset, new_b, axis=0)
                    b_index = np.insert(b_index, index+index_offset, new_b_index, axis=0)
                    index_offset += len(new_b_index)
                    print(len(b), len(new_b_index))
                    pass

            # index1 = np.argmax(signal.correlate(a, b))
            # index2 = np.argmax(signal.correlate(b, a))



            pass
            # a = df.loc[df.iter == iter, ['index', 'toa_with_1b_cpt'+ch_gain_suffix_at_cluster_level]].values.T
            # b = df.loc[df.iter != iter, ['index', 'toa_with_1b_cpt'+ch_gain_suffix_at_cluster_level]].values.T

            # a = df.loc[df.iter == iter, ['toa_with_1b_cpt'+ch_gain_suffix_at_cluster_level, 'index']].values.T
            # b = df.loc[df.iter != iter, ['toa_with_1b_cpt'+ch_gain_suffix_at_cluster_level, 'index']].values.T

            # index1 = np.argmax(signal.correlate2d(a, b))
            # plt.scatter(a[0], a[1])
            # plt.scatter(b[0], b[1])
            # plt.show()
            # index2 = np.argmax(signal.correlate2d(b, a))
            # print(iter, index1, index2)
            # df.loc[df.iter == iter, ['toa_with_1b_cpt' + ch_gain_suffix_at_cluster_level]].T.values

            corr = signal.convolve(a, b, mode='same')
            corr = np.correlate(a-a.mean(), b-b.mean(), mode='same')
            # lags = signal.correlation_lags(a.size, b.size)
            # lag = lags[np.argmax(corr)]


            print(convolve(a, b, 0))
            print(convolve(a, b, 27))
            # plt.plot(np.correlate(a,b))
            # plt.plot(np.correlate(a-a.mean(), b-b.mean()))
            # plt.plot(np.correlate(a-a.mean(), b-b.mean(), mode='same'))
            # plt.plot(np.correlate(a-a.mean(), b[::-1]-b.mean(), mode='same'))
            # plt.plot(np.correlate(a, b, mode='same'))
            # plt.show()

            # def rfft_xcorr(x, y):
            #     M = len(x) + len(y) - 1
            #     N = 2 ** int(np.ceil(np.log2(M)))
            #     X = np.fft.rfft(x, N)
            #     Y = np.fft.rfft(y, N)
            #     cxy = np.fft.irfft(X * np.conj(Y))
            #     cxy = np.hstack((cxy[:len(x)], cxy[N - len(y) + 1:]))
            #     return cxy
            #
            # def match(x, ref):
            #     cxy = rfft_xcorr(x, ref)
            #     index = np.argmax(cxy)
            #     if index < len(x):
            #         return index
            #     else:  # negative lag
            #         return index - len(cxy)
            #
            # print(match(a,b))

            def get_max_correlation(original, match):
                z = signal.fftconvolve(original, match[::-1])
                lags = np.arange(z.size) - (match.size - 1)
                return (lags[np.argmax(np.abs(z))])

            get_max_correlation(a, b)

            # y, x = np.unravel_index(np.argmax(corr), corr.shape)
            offset = np.argmax(corr)
            # offset2 =
            # index0 = a[0][offset]
            # index1 = a[1][offset]
            # index2 = b[0][offset]
            # index3 = b[1][offset]
            pass
            # df.loc[df.iter==iter, 'index'] -= index1
            shift = -(66 / 2 - len(b) + 1) * 2
            df.loc[df.iter==iter, 'index'] += shift #offset*2 #b_index[offset] #offset
            # df.loc[df.iter==iter, 'index'] += np.argmax(corr) # + (len(a[0]) - 1)

            for i, iter in enumerate(np.unique(df['iter'])):
                plt.scatter(df.loc[df.iter==iter, 'index'], df.loc[df.iter==iter, 'toa' + ch_gain_suffix_at_cluster_level], marker='x', s=100, label='%d'%iter)

            # plt.scatter(b_index+46, b, marker='o', label='8 filled shift 46')

            # plt.scatter(b_index+(offset/2-len(b)+1)*2, b, marker='o', label='8 filled shift found %d'%shift)
            # plt.scatter(a_index, a, marker='x', s=50, label='9 filled')
            plt.grid()
            plt.legend()
            plt.show()

        # df['index'] = df['index']+df.iter*1000
        # Convert x-axis into time
        # df = adjoin_real_time(df, output_folder, board)

        if 'tdc_ck' in PLL_config_file:
            if 'current_step' in config.keys():
                dt = config['current_step'][0]  # ps
            else:
                dt = find_step(hit_freq, tempo_dig_clock)  # ps
            df['real_time_ns'] = df['index'] * dt * 1e9
        else:
            df['real_time_ns'] = df['index'] * float(config['expected_step'][0]) * 1e9


        # plot_tdc_linearity(df, config, output_folder, folder_suffix='CPT', tvar='real_time_ns', col=['toa_with_1b_cpt', 'diff'], src_file=files[0])

        plot_tdc_linearity(df, config, output_folder, folder_suffix='CPT', tvar='index', col=['toa_with_1b_cpt', 'diff'], src_file=files[0])

        markers = ['x', 'o']
        for i, iter in enumerate(np.unique(df['iter'])):
            plt.scatter(df.loc[df.iter==iter, 'index'], df.loc[df.iter==iter, 'toa' + ch_gain_suffix_at_cluster_level], marker=markers[i])

        plt.grid()
        plt.show()
        # plt.scatter(df.loc[cluster_selection, 'index'], df.loc[cluster_selection, 'CPT'+ch_gain_suffix_at_cluster_level].diff())
        # plt.hist(df.loc[(df['diff']>0) & (df['diff']<376), 'diff'])
        markers = ['x', 'o']
        # for i, iter in enumerate(np.unique(df['iter'])):
            # plt.scatter(df.loc[df.iter==iter, 'index'], df.loc[df.iter==iter, 'toa' + ch_gain_suffix_at_cluster_level], marker=markers[i])

        plt.plot(a,marker='x')
        plt.plot(b,marker='o')
        plt.grid()
        plt.show()
        # df = correct_TDC_data(df, config)

def correlate(a,b,k):
    t = 0
    for l in range(len(a)):
        bi = l - k + len(b) - 1
        if (bi >= 0) & (bi < len(b)):
            t += a[l] * np.conj(b[bi])
    return t

def convolve(a, b, n):
    t = 0
    for m in range(len(a)):
        bi = n - m + int((len(b)+1)/2-1)
        if (bi >= 0) & (bi < len(b)):
            t += a[m] * b[bi]
    return t

def analyse_delaybox_step_internal_tdc(search_folder):

    df, output_folder, config, folder_index_str = analyse_init_internal_tdc(search_folder)


    if len(df) == 0:
        print("No data")
        exit(0)

    df2_filepath = output_folder + "2.feather"
    if not os.path.exists(df2_filepath):
        df = drop_not_injected_channels(df, config)
        df = drop_not_injected_gain(df, config)
        df = drop_adc_columns(df)
        df.to_feather(df2_filepath)
    else:
        df = pd.read_feather(df2_filepath)

    config['rangeTDCtoa_ps'] = 1e6/tempo_dig_ck
    config['toa_stats_filepath'] = config['output_folder'] + '/B%d_tdc_CAL_stats_per_channel.csv' % config['board'][0]

    # plot_tdc_linearity(df, config, output_folder, folder_suffix='raw', tvar='delay')
    # df = correct_TDC_data(df, config)
    # plot_tdc_linearity(df, config, output_folder, folder_suffix='corrected', tvar='delay')
    df = adjoin_real_time(df, config)
    plot_tdc_linearity(df, config, output_folder, folder_suffix='real_time', row=1, col=['toa', 'cal'])  # 'full_toa',
    # df = select_monotonous_data_internal_TDC(df, config, output_folder)
    # plot_non_linearities_internal(df, config, output_folder, folder_index_str)
    # analyse_calib_lsb(df, config, output_folder)
    # analyse_jitter(df, config, output_folder)


    df3_filepath = output_folder + "_3.feather"

    # Step 3 :
    if os.path.exists(df3_filepath):
        df = pd.read_feather(df3_filepath)
    else:
        hitFreq = int(config['hit_freq'][0])
        hitPeriod_in_320MHz_ck_cycles = int(1 / hitFreq / 3.125e-9)

        df = classify_tdc_cpt_data(df, config, output_folder, hitPeriod_in_320MHz_ck_cycles)
        df.to_feather(df3_filepath)

    plot_tdc_cpt_quality(config, output_folder)


    pass
    # plot_tdc_linearity(df, output_folder, folder_suffix='fitted')

def plot_NL(config):
    output_folder = config['output_folder'] + '/NL/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    channel_stats_filename = config['output_folder'] + '/tdc_NL_stats_per_channel.csv'
    tdc_CAL_df = pd.read_csv(channel_stats_filename)

    calib_table_filename = config['output_folder'] + '/tdc_DNL_TOA_calib_table.csv'
    calib_table = pd.read_csv(calib_table_filename)

    for board in config['board']:
        board_config = config['config_B%d' % board]
        for NL in ['DNL', 'INL']:
            plt.figure(figsize=(10, 7))
            plt.title(NL+' for low (dotted) and high (solid) TDC')
            ls= ['dotted', 'solid']
            for i,gain in enumerate(board_config['tdc_injected'][0]):
                lsb_selection = (tdc_CAL_df.gain == gain) & (tdc_CAL_df.board == board)

                plt.plot(tdc_CAL_df.loc[lsb_selection, 'channel'], tdc_CAL_df.loc[lsb_selection, NL+'_RMS_ps'],
                         label='RMS %s'%gain, ls=ls[i], color='tab:blue')
                plt.plot(tdc_CAL_df.loc[lsb_selection, 'channel'], tdc_CAL_df.loc[lsb_selection, NL+'_MIN_ps'],
                         label='MIN %s'%gain, ls=ls[i], color='tab:green')
                plt.plot(tdc_CAL_df.loc[lsb_selection, 'channel'], tdc_CAL_df.loc[lsb_selection, NL+'_MAX_ps'],
                         label='MAX %s'%gain, ls=ls[i], color='tab:red')

            plt.axvline(x=-0.5, color='black', linestyle='--', label='GND pads', alpha=0.5)
            plt.axvline(x=19.5, color='black', linestyle='--', alpha=0.5)
            plt.axvline(x=55.5, color='black', linestyle='--', alpha=0.5)
            plt.axvline(x=3.5, color='red', linestyle='--', label='VDD pads', alpha=0.5)
            plt.axvline(x=24.5, color='red', linestyle='--', alpha=0.5)
            plt.axvline(x=43.5, color='red', linestyle='--', alpha=0.5)
            plt.xlabel('Channel')
            plt.ylabel(NL+' [ps]')
            plt.grid()
            plt.legend()
            plt.tight_layout()
            plt.savefig(config['output_folder'] + '/NL/%s_vs_channel.png' % NL)
            # plt.show()
            plt.close()


        plt.figure(figsize=(10, 7))
        ls= ['dotted', 'solid']
        plt.title('Comparison between LSB fitted and LSB from TDC self-calibration')
        for i, gain in enumerate(board_config['tdc_injected'][0]):
            selection = (tdc_CAL_df.gain == gain) & (tdc_CAL_df.board == board)

            plt.plot(tdc_CAL_df.loc[selection, 'channel'], tdc_CAL_df.loc[selection, 'fit_lsb_ps'], label='fit %s'%gain, ls=ls[i], color='tab:blue')

            selection2 = (calib_table.gain == gain)  & (calib_table.toa == 100)
            plt.plot(calib_table.loc[selection2, 'channel'], calib_table.loc[selection2, 'lsb_fromCAL'], label='calib %s'%gain, ls=ls[i], color='tab:green')
            # whatever toa bin = all have the same lsb_fromCAL value from analysis !

        plt.xlabel('Channel')
        plt.ylabel('LSB [ps]')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(config['output_folder'] + '/NL/LSB_fit_vs_LSB_fromCAL.png')
        # plt.show()
        plt.close()


def plot_calib_lsb(df, config):


    local_output_folder = config['output_folder'] + '/calib_lsb/'
    if not os.path.exists(local_output_folder):
        os.makedirs(local_output_folder)

    tdc_CAL_df = pd.read_csv(config['output_folder'] + '/tdc_CAL_stats_per_channel.csv')

    board_list = get_board_list_from_df(df)

    for board in board_list:
        board_config = config['config_B%d'%board]
        channel_gain_list = board_config['tdc_injected'][0]


        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111)
        plt.title("Extrapolated TDC CTR FWHM versus channel")
        rms2FWHM = (math.log(2)*8)**0.5
        for gain in channel_gain_list:
            lsb_selection = (tdc_CAL_df.gain == gain)
            ax.scatter(tdc_CAL_df.loc[lsb_selection, 'channel'],
                       tdc_CAL_df.loc[lsb_selection, 'std_delta']*rms2FWHM*tdc_CAL_df.loc[lsb_selection, 'mean_lsb_fromCAL'], label=gain + ' gain')
        plt.axvline(x=-0.5, color='black', linestyle='--', label='GND pads', alpha=0.5)
        plt.axvline(x=19.5, color='black', linestyle='--', alpha=0.5)
        plt.axvline(x=55.5, color='black', linestyle='--', alpha=0.5)
        plt.axvline(x=3.5, color='red', linestyle='--', label='VDD pads', alpha=0.5)
        plt.axvline(x=24.5, color='red', linestyle='--', alpha=0.5)
        plt.axvline(x=43.5, color='red', linestyle='--', alpha=0.5)
        ax.set_xlabel('Channel')
        ax.grid()
        ax.legend()
        ax.set_ylabel('In coincidence TDC jitter FWHM [ps] ')
        plt.tight_layout()
        plt.savefig(local_output_folder + '/TDC_jitter_vs_channel.png')
        plt.close()



        # Best channel according to jitter on calibration lsb
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111)
        plt.title("LSB jitter obtained from TDC self-calibration versus channel")
        for gain in channel_gain_list:
            lsb_selection = (tdc_CAL_df.gain == gain)
            ax.scatter(tdc_CAL_df.loc[lsb_selection, 'channel'],
                             tdc_CAL_df.loc[lsb_selection, 'std_lsb_fromCAL'], label=gain + ' gain')


        plt.axvline(x=-0.5, color='black', linestyle='--', label='GND pads', alpha=0.5)
        plt.axvline(x=19.5, color='black', linestyle='--', alpha=0.5)
        plt.axvline(x=55.5, color='black', linestyle='--', alpha=0.5)
        plt.axvline(x=3.5, color='red', linestyle='--', label='VDD pads', alpha=0.5)
        plt.axvline(x=24.5, color='red', linestyle='--', alpha=0.5)
        plt.axvline(x=43.5, color='red', linestyle='--', alpha=0.5)
        ax.set_xlabel('Channel')
        ax.grid()
        ax.legend()
        ax.set_ylabel('Absolute LSB precision [ps] ')
        plt.tight_layout()
        plt.savefig(local_output_folder + '/absolute_lsb_jitter_vs_channel.png')
        plt.close()
        # plt.show()


        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111)
        plt.title("LSB jitter obtained from TDC self-calibration versus channel")
        for gain in channel_gain_list:
            lsb_selection = (tdc_CAL_df.gain == gain)
            ax.scatter(tdc_CAL_df.loc[lsb_selection, 'channel'],
                        tdc_CAL_df.loc[lsb_selection, 'std_lsb_fromCAL'] / tdc_CAL_df.loc[
                            lsb_selection, 'mean_lsb_fromCAL'] * 1000, label=gain + ' lsb')

        plt.axvline(x=-0.5, color='black', linestyle='--', label='GND pads', alpha=0.5)
        plt.axvline(x=19.5, color='black', linestyle='--', alpha=0.5)
        plt.axvline(x=55.5, color='black', linestyle='--', alpha=0.5)
        plt.axvline(x=3.5, color='red', linestyle='--', label='VDD pads', alpha=0.5)
        plt.axvline(x=24.5, color='red', linestyle='--', alpha=0.5)
        plt.axvline(x=43.5, color='red', linestyle='--', alpha=0.5)
        ax.set_xlabel('Channel')
        ax.grid()
        ax.legend()
        ax.set_ylabel('Relative LSB precision [‰] ')
        plt.tight_layout()
        plt.savefig(local_output_folder + '/relative_lsb_jitter_vs_channel.png')
        plt.close()


        plt.figure(1, figsize=(10, 7))
        plt.title("LSB obtained from TDC self-calibration versus channel")
        for gain in channel_gain_list:
            lsb_selection = (tdc_CAL_df.gain == gain)  # & (tdc_CAL_df.std_lsb_fromCAL < threshold_ps)
            plt.scatter(tdc_CAL_df.loc[lsb_selection, 'channel'],
                             tdc_CAL_df.loc[lsb_selection, 'mean_lsb_fromCAL'], label=gain + ' gain')

        plt.axvline(x=-0.5, color='black', linestyle='--', label='GND pads')
        plt.axvline(x=19.5, color='black', linestyle='--')
        plt.axvline(x=55.5, color='black', linestyle='--')
        plt.axvline(x=3.5, color='red', linestyle='--', label='VDD pads')
        plt.axvline(x=24.5, color='red', linestyle='--')
        plt.axvline(x=43.5, color='red', linestyle='--')
        plt.xlabel('Channel')
        plt.ylabel('LSB [ps] ')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_folder + '/lsb_vs_channel.png')
        plt.close()

        plt.figure(2, figsize=(10, 8))
        plt.title("Absolute jitter of the LSB obtained from TDC self-calibration versus channel")
        for gain in channel_gain_list:
            lsb_selection = (tdc_CAL_df.gain == gain)
            plt.scatter(tdc_CAL_df.loc[lsb_selection, 'channel'],
                        tdc_CAL_df.loc[lsb_selection, 'std_lsb_fromCAL'] / np.sqrt(tdc_CAL_df.loc[lsb_selection, 'mean_delta']), label=gain)

        plt.axvline(x=-0.5, color='black', linestyle='--', label='GND pads')
        plt.axvline(x=19.5, color='black', linestyle='--')
        plt.axvline(x=55.5, color='black', linestyle='--')
        plt.axvline(x=3.5, color='red', linestyle='--', label='VDD pads')
        plt.axvline(x=24.5, color='red', linestyle='--')
        plt.axvline(x=43.5, color='red', linestyle='--')
        plt.xlabel('Channel')
        plt.ylabel('Delay-cell jitter [ps] ')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_folder + '/delay_cell_jitter.png')
        plt.close()
        # plt.show()


        plt.figure(3, figsize=(9, 6))
        plt.title("Histogram of LSB obtained from TDC self-calibration ")
        # for gi, gain in enumerate(channel_gain_list):
        # plt.subplot(1, 2, gi+1)
        # plt.title(gain)
        # lsb_selection = (tdc_CAL_df.gain == gain)
        # serie_to_fit = tdc_CAL_df.loc[lsb_selection, 'mean_lsb_fromCAL']
        serie_to_fit = tdc_CAL_df.loc[:, 'mean_lsb_fromCAL']
        counts, bins = np.histogram(serie_to_fit, bins=50, density=True)
        plt.stairs(counts, bins, fill=True, label='%d out of 129 TDC'%len(tdc_CAL_df))

        try:
            p0 = [bins[np.argmax(counts)], 1, max(counts)]
            # print(p0)
            fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)  # , bounds= [(250, 1023)])
            meanHisto = fitParam[0]
            sigmaHisto = fitParam[1]
            ampHisto = fitParam[2]
            # print(fitParam)

            xmin = meanHisto - 3 * sigmaHisto
            xmax = meanHisto + 3 * sigmaHisto
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)

            plt.plot(xfit, yfit, linestyle='--', color='red',
                     label='Fit mean %.2f ps  sigma = %.2f ps' % (meanHisto, sigmaHisto))

        except RuntimeError as e:
            print("Fail to fit")
            print(e)
        plt.ylabel('Count')
        plt.xlabel('LSB [ps] ')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_folder + '/calib_lsb_histo.png')
        # plt.show()
        plt.close()


        plt.figure(4, figsize=(9, 6))
        plt.title("LSB obtained from TDC self-calibration versus channel")
        for gain in channel_gain_list:
            lsb_selection = (tdc_CAL_df.gain == gain)
            plt.errorbar(tdc_CAL_df.loc[lsb_selection, 'channel'],
                             tdc_CAL_df.loc[lsb_selection, 'mean_lsb_fromCAL'],
                             yerr= tdc_CAL_df.loc[lsb_selection, 'std_lsb_fromCAL'],
                             linestyle='dotted', label=gain) #fmt='o'
        ls='solid'
        lw=1
        plt.axvline(x=-0.5, color='black', linestyle=ls, linewidth=lw, label='GND pads')
        plt.axvline(x=19.5, color='black', linestyle=ls, linewidth=lw)
        plt.axvline(x=55.5, color='black', linestyle=ls, linewidth=lw)
        plt.axvline(x=3.5, color='red', linestyle=ls, linewidth=lw, label='VDD pads')
        plt.axvline(x=24.5, color='red', linestyle=ls, linewidth=lw)
        plt.axvline(x=43.5, color='red', linestyle=ls, linewidth=lw)
        plt.xlabel('Channel')
        plt.ylabel('LSB [ps] ')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_folder + '/calib_lsb_vs_ch.png')
        # plt.show()
        plt.close()



        group_size = 10000
        moving_average_calib_lsb_vs_time_per_channel_list = []
        # injected_channel_list = [0, 1, 7, 14] #, 16, 19, 20, 39, 40, 23, 24, 43, 44]

        channel_suffix_list = get_suffix_list_from_frames(df, board=board)

        for channel_suffix in channel_suffix_list:
            gain, channel, _ = get_board_ch_gain_from_suffix(channel_suffix)

            selection = df['tdc_data_valid' + channel_suffix]

            # subset = df.loc[non_null_delta_channel_selection, 'lsb_fromCAL' + channel_gain_suffix]
            subset = 2*3.125/df.loc[selection, 'delta' + channel_suffix]
            moving_average_calib_lsb_vs_time = subset.groupby({x: x // group_size for x in range(len(subset))}).mean()

            moving_average_calib_lsb_vs_time = (moving_average_calib_lsb_vs_time - moving_average_calib_lsb_vs_time.iloc[0]) /moving_average_calib_lsb_vs_time.iloc[0]*100# convert into ps
            moving_average_calib_lsb_vs_time_per_channel_list.append(moving_average_calib_lsb_vs_time.values)


        # truncate to equalise length/make array homogeneous
        n = min(map(len, moving_average_calib_lsb_vs_time_per_channel_list))
        moving_average_calib_lsb_vs_time_per_channel = []
        for a in moving_average_calib_lsb_vs_time_per_channel_list:
            moving_average_calib_lsb_vs_time_per_channel.append(a[:n])

        moving_average_calib_lsb_vs_time_per_channel_list = np.array(moving_average_calib_lsb_vs_time_per_channel)

        # # find n-th largest/smallest element among calib lsb for the last moving averaged
        N = 2
        last_group_moving_average_calib_lsb_vs_time_per_channel_list = moving_average_calib_lsb_vs_time_per_channel_list.T[-1].flatten()
        # Sort an array quickly : sort only the element at the ranking position of interest : N or (-N)
        threshold_max = np.partition(last_group_moving_average_calib_lsb_vs_time_per_channel_list, -N)[-N]
        threshold_min = np.partition(last_group_moving_average_calib_lsb_vs_time_per_channel_list, N)[N]

        plt.figure(5, figsize=(9, 6))
        plt.title("Average of the calib LSB over %d consecutive samples versus time\nOnly plotting best/worst channels"%group_size)

        channel_suffix_list = get_suffix_list_from_frames(df, board=board)

        for ci, channel_suffix in enumerate(channel_suffix_list):
            gain, channel, _ = get_board_ch_gain_from_suffix(channel_suffix)
            moving_average_calib_lsb_vs_time = moving_average_calib_lsb_vs_time_per_channel_list[ci]

            if (moving_average_calib_lsb_vs_time[-1]>=threshold_max) | (moving_average_calib_lsb_vs_time[-1]<=threshold_min):
                plt.plot(moving_average_calib_lsb_vs_time, label='Ch%d %s'%(channel, gain)) #, linestyle='--')
            # else:
            #     plt.plot(moving_average_calib_lsb_vs_time, linestyle='--')

            # plt.errorbar(moving_average_calib_lsb_vs_time, yerr=, label='Ch%d' % channel)
        plt.ylabel('Calib LSB variation [%]')
        plt.xlabel('Consecutive injection groups of size %d'%group_size)
        plt.grid()
        plt.legend(ncol=4)
        plt.tight_layout()
        plt.savefig(local_output_folder + '/cal_lsb_variation_across_time.png')
        # plt.show()
        plt.close()


        plt.figure(5, figsize=(9, 6))
        plt.title("TDC calibration LSB")
        ls=['dotted', 'solid']
        for gi, channel_gain in enumerate(channel_gain_list):
            selection = tdc_CAL_df.gain==channel_gain
            plt.plot(tdc_CAL_df.loc[selection, 'min_lsb_fromCAL'], label='min %s'%channel_gain, ls=ls[gi])
            plt.plot(tdc_CAL_df.loc[selection, 'median_lsb_fromCAL'], label='median %s'%channel_gain, ls=ls[gi])
            plt.plot(tdc_CAL_df.loc[selection, 'min_lsb_fromCAL'], label='min %s'%channel_gain, ls=ls[gi])
        plt.ylabel('Calib LSB variation [ps]')
        plt.xlabel('Channel')
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_folder + '/cal_lsb_variation_stats_vs_ch.png')
        # plt.show()
        plt.close()



        # select on channel in particular
        plt.figure(6, figsize=(10, 7))
        channel_gain = 'low'
        channel = board_config['enable_TL_ASIC_ch'][0][0]  # first channel injected
        plt.title("Calibration LSB variation versus time - ch%d %s"%(channel, channel_gain))
        channel_gain_suffix = '_%s_ch%d_B%d' % (channel_gain, channel, board)
        selection = df['tdc_data_valid' + channel_gain_suffix]
        delta = df.loc[selection, 'delta' + channel_gain_suffix] #.reset_index(drop=True) todo
        lsb_fromCAL = 2*3125/delta
        calib_lsb_variation = (lsb_fromCAL - lsb_fromCAL.iloc[0])
        # plt.scatter(calib_lsb_variation.index, calib_lsb_variation, label='ch %d %s'%(channel, channel_gain), s=1)
        # xy = np.vstack([calib_lsb_variation.index, calib_lsb_variation])
        # z = gaussian_kde(xy)(xy)
        # ax.scatter(calib_lsb_variation.index, calib_lsb_variation, c=z, s=100)
        plt.plot(calib_lsb_variation.index, calib_lsb_variation)
        plt.ylabel('Calib LSB variation [ps]')
        plt.xlabel('time')
        plt.grid()
        # plt.legend()
        plt.tight_layout()
        plt.savefig(local_output_folder + '/cal_lsb_variation_vs_time_ch%d_%s.png'%(channel, channel_gain))
        # plt.show()
        plt.close()




        # samples_number = range(9)
        # lsb_collection = [[] for i in samples_number]
        # channel_index = []
        # sample_size = 50
        # for channel in injected_channel_list:
        #     for gi, channel_gain in enumerate(channel_gain_list):
        #
        #         cluster = channel // 16
        #         cluster_channel = channel % 16
        #
        #         channel_gain_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)
        #         selection = (df.cluster == cluster) & (df['tdc' + channel_gain_suffix] != 0)
        #         tdc_serie = df.loc[selection, 'lsb_fromCAL'+channel_gain_suffix].reset_index(drop=True)
        #
        #         initial_offset = tdc_serie.iloc[0]
        #         for i in samples_number:
        #             start_index=round(len(tdc_serie)*(i+1)/10)
        #             a = tdc_serie.iloc[start_index:start_index+sample_size]
        #             lsb_collection[i] += ((a - initial_offset)*1e3).to_list()
        #             pass
        #         channel_index += [channel*2+gi]*sample_size
        #         # channel_index += [channel]*sample_size
        #
        # # plt.figure(0, figsize=(10, 7))
        # # for i in samples_number:
        # #     plt.hist(lsb_collection, label='%d'%i, histtype='bar', stacked=True)
        # # plt.scatter(channel_index, lsb_collection)
        # # plt.show()
        # for i in samples_number:
        #     plt.figure(i, figsize=(10, 7))
        #
        #     x = np.array(channel_index)
        #     y = np.array(lsb_collection[i])
        #     # Calculate the point density
        #     xy = np.vstack([x, y])
        #     z = gaussian_kde(xy)(xy)
        #
        #     # Sort the points by density, so that the densest points are plotted last
        #     idx = z.argsort()
        #     x, y, z = x[idx], y[idx], z[idx]
        #
        #     plt.scatter(x, y, c=z, s=50)
        #
        #     plt.xlabel('Channel')
        #     plt.ylabel('LSB variation [ps]')
        #     plt.title("")
        #     plt.grid()
        #     # plt.legend(ncol=4)
        #     plt.tight_layout()
        # plt.show()
        # plt.savefig(local_output_folder + '/cal_lsb_variation_histo.png')

def plot_NL_vs_channel(config):

    df_NL = pd.read_csv(config['output_folder']+"/B2_tdc_CAL_stats_per_channel.csv")

    plt.figure(figsize=(7, 4))
    for gain in config['tdc_injected'][0]:
        df_NL = df_NL.loc[df_NL.gain==gain, :]
        # plt.plot(df_NL.channel, df_NL.INL_MIN_ps, label='INL_MIN_ps')
        plt.plot(df_NL.channel, df_NL.INL_RMS_ps, label='INL_RMS_ps')
        # plt.plot(df_NL.channel, df_NL.INL_MAX_ps, label='INL_MAX_ps')

        # plt.plot(df_NL.channel, df_NL.DNL_MIN_ps, label='DNL_MIN_ps')
        plt.plot(df_NL.channel, df_NL.DNL_RMS_ps, label='DNL_RMS_ps')
        # plt.plot(df_NL.channel, df_NL.DNL_MAX_ps, label='DNL_MAX_ps')

    # plt.plot(df_jitter.loc[channel_selection, 'chB'], df_jitter.loc[channel_selection, 'dt_fit_std'], label='fit std')
    # plt.scatter(df_jitter.loc[:, 'chB'], df_jitter.loc[:, 'dt_std'], label='std', marker='o')
    plt.legend()
    plt.title("Non-linearities versus channel")
    plt.ylabel("Non linearities [ps]")
    plt.xlabel('Channel')
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "NL_vs_channel.png")
    plt.show()
    plt.close()

def plot_delta_vs_channel(df, config):

    plt.figure(figsize=(7, 4))
    delta = []
    for gain in config['tdc_injected'][0]:
        for ch in config['enable_TL_ASIC_ch'][0]:
            suffix = '_%s_ch%d' % (gain, ch)

            delta += df.loc[df['tdc_data_valid'+suffix], 'delta'+suffix].tolist()

    delta = np.array(delta)
    counts, bins = np.histogram(delta, bins=np.arange(delta.min() - 0.5, delta.max() + 1.5, 1))  # , density=True)
    plt.hist(bins[:-1], bins, align='mid', weights=counts) #, label="rms = %.2f ps" % (de))  # edgecolor='white', linewidth=2,
    plt.grid()
    plt.xlabel("Delta [lsb]")
    plt.ylabel("Count")
    plt.title("Delta max = %d  min = %d => %d bits required out of 9 for CAL"%(delta.min(), delta.max(), np.ceil(np.log2(delta.max()- delta.min()))))
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "histo_delta_for_all_channel.png")
    plt.show()

    df_NL = pd.read_csv(config['output_folder']+"/B2_tdc_CAL_stats_per_channel.csv")
    plt.figure(figsize=(7, 4))
    for gain in config['tdc_injected'][0]:
        df_NL = df_NL.loc[df_NL.gain == gain, :]
        plt.errorbar(df_NL.channel, df_NL.mean_delta, yerr=df_NL.std_delta, label='mean_delta')

    plt.legend()
    plt.title("Delta calib versus channel")
    plt.ylabel("Delta [lsb]")
    plt.xlabel('Channel')
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "delta_vs_channel.png")
    plt.show()
    plt.close()


def check_lsb_cpt_metastability_when_ext_trigger(df, config):

    res = {'board': [],
           'gain': [],
           'channel': [],
           'lsb_cpt_metastability_percent': []}

    lsb_cpt_stats_file = config['output_folder'] + '/lsb_cpt_metastability.csv'
    selection_df = pd.DataFrame()

    if 1: #not os.path.exists(lsb_cpt_stats_file):
        for board in config['board']:
            board_config = config['config_B%d' % board]

            if config['source'] != 'ext_trigger':
                print('This verification can only be performed if channels injected simultaneously (ie ext_trigger) !')
                continue
            if config['random_phase'] != True:
                print(
                    'This verification can only be performed if channels injected asynchronously with respect to the digital clock !')
                continue

            for gain in board_config['tdc_injected'][0]:

                lsb_cpt_col = [col for col in df.columns if ('cpt' in col) & (gain in col) & ('B%d' % board in col)]
                channel_list = [int(re.findall("(?<=_ch)[0-9]+", col)[0]) for col in lsb_cpt_col]

                df_lsb_cpt_stats = df[lsb_cpt_col]
                df_lsb_cpt_stats = df_lsb_cpt_stats[~df_lsb_cpt_stats.eq(df_lsb_cpt_stats.iloc[:, 0], axis=0).all(1)]
                true_CPT = df_lsb_cpt_stats.apply(mode, axis=1)
                df_lsb_cpt_stats = df_lsb_cpt_stats.sub(true_CPT, axis=0)
                error_types = df_lsb_cpt_stats.apply(lambda x: set(x) ^ {0}, axis=1)

                # Manully check metastability errors
                # for error in error_types
                # for error in [15]:
                #
                #     selection = (error_types == {error})
                #
                #     for i,row in df_lsb_cpt_stats[selection].iterrows():
                #
                #         error_cpt_col = row[row==error].index.tolist()
                #         error_channels = [int(re.findall("(?<=_ch)[0-9]+", col)[0]) for col in error_cpt_col]
                #         error_toa_col = ['toa_low_ch%d_B%d'%(channel, board) for channel in error_channels]
                #
                #         good_channels = set(error_channels) ^ set(range(64))
                #         good_cpt_col = ['cpt_low_ch%d_B%d'%(channel, board) for channel in good_channels]
                #         good_toa_col = ['toa_low_ch%d_B%d'%(channel, board) for channel in good_channels]
                #
                #         df.iloc[i][error_cpt_col]
                #         df.iloc[i][good_cpt_col]
                #         df.iloc[i][good_toa_col]
                #         df.iloc[i][error_toa_col]

                print("Lsb cpt metastability error type detected: {error} : rate (%)")
                print("Errors should be +-1 and +-15 (~1/16th of +-1)")
                print(error_types.value_counts() / len(df) * 100)

                df_lsb_cpt_stats = df_lsb_cpt_stats.abs().replace(15, 1)
                metastability_percent_per_channel = df_lsb_cpt_stats.sum(axis=0) / len(df)*100

                res['board'] += [board]*len(channel_list)
                res['gain'] += [gain]*len(channel_list)
                res['channel'] += channel_list
                res['lsb_cpt_metastability_percent'] += metastability_percent_per_channel.values.tolist()


                if len(selection_df)>0:
                    selection_df = pd.concat([selection_df, df_lsb_cpt_stats], axis=1)
                else:
                    selection_df = df_lsb_cpt_stats

                # plt.figure(figsize=(7, 4))
                # toa_col = ['toa_low_ch%d_B%d' % (channel, board) for channel in board_config['injected_channel'][0]]
                # reference_toa = df['toa_low_ch43_B%d' % board]
                # # toa_mean = df[toa_col].sub(reference_toa, axis=0).mean(axis=0).values
                # # toa_std = df[toa_col].sub(reference_toa, axis=0).std(axis=0).values
                # # plt.errorbar(board_config['injected_channel'][0], toa_mean, yerr=toa_std, label='TOA', fmt='o')
                #
                # for channel in range(64):
                #     # toa_diff = df['toa_low_ch%d_B%d' % (channel, board)].sub(reference_toa, axis=0)
                #     # plt.plot(toa_diff.iloc[df_lsb_cpt_stats.index], label='lsb_cpt_error')
                #     # plt.plot(toa_diff.loc[~df.index.isin(df_lsb_cpt_stats.index)], label='good lsb cpt')
                #     # plt.legend()
                #
                #     # plt.title("")
                #     plt.ylabel("TOA [lsb]")
                #     plt.xlabel('Channel')
                #     plt.grid()
                #     plt.tight_layout()
                #     # plt.savefig(config['output_folder'] + "B%d_TOA_dispersion.png"%board)
                #     plt.show()
                #     plt.close()

        lsb_cpt_stats_df = pd.DataFrame(res)
        lsb_cpt_stats_df.to_csv(lsb_cpt_stats_file, index=False)



    else:
        lsb_cpt_stats_df = pd.read_csv(lsb_cpt_stats_file)

    plt.figure(figsize=(7, 4))
    for board in np.unique(lsb_cpt_stats_df.board):
        for gain in np.unique(lsb_cpt_stats_df.gain):
            selection = (lsb_cpt_stats_df.gain == gain) & (lsb_cpt_stats_df.board == board)
            x = lsb_cpt_stats_df.loc[selection, 'channel']
            y = lsb_cpt_stats_df.loc[selection, 'lsb_cpt_metastability_percent']
            metastability_lsb_cpt_avg_pourcent = y.mean()
            plt.scatter(x, y, label='B%d %s: average = %.2f %%' % (board, gain, metastability_lsb_cpt_avg_pourcent),
                        marker='o')

    plt.legend()
    plt.title("LSB CPT metastability occurrence probability wrt majority lsb")
    plt.ylabel("%")
    plt.xlabel('Channel')
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "lsb_cpt_metastability.png")
    # plt.show()
    plt.close()

    return selection_df

def analyse_code_density_internal_tdc(df, config, plot=True):

    compute_bin_width(df, config, plot=plot)
    compute_non_linearities(config, plot=plot)
    plot_NL(config)
    # lsb_cpt_selection_df = check_lsb_cpt_metastability_when_ext_trigger(df, config)

    analyse_calib_lsb(df, config)
    plot_calib_lsb(df, config)

    compute_inter_channel_jitter_and_delay(df, config, plot=False)
    # plot_inter_channel_jitter_and_delay(df, config)

    pass
    # df, output_folder, config, folder_index_str, files = analyse_init(search_folder, other_cols_to_drop=[])
    #
    # # if len(df) == 0:
    #     # print("No data")
    #     # exit(0)

    # df2_filepath = output_folder + "2.feather"
    # if not os.path.exists(df2_filepath):
    #     df = drop_not_injected_channels(df, config)
    #     df = drop_not_injected_gain(df, config)
    #     df = drop_adc_columns(df)
    #     df.to_feather(df2_filepath)
    # else:
    #     df = pd.read_feather(df2_filepath)



    # for gain in config['tdc_injected'][0]:
    #     for ch in set(config['injected_channel'][0]):
    #         channel_suffix = '_%s_ch%d' % (gain, ch)
    #         selection = df['tdc_data_valid'+channel_suffix]
    #         plt.scatter(df.loc[selection, 'toa'+channel_suffix], df.loc[selection, 'cal'+channel_suffix])
    #         plt.grid()
    #         plt.title(channel_suffix)
    #         plt.show()

    # for gain in config['tdc_injected'][0]:
    #     for ch in set(config['injected_channel']):
    #         channel_suffix = '_%s_ch%d' % (gain, ch)
    #         selection = df['tdc_data_valid'+channel_suffix]
    #         for toa in df.loc[selection, 'toa' + channel_suffix]:
    #             plt.hist(df.loc[selection & (df.loc[selection, 'toa' + channel_suffix]==toa), 'cal'+channel_suffix])
    #             plt.grid()
    #             plt.title(channel_suffix+' toa %d'%toa)
    #             plt.show()

    # plot_lsb_vs_time(df, config)
    # plot_delta_vs_channel(df, config)
    # plot_NL_vs_channel(config)



def compute_inter_channel_jitter_and_delay(df, config, plot=False):

    method_list = ['lsb_fromCAL', 'lsb_fromCAL_mean', 'DNL_TOA']   # 'DNL_TOA_CAL' 'lsb_fromFIT'
    if config['save_folder'] != '../output/serial_test/B6_TPR108/1/raw/':
        method_list.append('ref_DNL_TOA')
    ref_DNL_TOA_calib_table_filename ='../output/serial_test/B6_TPR108/1/tdc/tdc_DNL_TOA_calib_table.csv'

    df_channels_time_diff_filename = config['output_folder'] + 'tdc_jitter_between_channel.csv'

    if os.path.exists(df_channels_time_diff_filename):
        print("Skipping compute_inter_channel_jitter_and_delay(): already existing results ! !")
        return df
    else:
        print("compute_inter_channel_jitter_and_delay")

        res = {'board': [],
               'chA': [],
               'gainA': [],
               'chB': [],
               'gainB': [],
               }
        for time_conversion_method in method_list:
            res.update({'%s_%s' % (meas, time_conversion_method): [] for meas in
                        ['dt_mean', 'dt_std', 'dt_fit_mean', 'dt_fit_std']})  #, 'perr_fit'

            channel_folder = config['output_folder'] + '/diff_inter_channel/' + '/%s/' % time_conversion_method
            if not os.path.exists(channel_folder):
                os.makedirs(channel_folder)

        brand_new_series_set = {}
        tmp_series_set = {}
        tdc_CAL_df = pd.read_csv(config['output_folder'] + '/tdc_CAL_stats_per_channel.csv')
        toa_NL_stats_df = pd.read_csv(config['output_folder'] + '/tdc_NL_stats_per_channel.csv')

        for board in config['board']:
            board_config = config['config_B%d'%board]
            tempo_dig_ck = board_config['tempo_dig_ck']

            if 24 in board_config['enable_TL_ASIC_ch'][0]:
                chA = 24  # lowest jitter on lsb from cal
            else:
                chA = board_config['enable_TL_ASIC_ch'][0]

            for gain in board_config['tdc_injected'][0]:
                gainA = gainB = gain
                channel_suffixA = '_%s_ch%d_B%d' % (gainA, chA, board)

                channel_list = list(set(board_config['enable_TL_ASIC_ch'][0]) ^ {chA})
                for chB in channel_list:
                    if (chB == chA) & (gainB == gainA):
                        continue

                    res['board'].append(board)
                    res['chA'].append(chA)
                    res['gainA'].append(gainA)
                    res['chB'].append(chB)
                    res['gainB'].append(gainB)

                    channel_suffixB = '_%s_ch%d_B%d' % (gainB, chB, board)
                    tdc_good_selection = df['tdc_good' + channel_suffixA] & df['tdc_good' + channel_suffixB]

                    for time_conversion_method in method_list:

                        channel_folder = config['output_folder'] + '/diff_inter_channel/' + '/%s/' % time_conversion_method

                        for ch, gain in zip([chA, chB], [gainA, gainB]):
                            df = compute_ps_time_within_one_msb_cpt(df, config, ch, gain, board, time_conversion_method,
                                                                    tdc_CAL_df = tdc_CAL_df, toa_NL_stats_df=toa_NL_stats_df,
                                                                    ref_DNL_TOA_calib_table_filename = ref_DNL_TOA_calib_table_filename)

                        dt = df['toa_ps' + channel_suffixA] - df['toa_ps' + channel_suffixB]
                        brand_new_series_set['diff_toa_ps' + channel_suffixA + '_' + channel_suffixB] = dt
                        subset = dt[tdc_good_selection]

                        # outlier_count_list = []
                        # outlier_with_cpt_error_by_one_count_list = []
                        # outlier = (subset.abs() > (abs(subset.median()) + 3125))
                        # outlier_count = (len(df)-(outlier.value_counts()[False]))/len(df)*100
                        # outlier_with_cpt_error_by_one_count = (len(df)-(((df['cpt' + channel_suffixA] - df['cpt' + channel_suffixB]).abs()==1) & (subset.abs() > (abs(subset.median()) + 3125))).value_counts()[False])/len(df)*100
                        # outlier_with_cpt_error_by_one_count_list.append(outlier_with_cpt_error_by_one_count)
                        # outlier_count_list.append(outlier_count)

                        # Histogram
                        if len(subset)==0:
                            print("Empty dataset ! ch%d %s - ch%d %s"%(chA, gainA, chB, gainB))
                            continue

                        dt_rms = subset.std()
                        sigma_fit = mean_fit = 0
                        # perr_fit = 0
                        xfit = yfit = np.nan

                        try:
                            bins = np.arange(subset.min() - 0.5, subset.max() + 1.5, 10)  # 30 ps bin smaller than tdc lsb
                            if len(bins) > 100:
                                print('len(bins) for chB %s '%channel_suffixB + str(len(bins)))
                                bins = np.arange(subset.min() - 0.5, subset.max() + 1.5, 50)
                                # suspicious of lsb cpt error

                                # z = np.abs(stats.zscore(subset))
                                # df[z > 3]

                                # plt.figure()
                                # plt.hist(subset)
                                # plt.show()
                                # raise Exception

                        except Exception:
                            pass

                        if dt_rms > 0:
                            try:
                                counts, bins = np.histogram(subset, bins=bins, density=True)
                                # p0 = [bins[np.argmax(counts)], 2*dt_rms, 1]
                                # p0 = [subset.median(), 2*dt_rms, max(counts)]
                                p0 = [subset.mean(), dt_rms, 1]
                                # print(p0)
                                fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)
                                mean_fit = fitParam[0]
                                sigma_fit = fitParam[1]
                                ampHisto = fitParam[2]
                                # print(fitParam)
                                # perr = np.sqrt(np.diag(cov))

                                xmin = mean_fit - 3 * sigma_fit
                                xmax = mean_fit + 3 * sigma_fit
                                xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
                                yfit = modelGauss(xfit, mean_fit, sigma_fit, ampHisto)

                            except (OptimizeWarning, RuntimeError) as e:
                                print("Fail to fit ch%d %s - ch%d %s" % (chA, gainA, chB, gainB))
                                print(e)


                        if plot:  # (dt_rms < 20) | (dt_rms > 30) |
                            # Plot with constant lsb
                            counts, bins = np.histogram(subset, bins=bins, density=True)
                            plt.figure(figsize=(8, 5))
                            plt.hist(bins[:-1], bins, align='mid', weights=counts,
                                     label="rms = %.2f ps " %dt_rms) # edgecolor='white', linewidth=2,

                            plt.plot(xfit, yfit, linestyle='--', color='red',
                                     label='Fit mean %.2f  sigma = %.2f ps RMS' % (mean_fit, sigma_fit))

                            plt.legend()
                            plt.title("TOA difference ch%d %s - ch%d %s %s"%(chA, gainA, chB, gainB, time_conversion_method))
                            plt.ylabel('Count')
                            plt.xlabel('TOA [ps]')
                            plt.grid()
                            plt.tight_layout()
                            plt.savefig(channel_folder+"ch%d_%s-ch%d_%s.png"%(chA, gainA, chB, gainB))
                            # if sigma_fit<25: # display outlier
                            #     plt.show()
                            plt.close()

                        res['dt_fit_mean_'+time_conversion_method].append(mean_fit)
                        res['dt_fit_std_'+time_conversion_method].append(sigma_fit)
                        res['dt_std_'+time_conversion_method].append(dt_rms)
                        res['dt_mean_'+time_conversion_method].append(subset.mean())
                        # res['perr_fit_'+time_conversion_method].append(perr)

        df_jitter = pd.DataFrame(res)
        df_jitter.to_csv(df_channels_time_diff_filename, index=False)

        df = pd.concat([df, pd.DataFrame(brand_new_series_set)], axis=1)
        return df

def plot_inter_channel_jitter_and_delay(df, config):
    df_channels_time_diff_filename = config['output_folder'] + 'tdc_jitter_between_channel.csv'

    df_jitter = pd.read_csv(df_channels_time_diff_filename)
    tdc_CAL_df = pd.read_csv(config['output_folder'] + '/tdc_CAL_stats_per_channel.csv')

    time_conversion_method_list = [col[7:] for col in df_jitter.columns if col.startswith('dt_mean')]
    channel_folder = config['output_folder'] + '/diff_inter_channel/'
    if not os.path.exists(channel_folder):
        os.makedirs(channel_folder)

    rms2FWHM = (math.log(2)*8)**0.5

    for board in config['board']:
        selection = df_jitter.board == board
        chA = int(np.unique(df_jitter.loc[selection,'chA']))

        # JITTER
        for time_conversion_method in time_conversion_method_list:
            color_list = ['tab:green', 'tab:blue']
            # fig, (ax1, ax2) = plt.subplots(2, 1, figsize=[12, 7], height_ratios=[3, 1])
            fig, ax1 = plt.subplots(1, 1, figsize=[12, 7])
            for gi, gain in enumerate(np.unique(df_jitter.loc[selection,'chB_gain'])):
            # for gi, gain in enumerate(['low']):
                    channel_selection = (df_jitter.chB_gain==gain) & selection
                    x = df_jitter.loc[channel_selection, 'chB']
                    y = df_jitter.loc[channel_selection, 'dt_std'+time_conversion_method]
                    label = ("Best/Worst channel (%d/%d) : %d/%d ps FWHM "
                             %(np.nanargmin(y), np.nanargmax(y), np.nanmin(y)*rms2FWHM, np.nanmax(y)*rms2FWHM))

                    ax1.plot(x, y, label=gain + ' np.std '+label, color = color_list[gi])
                    yfit = df_jitter.loc[channel_selection, 'dt_fit_std'+time_conversion_method].replace(0, np.nan)
                    # Mask outliers
                    yfit_masked = yfit
                    mask = np.abs(yfit-y)>15
                    outlier_channel = np.array(range(len(mask)))[mask]
                    yfit_masked[mask] = np.nan
                    # label = ("Best/Worst channel (%d/%d) : %d/%d ps FWHM\nExcluded channels: "
                    #          %(np.nanargmin(yfit_masked), np.nanargmax(yfit_masked),
                    #            np.nanmin(yfit_masked)*rms2FWHM, np.nanmax(yfit_masked)*rms2FWHM) + str(outlier_channel))
                    # yfit_masked
                    ax1.scatter(x, yfit, label=gain+' Gaussian fit', ls='dotted',
                                color = color_list[gi], marker="+")

                    # perr_fit = df_jitter.loc[channel_selection, 'perr_fit' + time_conversion_method]
                    # ax2.plot(x, perr_fit)

            ax1.legend()
            ax1.set_title("CTR channel %d - channel compared "%chA + time_conversion_method)
            ax1.set_ylabel("RMS jitter [ps]")
            ax1.set_xlabel('Compared channel')
            ax1.grid()
            # ax2.grid()
            fig.tight_layout()
            fig.savefig(channel_folder + "B%d_tdc_jitter_%s.png"%(board, time_conversion_method))
            # plt.show()
            plt.close()


        # Compared between time_conversion_method
        masked_channels = {'_lsb_fromCAL':[14,20,22,27,28,32,43],
                           '_DNL_TOA':[]}

        # method_list = ['lsb_fromCAL', 'lsb_fromCAL_mean', 'DNL_TOA', 'ref_DNL_TOA']
        # method_list = list(set(time_conversion_method_list) ^ {'_lsb_fromFIT'})
        method_list = ['_lsb_fromCAL', '_lsb_fromCAL_mean', '_DNL_TOA']
        for gain in np.unique(df_jitter.loc[selection,'chB_gain']):
            plt.figure(figsize=(12, 7))
            channel_selection = (df_jitter.chB_gain == gain) & selection
            x = df_jitter.loc[channel_selection, 'chB']
            for time_conversion_method in method_list:
                y = df_jitter.loc[channel_selection, 'dt_std'+time_conversion_method]
                plt.plot(x, y, label=time_conversion_method[1:]) #, marker='+')

            selection_floor_jitter = (tdc_CAL_df.board == board) & (tdc_CAL_df.gain == gain)
            subset = tdc_CAL_df.loc[selection_floor_jitter,:].sort_values(by='channel')
            lsb_chA = subset.loc[selection_floor_jitter & (tdc_CAL_df.channel==chA), 'mean_lsb_fromCAL'].iloc[0]
            lsb_chB = subset.loc[selection_floor_jitter, 'mean_lsb_fromCAL'].values
            chB = subset.loc[selection_floor_jitter, 'channel'].values
            floor_jitter = np.maximum(lsb_chA, lsb_chB)/(12**0.5)
            plt.plot(chB, floor_jitter, label=r"Quantization limit = LSB/$\sqrt{12}$ (largest LSB among chA&B)",
                     ls='dashed', color='tab:red')
            plt.legend()
            plt.title("CTR channel %d %s - channel %s compared "%(chA, gain, gain))
            plt.ylabel("RMS jitter [ps]")
            plt.xlabel('Compared channel ')
            plt.grid()
            plt.tight_layout()
            plt.savefig(channel_folder + "B%d_%s_jitter_method_comparison.png"%(board, gain))
            # plt.show()
            plt.close()


        # DELAY
        plt.figure(figsize=(12, 7))
        for gain in np.unique(df_jitter.loc[selection,'chB_gain']):
            channel_selection = (df_jitter.chB_gain==gain) & selection
            for time_conversion_method in time_conversion_method_list:
                toa_mean_dispersion = df_jitter.loc[channel_selection, 'dt_mean'+time_conversion_method].std()
                plt.scatter(df_jitter.loc[channel_selection, 'chB'], df_jitter.loc[channel_selection, 'dt_mean'+time_conversion_method],
                            label='TDC '+gain+' '+time_conversion_method ) #+' toa std = %d ps'%toa_mean_dispersion, marker='o')

        plt.legend()
        plt.title("TDC TOA dispersion : time difference ch%d - ch? "%chA)
        plt.ylabel("Delay with reference channel %d [ps]"%chA)
        plt.xlabel('Compared channel')
        plt.grid()
        plt.tight_layout()
        plt.savefig(channel_folder + "B%d_tdc_toa_delay.png"%board)
        # plt.show()
        plt.close()

    pass

def compare_inter_channel_jitter(search_folder):

    files = glob.glob(search_folder + "**/time_diff_stats.csv")
    plt.figure(figsize=(8, 5))
    markers = ['o', 'x', '.', '+']
    for i, file in enumerate(files):
        df_jitter = pd.read_csv(file)

        config_file = os.path.dirname(file) + "/config_post_analysis.yaml"
        with open(config_file, 'r') as outfile:
            config = yaml.safe_load(outfile)
        outfile.close()

        folder = os.path.basename(os.path.normpath(file+'/../'))

        for gain in config['tdc_injected'][0]:
            channel_selection = (df_jitter.chB_gain==gain) #(df_jitter.dt_std < 100)
            plt.scatter(df_jitter.loc[channel_selection, 'chB'], df_jitter.loc[channel_selection, 'dt_std'], marker=markers[i], label=folder+' TDC '+gain)
        # plt.plot(df_jitter.loc[channel_selection, 'chB'], df_jitter.loc[channel_selection, 'dt_fit_std'], label='fit std')
        # plt.scatter(df_jitter.loc[:, 'chB'], df_jitter.loc[:, 'dt_std'], label='std', marker='o')
    plt.legend()
    plt.title("Time difference chA 43 - chB ?")
    plt.ylabel("Jitter as std [ps]")
    plt.xlabel('ChB')
    plt.grid()
    plt.tight_layout()
    plt.savefig(search_folder+ "time_difference_jitter.png")
    plt.show()
    plt.close()

def analyse_jitter_internal_tdc(folder):

    df_filepath = glob.glob(folder+'*2.csv')
    df = pd.read_csv(df_filepath[0])

    channel_gain = 'low'
    channel = 0
    suffix = '_%s_ch%d' % (channel_gain, channel)

    col = ['TOAcoarse' + suffix, 'TOAfine' + suffix,  'toa' + suffix, 'CALcoarse' + suffix, 'CALfine' + suffix, 'cal' + suffix]

    # histogram
    # for mi, modeRO in enumerate(np.unique(df.modeRO)):
    #     selection = (df.modeRO == modeRO) & df.good_cpt_good_tdc_selection
    #     for ri,real_time in enumerate(np.unique(df.loc[(df.real_time_ns < 13.05) & (df.real_time_ns > 13), 'real_time_ns'])):
    #     # for ri, real_time in enumerate(np.unique(df.loc[(df.real_time_ns < 13.48) & (df.real_time_ns > 13.45), 'real_time_ns'])):
    #
    #         plt.figure(ri, figsize=(10, 8))
    #         for i, field in enumerate(col):
    #             plt.subplot(2, 3, i + 1)
    #
    #             plt.hist(df.loc[selection & (df.real_time_ns == real_time), field], label='real_time %.1f ns' % real_time)
    #             plt.ylabel('Count')
    #             plt.legend()
    #             plt.xlabel(field)
    #             plt.grid()
    #         plt.suptitle('Jitter for mode ' + modeRO)
    #         plt.tight_layout()
    #
    #         plt.show()
    #         plt.close()

    df_jitter = pd.pivot_table(df[df.good_cpt_good_tdc_selection|df.bad_cpt_good_tdc_selection], values=col, index=['modeRO', 'real_time_ns'], aggfunc='std')

    for mi, modeRO in enumerate(np.unique(df.modeRO)):
        plt.figure(mi, figsize=(10, 8))
        for i, field in enumerate(col):
            plt.subplot(2, 3, i+1)
            if df_jitter.index.isin([(modeRO,)]).any():
                plt.scatter(df_jitter.loc[(modeRO, ), :].index, df_jitter.loc[(modeRO, ), field])
            plt.title(field)
            plt.ylabel('Jitter')
            if i>3:
                plt.xlabel('Real time [ns]')
            plt.grid()
        plt.suptitle('Jitter for mode '+modeRO)
        plt.tight_layout()
        plt.savefig(folder+'jitter_'+modeRO+'.png')
        # plt.show()


    pass


def rename_files(search_folder):
    files = glob.glob(search_folder)
    for file in files:
        # new_filename = file.replace(file[40:42], '0_')
        # new_filename = file.replace(file[40:44], '0_B2')
        new_filename = file.replace(file[40:43], 'B')
        try:
            os.rename(file, new_filename)
        except FileExistsError as e:
            print("FileExistsError", file)
            os.remove(file)
            continue

def check_null_data():
    df = pd.read_csv("output/tdc_scan/internal/code_density/dig_ck_160_MHz/raw/0/B1_VDDD_1.34V_cluster_0.csv")
    # 22 is index of ch0 low
    # 70 is index of ch0 high
    # x-16 is 4bit counter associated
    df[df.iloc[:, 70] == '00000'].iloc[:, 70 - 16].drop_duplicates()  # always 0
    df[(df.iloc[:, 70] == '00000') | (df.iloc[:, 22] == '00000')].index.diff().value_counts()  # pattern by 23/70/100
    pass

def concat_results():
    folder = "output/tdc_scan/internal/code_density/dig_ck_160_MHz/raw/"
    for cluster in range(4):
        df = pd.DataFrame()
        for i in range(1,6):
            df_tmp = pd.read_csv(folder+'/%d/B1_VDDD_1.34V_cluster_%d.csv'%(i, cluster))
            df = pd.concat([df, df_tmp])
        df.to_csv(folder+'/%d/B1_VDDD_1.34V_cluster_%d.csv'%(1, cluster))



if __name__ == '__main__':

    # analyse_linearity_internal_tdc("output/internal_tdc/ch_0/delaybox_step/raw/0*.csv")
    # analyse_jitter_internal_tdc("output/internal_tdc/ch_0/delaybox_step/0/")
    # rename_files("output/internal_tdc/delaybox_step/raw/3/3_B*.csv")

    # analyse_multichannel_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_320_MHz/5/raw/")

    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/1/raw/")
    # concat_results()

    # analyse_multichannel_delaybox_step_internal_tdc("../output/tdc_scan/internal/delaybox_step/dig_ck_40_MHz/raw/2/")
    # for i in range(4):
    # analyse_multichannel_custom_step_internal_tdc("../output/tdc_scan/internal/custom_step/dig_ck_40_MHz/raw/40/")
    # analyse_multichannel_custom_step_internal_tdc("../output/tdc_scan/internal/custom_step/dig_ck_320_MHz/raw/7/")

    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B1/0_ch7_23_40_48_60/raw/")
    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/2_all_128_tdc/raw/")
    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/3_ch7_23_40_48_60/raw/")
    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_40_MHz/B2/0/raw/")
    # root_folder = "//192.168.2.143/temporoc/temporoc_sw/output/"
    # root_folder = "//PC-WEEROC20/temporoc/temporoc_sw/output/"
    root_folder = "C:\\Users\\weeroc\\temporoc\\temporoc_sw\\"

    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B1/1_64_low_tdc/raw/")
    # analyse_code_density_internal_tdc("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/1_64_low_tdc/raw/")
    # compare_inter_channel_jitter("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/")


    # plt.figure(figsize=(7, 4))
    # folder = 'time_diff_stats_DNL_TOA.cs'
    # for method in ['lsb_fromCAL', 'DNL_TOA']: #, 'DNL_TOA_CAL']:
    #     df_jitter = pd.read_csv("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/1_64_low_tdc/time_diff_stats_"+method+'.csv')
    #     for gain in np.unique(df_jitter.chB_gain):
    #         channel_selection = (df_jitter.chB_gain == gain)  # (df_jitter.dt_std < 100)
    #         plt.scatter(df_jitter.loc[channel_selection, 'chB'], df_jitter.loc[channel_selection, 'dt_std']/np.sqrt(2),
    #                     label=method+ ': jitter mean = %d ps RMS worst = %d ps RMS' % (
    #                     df_jitter['dt_std'].mean()/np.sqrt(2), df_jitter['dt_std'].max()/np.sqrt(2)), marker='o')
    #
    # plt.legend()
    # plt.title("Time difference chA %d vs chB ? " % 43)
    # plt.ylabel("Jitter as std [ps]")
    # plt.xlabel('ChB')
    # plt.grid()
    # plt.tight_layout()
    # plt.savefig("../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/1_64_low_tdc/time_difference_jitter_comparison.png")
    # plt.show()
    # plt.close()

    search_folder = root_folder + "output/tdc_scan/internal/custom_step/dig_ck_80_MHz/16_5ps_step_PLL_method/raw/"
    # search_folder = root_folder + "output/tdc_scan/internal/custom_step/dig_ck_80_MHz/15_5ps_step_best_method/raw/"
    # search_folder = root_folder + "output/tdc_scan/internal/custom_step/dig_ck_80_MHz/14_10ps_step_best_method/raw/"
    # search_folder = root_folder + "output/tdc_scan/internal/custom_step/dig_ck_80_MHz/12/raw/"

    analyse_custom_step(root_folder, search_folder)
    # analyse_delaybox_step_internal_tdc("../output/tdc_scan/internal/delaybox_step/dig_ck_80_MHz/B1/0/raw/")

