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


def plot_Na22_spectrum(search_folder):

    df, output_folder, save_filepath, config, folder_index_str, board, files = analyse_init_internal_adc(search_folder)
    injected_channel_list = config['enable_TL_ASIC_ch']
    channel_gain_list = ['low'] #config['tdc_injected']

    for channel in injected_channel_list:
        for gi, gain in enumerate(channel_gain_list):

            # df=df[(df.time!=0x558a) & (df.time!=0x558b)]
            # df = decode_CPT_data(df)
            #
            # channel_suffix = '_%s_ch%d' % (gain, channel%16)
            # cluster_selection = df.cluster==(channel//16)
            # fig, ax = plt.subplots()
            # # plt.plot(df.loc[cluster_selection, 'index'], df.loc[cluster_selection, 'CPT'+channel_suffix])
            # ax2 = ax.twinx()
            # ax2.plot(df.loc[cluster_selection, 'index'], df.loc[cluster_selection, 'time'], label='time')
            # # ax2.plot(df.loc[cluster_selection, 'index'], df.loc[cluster_selection, 'cpt'+channel_suffix], label='cpt')
            # plt.legend()
            # plt.show()
            # plt.close()
            #
            # plt.figure(1)
            # x = df.loc[cluster_selection, 'CPT'+channel_suffix].diff()
            # x=x[(x<7e6) & (x>1e6)]
            # hist, bins, _ = plt.hist(x, bins=100)
            # plt.show()
            #
            # logbins = np.logspace(np.log10(bins[0]), np.log10(bins[-1]), len(bins))
            # plt.hist(x, bins=logbins)
            # plt.xscale('log')


            plt.figure(figsize=(10, 8))
            plt.title("Na22 spectrum for ch%d %s"%(channel, gain))
            channel = channel%16
            serie = df.loc[:, 'adc_%s_ch%d' % (gain, channel)]

            counts, bins = np.histogram(serie, bins=150) #np.arange(0, 1024, 1)) #, density=True)
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

                r1, r2, FWHM = half_max_x(xfit, yfit)


                plt.plot(xfit, yfit, linestyle='--', color='red', label='Fit mean %.2f ADC  sigma = %.2f ADC  Resolution %.1f %% FWHM' % (meanHisto, sigmaHisto, FWHM/meanHisto*100))

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

def analyse_init_merge_specific(search_folder):
    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("(?<=raw/)[0-9]+", folder)

    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        return

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    files = glob.glob(search_folder + '/B*.csv')

    board = config['board'][0]
    df_filename = '%s_B%d' % (folder_index_str, board)
    # df_filename = os.path.basename(files[0])
    # df_filename = df_filename.split("__")[0]  # no mention of cluster or delay

    output_folder = folder + '/../../' + folder_index_str + '/coincidence/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    save_filepath = output_folder + df_filename
    df0_filepath = save_filepath + "_0.feather"
    df1_filepath = save_filepath + "_1.feather"
    stats_filepath = save_filepath + "_stats.csv"

    # Step 0 : assemble all files
    if os.path.exists(stats_filepath):
        pass
        # stats = pd.read_csv(stats_filepath)
        # if os.path.exists(df0_filepath):
        #     df = pd.read_feather(df0_filepath)
        # else:
        #     print("Missing dataframe.")
        #     exit(0)
        #
        # stats['not_received_frames'] = 0 #stats.asked_event_count - stats.raw_event_count
        # status_columns = [col for col in stats.columns if 'status' in col]
        # category_names_stats = ['exploitable_event'] + status_columns + ['all_tdc_null_count', 'frames not received']
        # columns = ['exploitable_event_count'] + status_columns + ['all_tdc_null_count', 'not_received_frames']
        # df_mean = pd.pivot_table(stats, values=columns, index='readout_mode', aggfunc='sum', sort=False)
        # results = df_mean.T.to_dict('list')
        #
        # plot_data_quality(category_names_stats, results, 'data_quality', output_folder)

    else:

        stats_dict = {'raw_event_count': [],
                      'asked_event_count': [],
                      'readout_mode': [],
                      'exploitable_event_count': [],
                      'file': [],
                      'cluster': [],
                      'injected_channels':[]}

        print("Combining all results...")
        # with alive_bar(len(files), force_tty=True) as bar:  # your expected total
        if 1:
            for fi, file in enumerate(files):

                df_tmp = build_dataframe_from_file(file)
                df_tmp = remove_status_erroneous_frames(len(df), df_tmp, stats_dict, fi)

                cluster = re.findall("(?<=cluster_)[0-9]+", file)
                cluster = int(cluster[0]) if cluster else 0

                readout_mode = config['readout_mode'][0]
                # expected_frame_count = config["total_nb_events_expected_cluster%d"%cluster]
                expected_frame_count = config['total_nb_events_expected']
                # df_tmp['modeRO'] = readout_mode
                # df_tmp['cluster'] = cluster

                injected_channel_for_this_cluster, df_tmp = drop_not_injected_channels_within_cluster(df_tmp, config, cluster)
                df_tmp = decode_CPT_data(df_tmp)

                stats_dict['asked_event_count'].append(expected_frame_count)
                stats_dict['readout_mode'].append(readout_mode)
                stats_dict['exploitable_event_count'].append(len(df_tmp))
                stats_dict['file'].append(os.path.basename(file))
                stats_dict['cluster'].append(cluster)
                stats_dict['injected_channels'].append(injected_channel_for_this_cluster)

                df_tmp = rename_channels_to_64base(df_tmp, cluster)

                df_tmp.to_feather(save_filepath + "_cluster_%d.feather"%cluster)

        stats = pd.DataFrame(stats_dict)
        stats.to_csv(stats_filepath, index=False)

    return output_folder, save_filepath, config, folder_index_str, board, files



def merge_specific(search_folder):
    # too complicated, not to be used
    # handles fpga overflows to match events between 2 different clusters
    # better to use new fw with larger overflow counter size (32 bits instead of 16 bits)

    output_folder, save_filepath, config, folder_index_str, board, files = analyse_init_merge_specific(search_folder)

    injected_channel_list = np.array(config['enable_TL_ASIC_ch'])
    channel_gain = 'low'

    chA = injected_channel_list[0]
    clusterA = chA//16
    dfA = pd.read_feather(save_filepath + "_cluster_%d.feather" % clusterA)
    channel_suffixA = '_%s_ch%d' % (channel_gain, chA)

    chB = injected_channel_list[1]
    clusterB = chB//16
    dfB = pd.read_feather(save_filepath + "_cluster_%d.feather" % clusterB)
    channel_suffixB = '_%s_ch%d' % (channel_gain, chB)

    dfA['time'] = np.right_shift(np.bitwise_and(dfA['CPT' + channel_suffixA], 0xffff << 14), 14)
    dfA['time_1'] = dfA['time'].shift(1)
    dfB['time'] = np.right_shift(np.bitwise_and(dfB['CPT' + channel_suffixB], 0xffff << 14), 14)
    dfB['time_1'] = dfB['time'].shift(1)
    selection_A = ((dfA['CPT' + channel_suffixA].diff() < -1e7) & (dfA.time != 0x558a) & (dfA.time != 0x558b)
                   & (dfA.time_1 != 0x558a) & (dfA.time_1 != 0x558b))
    #-5e8
    selection_B = ((dfB['CPT' + channel_suffixB].diff() < -1e7) & (dfB.time != 0x558a) & (dfB.time != 0x558b)
                & (dfB.time_1 != 0x558a) & (dfB.time_1 != 0x558b))

    plt.subplots(2,1,sharex=True)
    plt.subplot(2,1, 1)
    plt.plot(dfA.loc[:, 'CPT' + channel_suffixA], label='A')

    print(len(dfA.loc[selection_A, :].index.values), len(dfB.loc[selection_B, :].index.values))
    for index in dfA.loc[selection_A, :].index.values:
        plt.axvline(index, color='red', linestyle='--')

    plt.subplot(2,1, 2)
    plt.plot(dfB.loc[:, 'CPT' + channel_suffixB], label='B')

    for index in dfB.loc[selection_B, :].index.values:
        plt.axvline(index, color='red', linestyle='--')

    plt.show()

    # df = df.merge(df_tmp, on='CPT', how='inner')
    pass


def plot_spectrum(df, config):

    for board in config['board']:
        if len(config['board']) == 1:
            board_suffix = ''
        else:
            board_suffix = '_B%d' % board

def compute_spectrum_for_multichannel(df, config):
    board = 2
    board_suffix = '_B%d'%board
    # not_injected_adc_col = ['adc_low_ch%d' % ch + board_suffix for ch in config['not_injected_ASIC_channels']]
    # df.drop(labels=not_injected_adc_col, axis="columns", inplace=True)
    config['really_injected_ASIC_channels'] = list(range(3, 64))
    injected_adc_col = ['adc_low_ch%d' % ch + board_suffix for ch in config['really_injected_ASIC_channels']]

    pedestal_mean = pd.read_csv(config['root_folder'] + "../config/TEMPOROC/B2_pedestal_mean.csv")['pedestal_mean'].values
    df[injected_adc_col] -= pedestal_mean

    new_cols = {}
    for col in injected_adc_col:
        new_cols[col] = df[col] * (df[col] >= 10)
    df.drop(labels=list(new_cols.keys()), axis="columns", inplace=True)
    df = pd.concat([df, pd.DataFrame(new_cols)], axis=1)

    energy_cut = 100
    energy_selection = (df[injected_adc_col] > energy_cut).any(axis=1)
    energy_selection_count = energy_selection.value_counts()[energy_selection.value_counts().index == True].values
    energy_selection_count = energy_selection_count[0] if energy_selection_count else 0
    new_field = {'frame_%%_with_at_least_1ch_above_%d_adc_above_pedestal' % energy_cut: round(
        energy_selection_count / len(df) * 100)}
    print(new_field)
    config.update(new_field)
    df = df[energy_selection]

    df['adc_low_all_ch_sum'] = df[injected_adc_col].sum(axis=1)

    xmin, xmax, mu, sigmaHisto = plot_adc_sum(df['adc_low_all_ch_sum'], '')

    df['photopeak_B%d' % board] = (df['adc_low_all_ch_sum'] > xmin) & (df['adc_low_all_ch_sum'] < xmax)
    photopeak_event_count = df['photopeak_B%d'%board].value_counts()[
        df['photopeak_B%d'%board].value_counts().index == True].values
    photopeak_event_count = photopeak_event_count[0] if photopeak_event_count else 0
    label = '#%d (%d %%)' % (photopeak_event_count, photopeak_event_count / len(df) * 100)

    plt.title("Energy spectrum for 22Na summing all channels \nPhotopeak = %s"%label)
    plt.tight_layout()
    # plt.savefig(config['output_folder'] + "../adc_low_all_ch_sum.png")


def compute_spectrum_for_single_channel(df, config, board, channel):
    half_span = 30
    ch_gain_suffix = '_low_ch%d_B%d'%(channel, board)
    bins = np.arange(df['adc' + ch_gain_suffix].min(), df['adc' + ch_gain_suffix].max() + 1, 5)
    counts, bins = np.histogram(df['adc' + ch_gain_suffix], bins=bins)
    energy_cut = (bins[:-1] > 200) & (bins[:-1] < 1000)
    photopeak_adc = bins[:-1][energy_cut][counts[energy_cut].argmax()]

    plt.figure(figsize=(10, 6))
    plt.yscale('log')

    try:
        p0 = [photopeak_adc, 80, counts[energy_cut].max()]
        fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)

        mu = fitParam[0]
        sigmaHisto = fitParam[1]
        ampHisto = fitParam[2]
        xmin = mu - 3 * sigmaHisto
        xmax = mu + 3 * sigmaHisto
        xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
        yfit = modelGauss(xfit, mu, sigmaHisto, ampHisto)

        r1, r2, FWHM = half_max_x(xfit, yfit)

        plt.plot(xfit, yfit, linestyle='-', color='red',
                 label=r"$\Delta E/E$ " + '= %.0f %% FWHM' % (FWHM / mu * 100))

        # xmin = mu - 0.5 * sigmaHisto
        # xmax = mu + 0.5 * sigmaHisto
    except:
        print("Error fit energy resolution")
        xmax = photopeak_adc + half_span
        xmin = photopeak_adc - half_span
        plt.axvline(xmin, color='red', linestyle='--')
        plt.axvline(xmax, color='red', linestyle='--')

    df['photopeak_B%d'%board] = (df['adc' + ch_gain_suffix] < xmax) & (df['adc' + ch_gain_suffix] > xmin)
    photopeak_event_count = df['photopeak_B%d'%board].value_counts()[
        df['photopeak_B%d'%board].value_counts().index == True].values
    photopeak_event_count = photopeak_event_count[0] if photopeak_event_count else 0
    label = '#%d (%d %%) in photopeak' % (photopeak_event_count, photopeak_event_count / len(df) * 100)

    plt.title(ch_gain_suffix)
    plt.stairs(counts, bins, fill=True, label=label)
    bin_selection = (bins > xmin) & (bins < xmax)
    plt.stairs(counts[bin_selection[:-1]], bins[np.roll(bin_selection, 1) | bin_selection], fill=True, label='selected', color='darkblue')
    plt.xlabel('Low gain shaper energy [adc]')
    plt.ylabel('Count')
    plt.grid()
    plt.legend()
    plt.savefig(config['output_folder'] + "energy_spectrum_B%d_ch%d"%(board, channel))
    # plt.show()

    plt.close()
    return photopeak_adc

def find_most_lighted_channel(df, board=2):

    adc_col_list = ['adc_%s_ch%d_B%d' % (gain, channel, board) for channel in range(3, 64) for gain in['low']]
    sum_per_channel = df[adc_col_list].sum(axis=0)
    channel_full_label = sum_per_channel[sum_per_channel == sum_per_channel.max()].index[0]
    channel = int(channel_full_label[10:12])
    return channel







def correct_late_msb_cpt(df, config, channelA, boardA, channelB, boardB, plot=True):

    ch_suffixA = '_low_ch%d_B%d' % (channelA, boardA)
    ch_suffixB = '_low_ch%d_B%d' % (channelB, boardB)
    selection = (df['photopeak_B%d' % boardA] & df['photopeak_B%d' % boardB]
                 & df['tdc_data_valid' + ch_suffixA] & df['tdc_data_valid' + ch_suffixB])

    # Compute selection to correct
    df['dt_CPT'] = df['CPT_B%d'%boardA] - df['CPT_B%d'%boardB]
    dt = df.loc[selection, 'dt_CPT']
    tempo_dig_ck = config['config_B%d' % boardA]['tempo_dig_ck']
    clock_period = 1e3/tempo_dig_ck  # ns

    if plot:
        plt.subplots(1, 2)

        for i, (ch_suffix, board) in enumerate(zip([ch_suffixA, ch_suffixB], [boardA, boardB])):

            plt.subplot(1, 2, i+1)
            param = 'toa_ns' + ch_suffix
            plt.scatter(df.loc[selection, 'CPT_B%d' % board][dt != 16], df.loc[selection, param][dt != 16],
                        label=' good')
            plt.scatter(df.loc[selection, 'CPT_B%d' % board][dt == 16], df.loc[selection, param][dt == 16],
                        label=' erronous')
            plt.legend()
            plt.xlabel("CPT_B%d" % board)
            plt.ylabel(param)
            plt.grid()

        # # Compute selection of event to correct WITHOUT prior knowledge of error : CAN NOT !!
        # main_lsb_cpt_in_error = df.loc[selection, 'cpt' + ch_suffix][dt == 16].value_counts().idxmax()
        # thres_high = main_lsb_cpt_in_error + 5 / 4 * clock_period
        # thres_low = main_lsb_cpt_in_error - 1 / 4 * clock_period
        # plt.axhline(thres_high, color='red', linestyle='--', label='main_lsb_cpt_in_error + 5 / 4 * clock_period')
        # plt.axhline(thres_low, color='red', linestyle='--', label='main_lsb_cpt_in_error - 1 / 4 * clock_period')

        plt.suptitle("Erroneous msb_cpt (missing 1 lsb for board B = %d)"%boardB)
        plt.savefig(config['output_folder'] + 'visualise_erronous_msb_cpt.png')
        plt.show()
        plt.close()

    for i, (ch_suffix, board) in enumerate(zip([ch_suffixA, ch_suffixB], [boardA, boardB])):
        if board==boardA:
            continue
        # Only B should be corrected because only B is late because dt==+16 and not dt==-16
        # lsb_cpt_to_correct_selection = ((df.loc[selection, 'cpt' + ch_suffix] >= 0)
        #                                 & (df.loc[selection, 'cpt' + ch_suffix] <= 2))
        lsb_cpt_to_correct_selection = (df.loc[selection, 'cpt' + ch_suffix] == 1)

        # Apply correction
        df.loc[selection, 'CPT_B%d' %board] += 16 * lsb_cpt_to_correct_selection
        df.loc[selection, 'toa_ns' + ch_suffix] += (16 * lsb_cpt_to_correct_selection * clock_period)

    # plt.figure()
    df['dt_CPT'] = df['CPT_B%d'%boardA] - df['CPT_B%d'%boardB]
    # dt = df.loc[selection, 'dt']
    dt = df.loc[selection, 'dt_CPT']
    pass
    # # dt = df.loc[selection, 'dt_cpt']
    # step = 1  # lsb
    # bins = np.arange(dt.min(), dt.max() + 1, step)  # lsb
    # counts, bins = np.histogram(dt, bins=bins)
    # plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True, label='dt' + ch_suffixA + ch_suffixB)
    # plt.grid()
    # plt.yscale('log')
    # plt.show()


    plt.figure()
    for i, (ch_suffix, board) in enumerate(zip([ch_suffixA, ch_suffixB], [boardA, boardB])):
        plt.subplot(1, 2, i + 1)
        param = 'cpt' + ch_suffix
        plt.scatter(df.loc[selection, 'CPT_B%d' % board][dt != 16], df.loc[selection, param][dt != 16],
                    label=' good')
        plt.scatter(df.loc[selection, 'CPT_B%d' % board][dt == 16], df.loc[selection, param][dt == 16],
                    label=' erronous')
        plt.legend()
        plt.xlabel("CPT_B%d" % board)
        plt.ylabel(param)
        plt.grid()
    plt.show()




def analyse_coincidence_Na22(root_folder, search_folder):

    config = read_config(root_folder, search_folder)
    df = analyse_init(search_folder, config)

    if len(df)==0:
        print("No data")
        exit(0)

    df2_filepath = config['output_folder'] + "2.feather"

    boardA = 1
    channelA = 43
    boardB = 2
    # channelB = find_most_lighted_channel(df, board=2)
    channelB = 43

    # Step 2: select photopeak
    if os.path.exists(df2_filepath):
        df = pd.read_feather(df2_filepath)
    else:
        compute_spectrum_for_single_channel(df, config, 1, channelA)
        compute_spectrum_for_single_channel(df, config,2, channelB)
        # compute_spectrum_for_multichannel(df, config)

        # injected_adc_col = ['adc_low_ch%d_B%d' % (ch, board) for ch in config['really_injected_ASIC_channels'] for board in config['board']]
        # injected_adc_col = ['adc_low_ch%d_B%d' % (ch, board) for col in df.columns if  ]
        # df.drop(labels=, axis="columns", inplace=True)

        df.to_feather(df2_filepath)


    plot_lsb_vs_time_for_one_ch(df, channelA, 'low', config, boardA)
    plot_lsb_vs_time_for_one_ch(df, channelB, 'low', config, boardB)

    df['photopeak'] = df['photopeak_B%d' % boardA] & df['photopeak_B%d' % boardB]

    stats_null_events(df, channelA, boardA, channelB, boardB)

    for time_conversion_method in ['lsb_fromCAL', 'lsb_fromCAL_moving_avg', 'DNL_TOA_fraction', 'DNL_TOA_calibrated_time']:
    # for time_conversion_method in ['lsb_fromCAL'] :
    # for time_conversion_method in ['lsb_fromCAL_moving_avg']:
    # for time_conversion_method in ['DNL_TOA_fraction']:
    # for time_conversion_method in ['DNL_TOA_calibrated_time']:
        for channel, board in zip([channelA, channelB], [boardA, boardB]):

            compute_ps_time_within_one_msb_cpt(df, config, channel, board, time_conversion_method)


        # correct_late_msb_cpt(df, config, channelA, boardA, channelB, boardB)

        ch_suffixA = '_low_ch%d_B%d' % (channelA, boardA)
        ch_suffixB = '_low_ch%d_B%d' % (channelB, boardB)
        df['dt'] = df['toa_ns' + ch_suffixA] - df['toa_ns' + ch_suffixB]
        # df['dt_cpt'] = df['cpt' + ch_suffixA] - df['cpt' + ch_suffixB]

        plot_CTR(df['photopeak'], config, channelA, boardA, channelB, boardB, time_conversion_method)



    # df['index_gap'] = abs(df.index_master - df.index_slave)
    # dt = df.loc[energy_selection, 'dt' + ch_gain_suffixA + ch_gain_suffixB]




    # df_stats = pd.read_csv(output_folder + "/stats.csv")

    # plot_spectrum_per_channel(df, config, '', '', folder_index_str)




        # chA = config['enable_TL_ASIC_ch'][0][0]
        # chB = config['enable_TL_ASIC_ch'][1][0]
        #
        #
        # total_events = df_stats.raw_event_count.min()
        # plt.suptitle("Energy spectrum for events in coincidence : %d (%d %%)"%(len(df), len(df)/total_events*100))
        # plt.tight_layout()
        # plt.savefig(output_folder+'energy_spectrum.png')
        # # plt.show()
        # plt.close()
        #
        # # plt.subplots(2,2)
        #
        # for giA, channel_gainA in enumerate(config['tdc_injected'][0]):
        #     for giB, channel_gainB in enumerate(config['tdc_injected'][1]):
        #         plt.figure(figsize=(13, 7))
        #
        #         ch_gain_suffixA = '_%s_ch%d_master' % (channel_gainA, chA)
        #         ch_gain_suffixB = '_%s_ch%d_slave' % (channel_gainB, chB)
        #
        #         for channel, gain, mode in zip([chB, chA], [channel_gainB, channel_gainA], ['slave', 'master']):
        #
        #             suffix = '_%s_ch%d_%s' % (gain, channel, mode)
        #             if time_conversion_method == 'lsb_fromCAL':
        #                 df['toa_ns' + suffix] = (df['cpt' + suffix] * 1e3/tempo_dig_ck) - (df['toa' + suffix] * df['lsb_fromCAL' + suffix].mean())
        #
        #             elif time_conversion_method == 'DNL':
        #                 calib_table_filepath = '../output/tdc_scan/internal/code_density/dig_ck_80_MHz/B2/1_64_low_tdc/toa_non_linearity_calib_table.csv'
        #
        #                 if calib_table_filepath is not None:
        #                     calib_table = pd.read_csv(calib_table_filepath)
        #
        #                     # MAP no matter lsb obtained from cal
        #                     calib_table = calib_table.loc[(calib_table.channel == channel) & (calib_table.gain == gain), ['toa', 'calibrated_time']].rename(columns={'toa':'toa'+suffix, 'calibrated_time':'calibrated_time'+suffix})
        #                     df = df.merge(calib_table, on='toa'+suffix, how='left')
        #                     unmatched_calib_toa_count = df.loc[df['calibrated_time' + suffix].isna(), 'toa'+suffix].value_counts().sum()
        #                     print("unmatched_calib_toa_count", unmatched_calib_toa_count)
        #                     config['unmatched_calib_toa_count'+suffix] = unmatched_calib_toa_count
        #                     df = df.dropna(subset='calibrated_time'+suffix)
        #                     df['toa_ns' + suffix] = (df['cpt' + suffix] * 1e3/tempo_dig_ck[0]) - df['calibrated_time'+suffix]
        #                     pass
        #                 else:
        #                     print("Missing TDC TOA calibration table ", calib_table_filepath)
        #             else:
        #                 print("time_conversion_method unknown ", time_conversion_method)

                #     plt.subplot(2, 2, 1)
                #     counts, bins = np.histogram(df['lsb_fromCAL' + suffix], bins=150)
                #     plt.stairs(counts, bins, fill=True)
                #     plt.title('lsb_fromCAL')
                #     plt.subplot(2, 2, 2)
                #     counts, bins = np.histogram(df['cpt' + suffix], bins=150)
                #     plt.stairs(counts, bins, fill=True)
                #     plt.title('cpt')
                #     plt.subplot(2, 2, 3)
                #     counts, bins = np.histogram(df['toa' + suffix], bins=150)
                #     plt.stairs(counts, bins, fill=True)
                #     plt.title('toa')
                #     plt.subplot(2, 2, 4)
                #     counts, bins = np.histogram(df['toa_ns' + suffix], bins=150)
                #     plt.stairs(counts, bins, fill=True)
                #     plt.title('toa_ns')
                #     plt.suptitle(suffix)
                #     plt.show()

                # tdc_selection = ((df['lsb_fromCAL' + ch_gain_suffixA] > 0.048) & (df['lsb_fromCAL' + ch_gain_suffixA] < 0.0485)
                #             & (df['lsb_fromCAL' + ch_gain_suffixB] > 0.0468) & (df['lsb_fromCAL' + ch_gain_suffixB] < 0.047))
                # mean_lsb_A = df['lsb_fromCAL' + ch_gain_suffixA].median()
                # mean_lsb_B= df['lsb_fromCAL' + ch_gain_suffixB].median()
                # half_span_ns = 0.005
                # tdc_selection = ((df['lsb_fromCAL' + ch_gain_suffixA] > (mean_lsb_A-half_span_ns)) & (df['lsb_fromCAL' + ch_gain_suffixA] < (mean_lsb_A+half_span_ns))
                #             & (df['lsb_fromCAL' + ch_gain_suffixB] > (mean_lsb_B-half_span_ns)) & (df['lsb_fromCAL' + ch_gain_suffixB] < (mean_lsb_B+half_span_ns)))

        #         df['dt'+ch_gain_suffixA+ch_gain_suffixB] = df['toa_ns' + ch_gain_suffixA] - df['toa_ns' + ch_gain_suffixB]
        #         # df['index_gap'] = abs(df.index_master - df.index_slave)
        #         dt = df.loc[energy_selection, 'dt'+ch_gain_suffixA+ch_gain_suffixB]
        #
        #         # FIRST STEP
        #         bins = np.arange(dt.min(), dt.max(), 1)  # large step 1 ns
        #         counts, bins = np.histogram(dt, bins=bins)
        #         plt.stairs(counts, bins, fill=True, label='dt' + ch_gain_suffixA + ch_gain_suffixB)
        #
        #         # SECOND STEP
        #         tdc_selection = (df['delta' + ch_gain_suffixA] != 0) & (
        #                     df['delta' + ch_gain_suffixB] != 0)  # remove null tdc events
        #         cpt_selection = df['cpt' + ch_gain_suffixB] < 14  # issues when fine counter is close to its maximum
        #         # ovf_selection = df['overflown_TOA'+ch_gain_suffixA] & df['overflown_TOA'+ch_gain_suffixB]
        #         dt_median = dt.median()
        #         print(dt_median)
        #
        #         time_selection = (df['dt'+ch_gain_suffixA+ch_gain_suffixB]>dt_median-2) & (df['dt'+ch_gain_suffixA+ch_gain_suffixB]<dt_median+2)
        #         selection = energy_selection & time_selection
        #         if len(df[selection]) > 10:
        #             dt = df.loc[selection, 'dt' + ch_gain_suffixA + ch_gain_suffixB]
        #
        #             bins = np.arange(dt.min(), dt.max(), 0.04)  # ~ tdc bin size
        #             # bins = np.arange(dt.min(), dt.max(), 1) # ~ tdc bin size
        #             counts, bins = np.histogram(dt, bins=bins)
        #
        #             plt.figure(figsize=(13, 7))
        #             plt.hist(bins[:-1], bins, weights=counts, align='left', color="darkblue", fill=True,
        #                      label='Energy selection : #%d (%d %%)' % (len(dt), len(dt) / len(df) * 100))
        #
        #
        #
        #             plt.title('dt' + ch_gain_suffixA + ch_gain_suffixB)
        #             plt.xlabel('Time difference [ns]')
        #             plt.grid()
        #             plt.legend()
        #
        #             plt.tight_layout()
        #             # mng = plt.get_current_fig_manager()
        #             # mng.full_screen_toggle()
        #             plt.savefig(output_folder + 'CTR.png')
        #
        #             # try:
        #             #     p0 = [bins[np.argmax(counts)], dt.std(), max(counts)]
        #             #     fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)
        #             #     meanHisto = fitParam[0]
        #             #     sigmaHisto = fitParam[1]
        #             #     ampHisto = fitParam[2]
        #             #     xmin = meanHisto - 3 * sigmaHisto
        #             #     xmax = meanHisto + 3 * sigmaHisto
        #             #     xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
        #             #     yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)
        #             #     plt.plot(xfit, yfit,
        #             #              label='fit CTR = %d ps RMS = %d ps FWHM' % (sigmaHisto * 1e3, sigmaHisto * 1e3 * 2.35))
        #
        #         else:
        #             pass
        #
        #
        # save_config_file_copy(config)
        # plt.show()
        #
        # plt.subplots(2,2)



        # plt.plot(df['dt'])

        # for injected_ch in config['enable_TL_ASIC_ch']:
        #     channel_gain = 'high'
        #     cluster = injected_ch // 16
        #     cluster_channel = injected_ch % 16
        #     ch_gain_suffix_at_cluster_level = '_%s_ch%d' % (channel_gain, cluster_channel)
        #     cluster_selection = (df.cluster == cluster)
        #
        #     plt.plot(df.loc[cluster_selection, 'index'], df.loc[cluster_selection, 'toa' + ch_gain_suffix_at_cluster_level], label="%d"%injected_ch)
        # plt.legend()

def stats_null_events(df, channelA, boardA, channelB, boardB):

    ch_suffixA = '_low_ch%d_B%d' % (channelA, boardA)
    ch_suffixB = '_low_ch%d_B%d' % (channelB, boardB)
    non_null_selection = df['tdc_data_valid' + ch_suffixA] & df['tdc_data_valid' + ch_suffixB]

    non_null_selection_count = non_null_selection.value_counts()[non_null_selection.value_counts().index == True].values
    non_null_selection_count = non_null_selection_count[0] if non_null_selection_count else 0
    print(
        "Non null %d  %d %%" % (non_null_selection_count, non_null_selection_count / len(df) * 100))

    energy_selection_count = df['photopeak'].value_counts()[df['photopeak'].value_counts().index == True].values
    energy_selection_count = energy_selection_count[0] if energy_selection_count else 0
    print("Photopeak both %d  %d %%" % (
        energy_selection_count, energy_selection_count / len(df) * 100))  # B1 %d %%    B2 %d %%

    non_null_photopeak_selection = df['photopeak'] & non_null_selection
    non_null_photopeak_selection_count = non_null_photopeak_selection.value_counts()[non_null_photopeak_selection.value_counts().index == True].values
    non_null_photopeak_selection_count = non_null_photopeak_selection_count[0] if non_null_photopeak_selection_count else 0
    print("\t↳ Non null %d  %d %%" % (non_null_photopeak_selection_count, non_null_photopeak_selection_count / energy_selection_count * 100))


if __name__ == '__main__':
    # plot_hex_sipm()
    # search_folder = "../output/coincidence/Na22_spectra/raw/72/"
    # search_folder = "../output/coincidence/Na22_spectra/raw/86/"
    # root_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    root_folder = "//192.168.2.230/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    # search_folder = root_folder + "coincidence/22Na_digital/17/raw/"
    # search_folder = root_folder + "Hamamatsu/coincidence/3x3x5_vs_segm_alu_LYSO/1/raw/"
    # search_folder = root_folder + "Hamamatsu/coincidence/3x3x5_vs_segm_alu_LYSO/0/raw/"
    search_folder = root_folder + "Hamamatsu/coincidence/3x3x5_vs_3x3x5_LYSO/81/raw/"
    # search_folder = root_folder + "Hamamatsu/coincidence/3x3x5_vs_segm_alu_LYSO/4/raw/"

    # search_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/coincidence/Na22_spectra/raw/46/"
    analyse_coincidence_Na22(root_folder, search_folder)
    # merge_specific(search_folder)
    # plot_Na22_spectrum(search_folder)
    # root_folder = "../output/coincidence/Na22_spectra/raw/2/"
    # fast_compute_coincidence_events([root_folder+"B1_VDDD_1.34V_cluster_1.csv", root_folder+"B1_VDDD_1.34V_cluster_2.csv"], [25,34])
