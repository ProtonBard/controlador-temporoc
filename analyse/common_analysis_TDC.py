import glob
import itertools
import os
import re
import time

import yaml
from alive_progress import alive_bar
from colorama import Fore, Back, Style
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning

import src.temporoc3

import scipy.optimize as opt
import pandas as pd

from analyse.common_data_decoding import get_toa_cal_from_tdc
from src.utils import *
import matplotlib
matplotlib.use('Qt5Agg')
# matplotlib.use('QtAgg')
# matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import matplotlib.rcsetup as rcsetup

font = {'size'   : 10}
matplotlib.rc('font', **font)

def modelFitLinear(x, a, b):
    return a*x+b

def reverse_mask(x):
    x = ((x & 0x55555555) << 1) | ((x & 0xAAAAAAAA) >> 1)
    x = ((x & 0x33333333) << 2) | ((x & 0xCCCCCCCC) >> 2)
    x = ((x & 0x0F0F0F0F) << 4) | ((x & 0xF0F0F0F0) >> 4)
    x = ((x & 0x00FF00FF) << 8) | ((x & 0xFF00FF00) >> 8)
    x = ((x & 0x0000FFFF) << 16) | ((x & 0xFFFF0000) >> 16)
    return x

def analyse_linearity_quick_folder(search_path):
    filepath_list = glob.glob(search_path)

    for filepath in filepath_list:
        analyse_linearity_quick_file(filepath)


    # hitFreq = int(config['hit_freq'][0])
    # hitPeriod_in_320MHz_ck_cycles = int(1 / hitFreq / 3.125e-9)




def drop_erroneous_events(df):

    # mask to be applied due to FPGA TDC data sampling issue
    df['diff'] = df.CPT.diff()
    # plt.hist(df.CPT.diff(), bins='auto')
    # plt.show()

    mask = (df['diff'] < (df['diff'].median()-2)) | (df['diff'] > (df['diff'].median()+2))
    selection = ~(mask & np.roll(mask, -1)) # take only the first value of each group of 2 consecutive true values
    events_dropped = selection.value_counts()[selection.value_counts().index==False].values
    if events_dropped.size > 0:
        events_dropped = events_dropped[0]
        label_events_dropped = "%d (or %.2f %%)" %(events_dropped, (events_dropped/len(df)*100))
    else:
        label_events_dropped = "0"
    print(label_events_dropped+" of events dropped because of FPGA sampling failure")
    return label_events_dropped, selection    # return events to keep



def analyse_linearity_quick_file(filepath):

    print(os.path.basename(filepath))
    if not os.path.exists(filepath):
        print("File does not exists")
        exit(0)

    folder = os.path.dirname(filepath)+'/'+os.path.basename(filepath)[:1]+'/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    fig, axs = plt.subplots(1, 1, figsize=(10, 8))

    if 'standalone_tdc' in filepath:
        df = pd.read_csv(filepath)
        # df.CPT -= df.CPT.min()

        df['toa'] = df.TOAfine + 31 * df.TOAcoarse
        df['cal'] = df.CALfine + 31 * df.CALcoarse
        df['delta'] = df.cal - df.toa

        label_events_dropped, selection = drop_erroneous_events(df)
        axs.scatter(df.loc[selection, 'iter'], df.loc[selection, 'toa'], marker='x', label='raw TOA')
        axs.scatter(df.loc[~selection, 'iter'], df.loc[~selection, 'toa'], marker='x',
                    label='excluded data: ' + label_events_dropped)

        if 'delaybox_step' in filepath:
            expected_step = 10e-12
            df['real_time_ns'] = df.delay * 0.01  # 10 ps step

        elif 'custom_step' in filepath:
            # step given by frequency chosen
            expected_step, ck_cycles_in_between_2_hits = frequency_planner(8e6, 4e-12)

            df['real_time_ns'] = df.iter * expected_step * 1e9
            df['real_time_ns_B'] = df.CPT / ck_cycles_in_between_2_hits * expected_step * 1e9
    else:
        print("Not the right analysis")
        exit(0)


    df['lsb_fromCAL'] = 2 * 3125 / df.delta
    # df = df.sort_values('real_time_ns_A')
    df = df.sort_values('iter')


    # basic

    filename = os.path.basename(filepath)
    axs.annotate(filename, xy=(5, 7), xycoords='axes pixels')  # 'axes pixels


    # axs.scatter(df.real_time_ns_A, df.toa, marker='x', label='raw TOA assuming 1 hit every 40 ck cycles')
    # axs.scatter(df.real_time_ns_B, df.toa, marker='x', label='raw TOA taking into account super-coarse counter fluctuations')

    # axs.scatter(df.iter, df.CPT.diff(), label='raw cpt diff')

    # axs.scatter(df.real_time_ns, df.lsb_fromCAL, marker='x', label='raw CAL')

    # axs.scatter(df.real_time_ns, df.TOAfine, marker='x', label='raw TOA fine')
    # axs.scatter(df.real_time_ns, df.TOAcoarse, marker='x', label='raw TOA coarse')
    # axs.scatter(df.real_time_ns, df.CALcoarse, marker='x', label='raw CAL coarse')
    # axs.scatter(df.real_time_ns, df.CALfine, marker='x', label='raw CAL fine')
    # axs.scatter(df.real_time_ns, df.delta, marker='x', label='raw delta')

    axs.set_xlabel("Acquisition n°")
    axs.set_ylabel("TOA [lsb]")
    axs.set_title("TDC linearity with a step of %.2f ps" % (expected_step*1e12))
    axs.grid()
    axs.legend()

    plt.tight_layout()
    mng = plt.get_current_fig_manager()
    mng.full_screen_toggle()

    fig.savefig(folder + "/raw_data.png")
    # plt.show()
    plt.close()

    hitFreq = int(re.findall("(?<=hit_)[0-9]+", filepath)[0])

    plt.figure(0, figsize=(10, 8))
    hitPeriod_in_320MHz_ck_cycles = 320e6/hitFreq
    df['expected_CPT'] = df.iter*hitPeriod_in_320MHz_ck_cycles

    # plt.plot(df.loc[df.delay==0, 'iter'], df.loc[df.delay==0, 'expected_CPT']+df.loc[df.delay==0, 'CPT'].iloc[0], label='expected')
    # plt.plot(df.loc[df.delay==0, 'iter'], df.loc[df.delay==0, 'CPT'], label='measured')
    # df.loc[:, 'CPT_match'] = (df.loc[:, 'expected_CPT'] + df.loc[:, 'CPT'].iloc[0]) == df.loc[:, 'CPT']
    for delay in np.unique(df.delay):
        # df.loc[df.delay == delay, 'expected_CPT'] += df.loc[df.delay == delay, 'CPT'].iloc[0]
        clock_phases = (df.loc[df.delay == delay, 'CPT'] % hitPeriod_in_320MHz_ck_cycles).value_counts()
        if clock_phases.size > 0:
            dominant_clock_phase = int(clock_phases[clock_phases == np.max(clock_phases)].index[0])
            clock_phase_above_modulo = int((df.loc[df.delay == delay, 'CPT'] // hitPeriod_in_320MHz_ck_cycles).min())
            clock_phase_above_modulo = clock_phase_above_modulo * hitPeriod_in_320MHz_ck_cycles
            df.loc[df.delay == delay, 'expected_CPT'] += dominant_clock_phase + clock_phase_above_modulo

    df.loc[:, 'expected_CPT'] = df.loc[:, 'expected_CPT']
    df.loc[:, 'CPT_match'] = df.expected_CPT == df.CPT


    CPT_errors_per_delay = df[~df.CPT_match].groupby('delay')['delay'].count().sort_values()
    problematic_delay_list = CPT_errors_per_delay.index
    hits_per_delay = df.delay.value_counts()

    # cpt error versus iter for each delay
    # for delay in problematic_delay_list:
    #     plt.scatter(df.loc[df.delay==delay, 'iter'], df.loc[df.delay==delay, 'expected_CPT']-df.loc[df.delay==delay, 'CPT'], label='%d delay, %d (%d %%) in error'%(delay, CPT_errors_per_delay[delay], CPT_errors_per_delay[delay]/hits_per_delay[delay]*100))
    # plt.grid()
    # plt.legend()
    # plt.tight_layout()
    # plt.title('Super-coarse counter expected - measured difference')
    # plt.savefig(folder+"unmatched_super_coarse_counter.png")
    # plt.close()

    # cpt error histo for each delay
    yvar = []
    labels= []
    for delay in problematic_delay_list:
        labels.append('%d delay, %d (%d %%) in error'%(delay, CPT_errors_per_delay[delay], CPT_errors_per_delay[delay]/hits_per_delay[delay]*100))
        yvar.append(df.loc[~df.CPT_match & (df.delay==delay), 'expected_CPT'] - df.loc[~df.CPT_match & (df.delay==delay), 'CPT'])
    plt.hist(yvar, label= labels, stacked=True)
    #if not stacked
    # plt.hist(df.loc[~df.CPT_match, 'expected_CPT']-df.loc[~df.CPT_match, 'CPT'], align='left')
    plt.title('Super-coarse counter expected - measured difference per delay')
    plt.grid()
    plt.tight_layout()
    plt.annotate("%d (%d %%) errors"%(df.CPT_match.value_counts()[False], df.CPT_match.value_counts()[False]/len(df)*100), xy = (0.1, 0.9), xycoords = 'figure fraction')
    plt.annotate(filename, xy = (5, 7), xycoords = 'figure pixels')
    plt.savefig(folder+"histo_unmatched_super_coarse_counter.png")
    # plt.show()
    plt.close()

    pass
    # jitter
    suffix=''
    df['full_toa'] = df.toa + df.CPT


    col = ['TOAcoarse' + suffix, 'TOAfine' + suffix,  'toa' + suffix, 'full_toa', 'CALcoarse' + suffix, 'CALfine' + suffix, 'cal' + suffix]
    df_jitter = pd.pivot_table(df, values=col, index=['real_time_ns'], aggfunc='std')

    plt.figure(1, figsize=(10, 8))
    for i, field in enumerate(col):
        plt.subplot(2, 4, i+1)
        plt.scatter(df_jitter.index, df_jitter.loc[:, field])
        plt.title(field)
        plt.ylabel('Jitter')
        if i>3:
            plt.xlabel('Real time [ns]')
        plt.grid()
    plt.suptitle('Jitter for standalone TDC ')
    plt.tight_layout()
    plt.savefig(folder+'jitter.png')
    # plt.show()
    plt.close()


    # advanced
    df = df[selection]
    df = select_monotonous_data(df, expected_step)


    ax = axs.plot(df.iter, df.toa, color='red', marker='x', label='monotonous ?')
    fig.savefig(folder + "/raw_data_selection.png")

    # zoom on FPGA error
    ax.pop(0).remove() # remove monotonous selection

    if '/2_' in filepath:
        axs.set_xlim([740, 790])
        axs.set_ylim([0, 120])
        axs.axvline([753], color='red', linestyle='--')
        axs.axvline([756], color='red', linestyle='--')
        axs.axvline([782], color='red', linestyle='--')
        fig.savefig(folder + "/raw_data_FPGA_sampling_error.png")

    plt.close()

    plot_all_points(df, len(df), hitFreq, folder, filename, 64)

    # plot_average_per_delay(df, len(df), hitFreq, folder, 64, saveDF=True)

    plot_non_linearities(df, folder, filename, 64)


def make_caracteristic_linear(df, config, output_folder):
    new_series_set = {}
    injected_channel_list = config['enable_TL_ASIC_ch']
    df = df.sort_values(by='delay', ascending=False)

    calib_stats_df = pd.read_csv(output_folder + 'calib_stats.csv')

    with alive_bar(len(injected_channel_list)*2, force_tty=True) as bar:
        for channel in injected_channel_list:
            for channel_gain in ['low', 'high']:
                bar()
                cluster_channel = channel%16
                cluster = channel//16
                cluster_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)
                cluster_selection = df.cluster == cluster

                average_lsb_from_cal = 0
                one_tdc_clock_period_in_tdc_lsb = 1 / tempo_dig_ck

                derivative = np.diff(df.loc[cluster_selection, 'toa'+cluster_suffix])
                indexes = np.where(derivative == derivative.max())
                new_series_set['toa' + cluster_suffix] = df.loc[:, 'toa'+cluster_suffix]
                for i, index in enumerate(indexes):
                    new_series_set['toa'+cluster_suffix] += [0]*()

    df.drop(labels=list(new_series_set.keys()), axis="columns", inplace=True)
    df = pd.concat([df, pd.DataFrame(new_series_set)], axis=1)

    return df

def select_monotonous_data(df, step):

    # delay selection to have monotonous caracteristic
    # SOLUTION A
    indexesOfMin = np.where(df.toa == df.toa.min())[0]
    start = indexesOfMin[0]
    indexesOfMin = indexesOfMin[indexesOfMin > (start + 3125 / step/1e12)]  # length of the tdc caracteristic
    if len(indexesOfMin) == 0:
        print("Could not find the end of the TDC caracteristic.")
    stop = indexesOfMin[0]

    return df.iloc[start + 6:stop - 5, :]

    # # SOLUTION B
    # middle_value = 110  # todo
    # middle_value = 80  # todo
    # polarity = -1 # decreasing
    # if polarity==-1:
    #     df = df.sort_values('real_time', ascending=False)
    # middle = df.index[df.toa == middle_value][0]  # middle point toa supposed to range between 80 and 140
    # saturation_value = np.max(df.toa)
    # start = df[:middle].loc[(df[:middle].toa == saturation_value).rolling(2, center=True).sum() == 2].index[-1]
    # df = df.drop(df[:start].index).reset_index()
    # saturation_value = np.max(df.toa)
    # stop = df.loc[(df.toa == saturation_value).rolling(2, center=True).sum() == 2].index[0]
    # df.drop(df[stop:].index, inplace=True)
    # return df


def select_monotonous_data_internal_TDC(df, config):

    # SOLUTION B
    new_series_set = {}
    for board in config['board']:
        df = df.sort_values('real_time_ns', ascending=False)  # make decreasing carac increasing

        safety_margin_max = 4
        safety_margin_min = 4
        if 1:
            for channel in config['config_B%d'%board]['enable_TL_ASIC_ch'][0]:
                for channel_gain in config['config_B%d'%board]['tdc_injected'][0]:
                    suffix = '_%s_ch%d_B%d' % (channel_gain, channel, board)
                    # selection = df['tdc_data_valid'+suffix]

                    derivative = np.diff(df['toa' + suffix])
                    indexes = np.where(derivative == derivative.max())
                    separative_index = [df['real_time_ns'].min()-safety_margin_min]  # first index
                    last_index = None
                    for index in indexes[0]:
                        if last_index:
                            if abs(df['real_time_ns'].iloc[index]-df['real_time_ns'].iloc[last_index])<10:
                                # part of the characteristic already processed
                                last_index = index
                                continue
                        last_index = index
                        separative_index.append(df['real_time_ns'].iloc[index])
                        # print(index, df.delay.iloc[index])
                    separative_index.append(df['real_time_ns'].max()+safety_margin_max) # last index
                    new_series_set['monotonic'+suffix] = np.array([0]*len(df))
                    for i in range(len(separative_index)-1):
                        min_delay = separative_index[i]+safety_margin_min
                        max_delay = separative_index[i+1]-safety_margin_max
                        monotonic_selection = (df['real_time_ns'] > min_delay) & (df['real_time_ns'] <= max_delay)
                        # print(min_delay, max_delay)
                        new_series_set['monotonic'+suffix] += monotonic_selection.astype(int)*(i+1)
                    pass

        # Add empty columns
        # not_injected_channel_set = set(injected_channel_list) ^ set(range(16)) # not 64 otherwise overwrite data
        # for channel in not_injected_channel_set:
        #     for channel_gain in ['low', 'high']:
        #         cluster_channel = channel % 16
        #         cluster_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)
        #         new_series_set['monotonic' + cluster_suffix] = []

    df = pd.concat([df, pd.DataFrame(new_series_set)], axis=1)

    return df

def plot_all_points(subset, N, hitFreq, folder, filename, channel):

    plt.figure(1, figsize=(10, 8))
    plt.suptitle("All raw data")
    ax = plt.subplot(131)
    plt.annotate(filename, xy=(5, 7), xycoords='axes pixels')  # 'axes pixels

    # RAW
    par = np.polyfit(subset.real_time_ns, subset.toa, 1).tolist()
    lsb_eff = abs(1 / par[0] * 1e3)
    plt.scatter(subset.real_time_ns, subset.toa, marker='x',
             label='raw TOA N = %d  hitFreq = %d MHz \neffective lsb = %.2f ps \noffset = %.2f lsbUnit' % (
             N, hitFreq, lsb_eff, par[1]))

    # TIME-CONVERTED
    plt.subplot(132, sharex=ax)
    plt.subplot(133, sharex=ax)

    # method A: lsb extracted from the full caracteristic & knowledge of the time step
    subset['toa_ns_A'] = subset.toa * lsb_eff / 1e3

    # method B: lsb extracted from the full caracteristic & calibration lsb
    avg_cal_lsb = np.mean(subset.lsb_fromCAL)
    subset['toa_ns_B'] = subset.toa * avg_cal_lsb / 1e3

    # method C: lsb extracted from the full caracteristic & calibration lsb
    subset['toa_ns_C'] = subset.toa * subset.lsb_fromCAL / 1e3

    labels = ['using offline lsb (from fit) = %.2f ps'%lsb_eff, 'using inline multi-shot calib lsb \n(all data) = %.2f ps'%avg_cal_lsb, 'using inline single-shot calib \nlsb (fluctuating)']
    markers= ['.', 'X', 'v']
    for i, method in enumerate(['A', 'B', 'C']):
        plt.subplot(132)

        par = np.polyfit(subset.real_time_ns, subset['toa_ns_' + method], 1).tolist()

        yfit = par[0] * subset.real_time_ns + par[1]
        ax_tmp = plt.scatter(subset.real_time_ns, subset['toa_ns_' + method], marker='x',
                          label="gain = %.2f  offset = %.3f ns " % (par[0], par[1]) + '\n' + labels[i])
        # plt.plot(subset.real_time_ns, yfit, linestyle='--', color='tab:red') # ax_tmp.get_facecolors()

        plt.subplot(133)
        residue = (subset['toa_ns_' + method] - yfit) * 1e3
        plt.scatter(subset.real_time_ns, residue, s=2, label="std = %.1f ps" % np.std(residue), marker=markers[i])


    plt.figure(1)
    plt.subplot(131)
    plt.xlabel('Real time [ns]')
    plt.ylabel('Raw TOA [lsb]')
    plt.legend()
    plt.grid()

    plt.subplot(132)
    plt.xlabel('Real time [ns]')
    plt.ylabel('Converted time [ns]')
    plt.legend()
    plt.grid()

    plt.subplot(133)
    plt.xlabel('Real time [ns]')
    plt.ylabel('Residual time [ps] = converted time - fit')
    plt.legend()
    plt.grid()

    mng = plt.get_current_fig_manager()
    mng.full_screen_toggle()

    if not os.path.exists(folder):
        os.makedirs(folder)

    plt.tight_layout()
    plt.savefig(folder + "/ch%d.png"%channel)

    if '/2/' in folder:
        plt.xlim([1.5, 2])
        plt.subplot(131)
        plt.ylim([70, 90])
        plt.subplot(132)
        plt.ylim([3, 3.8])
        plt.subplot(133)
        plt.ylim([-100, 100])

        plt.savefig(folder + "/ch%d_zoom.png"%channel)
    # plt.subplot_tool()
    plt.show()


def plot_average_per_delay(subset, N, hitFreq, folder, channel, saveDF=True):
    # looking at mean over the N samples for a given delay

    df_pivot_mean = pd.pivot_table(subset, values=['toa', 'cal', 'lsb_fromCAL'], index='real_time_ns',
                                   aggfunc="mean").reset_index()

    df_pivot_std = pd.pivot_table(subset, values=['toa', 'cal', 'lsb_fromCAL'], index='real_time_ns',
                                  aggfunc="std").reset_index()

    # for simu todo
    df_pivot_std = df_pivot_mean.copy()
    df_pivot_std['toa'] = 0
    df_pivot_std['cal'] = 0
    df_pivot_std['lsb_fromCAL'] = 0

    df_pivot_mean = df_pivot_mean.sort_values('real_time_ns')

    # RAW data
    plt.figure(2, figsize=(10, 8))
    plt.suptitle("Averaging the calibrated LSB over the repeated measurements for each delay")

    par = np.polyfit(df_pivot_mean['real_time_ns'], df_pivot_mean.toa, 1).tolist()
    lsb_eff = abs(1 / par[0] * 1e3)

    ax = plt.subplot(131)
    plt.errorbar(df_pivot_mean['real_time_ns'], df_pivot_mean.toa, yerr=df_pivot_std.toa, marker='x',
                 label='raw TOA N = %d  hitFreq = %d MHz \neffective lsb = %.2f ps \noffset = %.2f lsbUnit' % (
                 N, hitFreq, lsb_eff, par[1]))

    # TIME-CONVERTED
    plt.subplot(132, sharex=ax)
    plt.subplot(133, sharex=ax)

    # method A: lsb extracted from the full caracteristic & knowledge of the time step
    df_pivot_mean['toa_ns_A'] = df_pivot_mean.toa * lsb_eff / 1e3
    df_pivot_std['toa_ns_A'] = df_pivot_std.toa * lsb_eff / 1e3
    # plt.errorbar(df_pivot_mean['real_time_ns'], df_pivot_mean.toa_ns_A, yerr=df_pivot_std.toa_ns_A,
    #                  marker='x', label='effective lsb = %.2f ps   offset = %.2f [lsb]' % (lsb_eff, par[1]))

    # method B: lsb extracted from the full caracteristic & calibration lsb
    df_pivot_mean['toa_ns_B'] = df_pivot_mean.toa * df_pivot_mean.lsb_fromCAL / 1e3
    df_pivot_std['toa_ns_B'] = df_pivot_std.toa * df_pivot_std.lsb_fromCAL / 1e3
    # plt.errorbar(df_pivot_mean['real_time_ns'], df_pivot_mean.toa_ns_B,
    #                  yerr=df_pivot_std.toa_ns_B,
    #                  marker='x', label='with average calib LSB for each delay injected')

    labels = ['offline lsb', 'inline multi-shot calib lsb (fluctuating)']  # between delay
    lsbs = [lsb_eff, 0]
    for i, method in enumerate(['A', 'B']):
        plt.subplot(132)

        par = np.polyfit(df_pivot_mean.real_time_ns, df_pivot_mean['toa_ns_' + method], 1).tolist()
        yfit = par[0] * df_pivot_mean.real_time_ns + par[1]

        ax_tmp = plt.plot(df_pivot_mean.real_time_ns, df_pivot_mean['toa_ns_' + method], marker='x',
                          label="gain = %.2f  offset = %.3f ns  using lsb=%.2f ps" % (par[0], par[1], lsbs[i]) + '\n' +
                                labels[i])
        plt.plot(df_pivot_mean.real_time_ns, yfit, linestyle='--', color=ax_tmp[0].get_color())

        plt.subplot(133)
        residue = (df_pivot_mean['toa_ns_' + method] - yfit) * 1e3
        plt.scatter(df_pivot_mean.real_time_ns, residue, s=3, label="std = %.1f ps" % np.std(residue))  # marker='x')

    save_folder = folder + '/average_per_delay/'
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    if saveDF:
        df_pivot_mean.to_csv(save_folder+'ch%d_pivot_mean.csv'%channel)
        df_pivot_std.to_csv(save_folder+'ch%d_pivot_std.csv'%channel)

    plt.figure(2)
    plt.subplot(131)
    plt.xlabel('Real time [ns]')
    plt.ylabel('Converted time [ns]')
    plt.legend()
    plt.grid()

    plt.subplot(132)
    plt.xlabel('Real time [ns]')
    plt.ylabel('Converted time [ns]')
    plt.legend()
    plt.grid()

    plt.subplot(133)
    plt.xlabel('Real time [ns]')
    plt.ylabel('Residual time [ns]')
    plt.legend()
    plt.grid()

    plt.tight_layout()
    mng = plt.get_current_fig_manager()
    mng.full_screen_toggle()

    plt.savefig(save_folder + 'ch%d.png'%channel)

def plot_non_linearities(subset, folder, filename, channel, xvar='toa', yvar=['real_time_ns', 'lsb_fromCAL'], calib_table_filepath=None, saveDF=False):
    # NON LINEARITIES on one method
    ###############################

    # yvar = 'toa_ns_B'
    df_pivot_mean = pd.pivot_table(subset, values=yvar, index=xvar, aggfunc="mean").reset_index()

    try:
        fitParam, cov = opt.curve_fit(modelFitLinear, df_pivot_mean[xvar], df_pivot_mean[yvar])
    except:
        fitParam = [0, 0]
    slope = fitParam[0]
    # delayOffset = fitParam[1]
    lsb = slope

    df_pivot_mean[yvar + '_fit'] = modelFitLinear(df_pivot_mean[xvar], *fitParam)
    inl = df_pivot_mean['inl'] = (df_pivot_mean[yvar + '_fit'] - df_pivot_mean[yvar]) / lsb

    plt.figure(3, figsize=(10, 8))
    plt.suptitle("NB: DNL can not be plotted without code-density test to quantify each bin width")
    ax = plt.subplot(121)
    plt.annotate(filename, xy=(5, 7), xycoords='axes pixels')  # 'axes pixels

    ax1 = plt.plot(df_pivot_mean[xvar], df_pivot_mean[yvar + '_fit'], '--', linewidth=1, color='red',
                   label='Fit raw data %.2f ps' % (lsb * 1e3))

    plt.scatter(df_pivot_mean[xvar], df_pivot_mean[yvar], s=2, label=yvar, color="tab:blue") # color=ax1[0].get_color()
    # plt.scatter(df_pivot_mean[xvar], df_pivot_mean['real_time_ns'], s=2, label='real time')

    plt.subplot(122, sharex=ax)
    plt.plot(df_pivot_mean[xvar], inl, marker='.',
             label='INL rms={:.2f} lsb/{:.0f} ps  {:.2f}/{:.2f} fit lsb = {:.0f}/{:.0f} ps - raw data'
             .format(np.std(inl), np.std(inl) * lsb * 1e3, np.nanmin(inl), np.nanmax(inl), np.nanmin(inl) * lsb * 1e3,
                     np.nanmax(inl) * lsb * 1e3))
    # # +'\n'+'Excluding |INL| > %d'%inl_cut)


    # Correct data using calibration table
    ###############################

    if calib_table_filepath is not None:
        calib_table = pd.read_csv(calib_table_filepath)

        # MAP no matter lsb obtained from cal
        calib_table = calib_table[['delta_calib', 'toa', 'calibrated_time']]
        subset = subset.merge(calib_table, on=['delta_calib', 'toa'], how='left').dropna(subset='calibrated_time')

        # selecting for a given delta_calib
        # calib_table = calib_table.loc[calib_table.delta_calib==0, ['toa', 'calibrated_time']]
        # subset = subset.merge(calib_table, on='toa', how='left').dropna(subset='calibrated_time')

        # alternative
        # subset = calib_table[calib_table.delta_calib==0]
        # subset['calibrated_time'] = subset.toa.map(subset.reindex(subset.toa_bin).calibrated_time)/1e3

        # # MAP taking into account the lsb from cal
        # subset['calibrated_time_lsb_wise'] = subset.apply(lambda row: calib_table.loc[(calib_table.toa==row.toa) & (calib_table.delta_calib==row.delta), 'calibrated_time'], axis=1)
        #
        # # faster alternative
        # subset['calibrated_time_lsb_wise'] = calib_table.reindex(pd.MultiIndex.from_frame(subset[['delta_calib', 'toa']].astype(str)), fill_value=np.NAN).to_numpy()

        df_pivot_calibrated_mean = pd.pivot_table(subset, values='calibrated_time',
                                                  index='toa', aggfunc="mean").reset_index()

        df_pivot_mean.merge(df_pivot_calibrated_mean, on='toa', how='inner')
        df_pivot_mean = df_pivot_mean.sort_values('toa')

        try:
            fitParam, cov = opt.curve_fit(modelFitLinear, df_pivot_mean[xvar],
                                          df_pivot_mean.calibrated_time)
        except:
            fitParam = [0, 0]
        lsb = fitParam[0]

        yfit = modelFitLinear(df_pivot_mean[xvar], *fitParam)
        inl = (yfit - df_pivot_mean.calibrated_time) / lsb

        plt.subplot(121)
        ax = plt.plot(df_pivot_mean[xvar], yfit, linestyle='--',
                      label='Fit corrected data %.2f' % (lsb * 1e3))
        plt.scatter(df_pivot_mean[xvar], df_pivot_mean.calibrated_time,
                    label='corrected using calibration table', color=ax[0].get_color())
        plt.subplot(122)
        plt.plot(df_pivot_mean[xvar], inl, marker='.',
                 label='INL rms={:.2f}  {:.2f}/{:.2f} fit lsb = {:.0f}/{:.0f} ps - corrected data'
                 .format(np.std(inl), np.nanmin(inl), np.nanmax(inl), np.nanmin(inl) * lsb * 1e3,
                         np.nanmax(inl) * lsb * 1e3))

    if not os.path.exists(folder):
        os.makedirs(folder)

    if saveDF:
        df_pivot_mean.to_csv(folder + 'inl_ch%d_pivot_mean.csv' % channel)

    plt.figure(3)
    plt.subplot(121)
    plt.ylabel("Time [ns]")
    plt.title("TDC TOA linearity")
    plt.xlabel("TOA [LSB]")
    plt.grid()
    plt.legend()

    plt.subplot(122)
    plt.xlabel("TOA [LSB]")
    plt.ylabel("INL [LSB]")
    plt.title("Integral non-linearity [LSB]")
    plt.grid()
    plt.legend()

    # plt.tight_layout()
    mng = plt.get_current_fig_manager()
    mng.full_screen_toggle()

    plt.savefig(folder + "/inl_ch%d.png"%channel)
    plt.show()


def plot_non_linearities_internal(df, config, calib_table_filepath=None, saveDF=False):
    # NON LINEARITIES on one method
    ###############################

    yvar = 'real_time_ns'  # ['real_time_ns', 'lsb_fromCAL']

    # with alive_bar(len(injected_channel_list) * 2, force_tty=True) as bar:
    for board in config['board']:

        for channel in config['config_B%d'%board]['enable_TL_ASIC_ch'][0]:
            for channel_gain in config['config_B%d'%board]['tdc_injected'][0]:

                suffix = '_%s_ch%d_B%d' % (channel_gain, channel, board)
                xvar = 'toa'+suffix
                # yvar = 'toa_ns_B'

                plt.figure(0, figsize=(15, 8))

                for monotonic in np.unique(df.loc[:, 'monotonic'+suffix]):
                    # if monotonic==0:
                    #     continue
                    subset = df[df['monotonic'+suffix]==monotonic]
                    df_pivot_mean = pd.pivot_table(subset, values=yvar, index=xvar, aggfunc="mean").reset_index()

                    try:
                        fitParam, cov = opt.curve_fit(modelFitLinear, df_pivot_mean[xvar], df_pivot_mean[yvar])
                    except:
                        fitParam = [0, 0]
                    slope = fitParam[0]
                    # delayOffset = fitParam[1]
                    lsb = abs(slope)

                    df_pivot_mean[yvar + '_fit'] = modelFitLinear(df_pivot_mean[xvar], *fitParam)
                    inl = df_pivot_mean['inl'] = (df_pivot_mean[yvar + '_fit'] - df_pivot_mean[yvar]) / lsb


                    ax = plt.subplot(121)
                    plt.annotate(config['datapath_to_display'], xy=(5, 7), xycoords='axes pixels')  # 'axes pixels

                    ax1 = plt.plot(df_pivot_mean[xvar], df_pivot_mean[yvar + '_fit'], '--', linewidth=1, color='black')

                    plt.scatter(df_pivot_mean[xvar], df_pivot_mean[yvar], s=2, label='Fit averaged data  LSB = %.2f ps' % (lsb * 1e3))  # color=ax1[0].get_color()
                    # plt.scatter(df_pivot_mean[xvar], df_pivot_mean['real_time_ns'], s=2, label='real time')

                    plt.subplot(122, sharex=ax)
                    plt.plot(df_pivot_mean[xvar], inl, marker='.',
                             label='INL rms={:.2f} lsb/{:.0f} ps  min/max {:.2f}/{:.2f} fit lsb = {:.0f}/{:.0f} ps'
                             .format(np.std(inl), np.std(inl) * lsb * 1e3, np.nanmin(inl), np.nanmax(inl), np.nanmin(inl) * lsb * 1e3,
                                     np.nanmax(inl) * lsb * 1e3))
                    # # +'\n'+'Excluding |INL| > %d'%inl_cut)

                    # Correct data using calibration table
                    ###############################

                    if calib_table_filepath is not None:
                        calib_table = pd.read_csv(calib_table_filepath)

                        # MAP no matter lsb obtained from cal
                        calib_table = calib_table[['delta_calib', 'toa', 'calibrated_time']]
                        subset = subset.merge(calib_table, on=['delta_calib', 'toa'], how='left').dropna(subset='calibrated_time')

                        # selecting for a given delta_calib
                        # calib_table = calib_table.loc[calib_table.delta_calib==0, ['toa', 'calibrated_time']]
                        # subset = subset.merge(calib_table, on='toa', how='left').dropna(subset='calibrated_time')

                        # alternative
                        # subset = calib_table[calib_table.delta_calib==0]
                        # subset['calibrated_time'] = subset.toa.map(subset.reindex(subset.toa_bin).calibrated_time)/1e3

                        # # MAP taking into account the lsb from cal
                        # subset['calibrated_time_lsb_wise'] = subset.apply(lambda row: calib_table.loc[(calib_table.toa==row.toa) & (calib_table.delta_calib==row.delta), 'calibrated_time'], axis=1)
                        #
                        # # faster alternative
                        # subset['calibrated_time_lsb_wise'] = calib_table.reindex(pd.MultiIndex.from_frame(subset[['delta_calib', 'toa']].astype(str)), fill_value=np.NAN).to_numpy()

                        df_pivot_calibrated_mean = pd.pivot_table(subset, values='calibrated_time',
                                                                  index='toa', aggfunc="mean").reset_index()

                        df_pivot_mean.merge(df_pivot_calibrated_mean, on='toa', how='inner')
                        df_pivot_mean = df_pivot_mean.sort_values('toa')

                        try:
                            fitParam, cov = opt.curve_fit(modelFitLinear, df_pivot_mean[xvar],
                                                          df_pivot_mean.calibrated_time)
                        except:
                            fitParam = [0, 0]
                        lsb = fitParam[0]

                        yfit = modelFitLinear(df_pivot_mean[xvar], *fitParam)
                        inl = (yfit - df_pivot_mean.calibrated_time) / lsb

                        plt.subplot(121)
                        ax = plt.plot(df_pivot_mean[xvar], yfit, linestyle='--',
                                      label='Fit corrected data %.2f' % (lsb * 1e3))
                        plt.scatter(df_pivot_mean[xvar], df_pivot_mean.calibrated_time,
                                    label='corrected using calibration table', color=ax[0].get_color())
                        plt.subplot(122)
                        plt.plot(df_pivot_mean[xvar], inl, marker='.',
                                 label='INL rms={:.2f}  {:.2f}/{:.2f} fit lsb = {:.0f}/{:.0f} ps - corrected data'
                                 .format(np.std(inl), np.nanmin(inl), np.nanmax(inl), np.nanmin(inl) * lsb * 1e3,
                                         np.nanmax(inl) * lsb * 1e3))

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

                plt.tight_layout()
                # mng = plt.get_current_fig_manager()
                # mng.full_screen_toggle()

                output_folder = config['save_folder']+'/inl/'
                if not os.path.exists(output_folder):
                    os.makedirs(output_folder)
                plt.savefig(output_folder + "inl_ch%d_%s.png" % (channel, channel_gain))
                plt.show()
                plt.close()


        if not os.path.exists(config['save_folder']):
            os.makedirs(config['save_folder'])

        if saveDF:
            df_pivot_mean.to_csv(config['save_folder'] + 'inl_ch%d_pivot_mean.csv' % channel)




def analyse_jitter_complex(folder, calib_table_filepath=None, saveDF=True):
    # works on the entire dataset, not on a monotonous selection restricted to only bits from the TDC itself,
    # thus requires all counters (in temporoc's digital, in the FPGA)
    # the delay box allows sweeping the TDC range from 0 to 20 ns, should be enougth to see the 320MHz clock effects on the jitter
    # compute for each delay the average and standard deviation of the TOA + histogram

    # each file contains the all matrix
    filepath_list = glob.glob(folder + "/*.csv")

    save_folder = folder + '/jitter/'
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    for filepath in filepath_list:
        df = pd.read_csv(filepath)

        # in nanoseconds
        # df['real_time'] = df.delay*0.01 # 10 ps step  # MEASUREMENT
        df['real_time'] = df.hitTime * 1e9  # SIMU  todo
        df = df.sort_values('real_time')

        for ch in range(65): # 64 is standalone TDC
            ch_str = '_' + str(ch)
            if 'toa'+ch_str not in df.columns:
                print("No data for channel %d"%ch)
                break
            df['toa'+ch_str] = df['TOAfine' + ch_str] + 31 * df['TOAcoarse' + ch_str]
            df['delta_calib'+ch_str] = df['CALfine' + ch_str] + 31 * df['CALcoarse' + ch_str] - df['toa'+ch_str]
            df['lsb_fromCAL'+ch_str] = 2 * 3125 / df.delta_calib

            offset = df['CPT' + ch_str]*3.125 +  df['global']*50 + df['super_coarse']*51200
            # counter at 320 MHz in temporoc : LSB 4 bits per channel + MSB 10 bits per cluster + counter at 50 µs in FPGA per frame
            # todo labels super coarse counter

            # method A: lsb from full charac
            # not to apply here

            # method B: lsb extracted from the full caracteristic & calibration lsb
            df['toa_ns_B' + ch_str] = df['toa' + ch_str] * np.mean(2 * 3125 /df['delta_calib'+ch_str]) / 1e3 + offset

            # method C:
            df['toa_ns_C' + ch_str] = df['toa' + ch_str] * 2 * 3125 / df['delta_calib' + ch_str] / 1e3 + offset

            # method D:
            if calib_table_filepath is not None:
                calib_table = pd.read_csv(calib_table_filepath)

                # MAP no matter lsb obtained from cal
                calib_table = calib_table[['delta_calib', 'toa', 'calibrated_time']]
                df = df.merge(calib_table, on=['delta_calib', 'toa'], how='left').dropna(subset='calibrated_time')
                df = df.rename(columns={"toa": "toa_ns_D"+ch_str})
                df["toa_ns_D"+ch_str] += offset

        # plot jitter heatmap comparison channel versus delay
        for chA in [0]: #range(65):
            for mi, method in enumerate(['B', 'C', 'D']):
                matching_chB_with_1chA = []
                # compute data
                for chB in [1]: # range(65):
                    if (chA == chB) or ('toa_ns_' + method + str(chA) not in df.columns) or ('toa_ns_' + method + str(chB) not in df.columns):
                        break
                    df['toa_diff_ns_'+method+str(chA)+'-'+str(chB)] = df['toa_ns_'+method+str(chA)].sub(df['toa_ns_'+method+str(chB)], axis=0)
                    matching_chB_with_1chA += ['toa_diff_ns_'+method+str(chA)+'-'+str(chB)]
                    # subset = df['toa_diff_ns_'+method+str(chA)+'-'+str(chB)].groupby(['delay']).mean()

                # For one channel chA, time difference with every chB available
                plt.figure(mi, figsize=(10, 10))
                plt.suptitle("Jitter extracted from time difference between ch %d and others for conversion method %s"%(chA, method))
                for li, metric in enumerate(['mean', 'std']):
                    ax = plt.subplot(1, 2, li+1)
                    map_channels_vs_delay = pd.pivot_table(df, columns='delay', values=matching_chB_with_1chA, aggfunc=metric)
                    im = plt.imshow(map_channels_vs_delay.values, origin='lower')
                    plt.title(metric+' time difference')
                    xrange = range(len(map_channels_vs_delay.columns))
                    yrange = range(len(map_channels_vs_delay.index))
                    plt.xticks(xrange, map_channels_vs_delay.columns) # delay
                    plt.yticks(yrange, map_channels_vs_delay.index+1) # comparison channels
                    plt.xlabel("Delay [ns]")
                    plt.ylabel("Comparison channel")
                    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                    plt.grid()
                    plt.legend()

                    # write number
                    for y in range(15):
                        for x in xrange:
                            ax.text(x, y, map_channels_vs_delay.loc[y, x], ha="center", va="top", color="w", fontsize=8)

                plt.tight_layout()
                figManager = plt.get_current_fig_manager()
                figManager.window.showMaximized()

                plt.savefig(save_folder + "/heatmap_ch%d_method_%d.png" % (chA, method))
                plt.close("all")

        #####
        # Looking only at 2 channels
        chA = 0
        chB = 1

        # Plot jitter between ch0-ch1 versus delay for various correction methods
        plt.figure(2, figsize=(10, 10))
        plt.title("Jitter between channels %d-%d for various time conversion methods"%(chA, chB))
        for method in ['B', 'C', 'D']:
            column_name = 'toa_diff_ns_' + method + str(chA) + '-' + str(chB)
            df_plot = pd.pivot_table(df, columns='delay', values=column_name, aggfunc='std')
            df_stat = pd.pivot_table(df, columns='delay', values=column_name, aggfunc='count')
            plt.errorbar(df_plot.delay, df_plot[column_name], yerr = 1/np.sqrt(df_stat[column_name]), label='method %s'%method)

        plt.xlabel("Delay [ns]")
        plt.title("Method %s " % method)
        plt.ylabel("Jitter as RMS ")
        plt.grid()
        plt.legend()

        plt.tight_layout()
        figManager = plt.get_current_fig_manager()
        figManager.window.showMaximized()
        plt.savefig(save_folder + "/time_conversion_methods_ch%d_vs_ch%d.png" % (chA, chB))


        # Plot time difference between ch0 and 1 for one given delay for various methods
        unique_delay_list = np.unique(df.delay)
        chosen_delay = unique_delay_list[-1]
        mask = df['delay'] == chosen_delay

        plt.figure(2, figsize=(10, 8))
        plt.suptitle("Histogram time diff between 2 channels %d-%d for delay %.2e ns for various time conversion methods", chA, chB, chosen_delay)
        for li, method in enumerate(['B', 'C', 'D']):
            plt.subplot(1,2,li+1)
            column_name = 'toa_diff_ns_'+method+str(chA)+'-'+str(chB)

            count, edges = plt.hist(df.loc[mask, column_name], bins=50, label='TDC RMS jitter = std/sqrt(2) = %.2f ps' % (
                    np.std(df.loc[mask, column_name].values)*1e3 / np.sqrt(2)))

            try:  # Fit gaussian timing difference
                fitParam, cov = opt.curve_fit(modelGauss, edges, count,
                                              p0=[edges[np.argmax(count)], .01, max(count)])
                meanHisto = fitParam[0]
                sigmaHisto = fitParam[1]
                ampHisto = fitParam[2]
                # xmin = min(edges)
                # xmax = max(edges)
                xmin = meanHisto - 5 * sigmaHisto
                xmax = meanHisto + 5 * sigmaHisto

                xfit = np.arange(xmin, xmax, (xmax-xmin)/100)
                yfit = modelGauss(xfit, meanHisto, sigmaHisto, ampHisto)
                plt.plot(xfit, yfit, linestyle='--', color='red', label='sigma = %.2f ps '%(sigmaHisto*1e3))

            except RuntimeError:
                print("ERROR fit Gaussian")

            plt.xlabel("Time difference [ns]")
            plt.title("Method %s "%method)
            plt.ylabel("Count")
            plt.grid()
            plt.legend()

            plt.subplot(1,2, li+1+3)
            df.loc[mask, column_name].sort_values('iter', inplace=True)
            plt.plot(df.loc[mask, 'iter'], df.loc[mask, column_name])
            plt.xlabel("Iter")
            plt.ylabel("Time difference [ns]")
            plt.title("Is time difference constant with time ?")
            plt.grid()
            plt.legend()

        plt.tight_layout()
        figManager = plt.get_current_fig_manager()
        figManager.window.showMaximized()
        plt.savefig(save_folder + "/histo_time_diff_ch%d_vs_ch%d_delay%d.png" % (chA, chB, chosen_delay))
        plt.close("all")

        if saveDF:
            df.to_csv(save_folder)

def analyse_linearity(folder, calib_table_filepath=None):
    filepath_list = glob.glob(folder + "/*.csv")

    for filepath in filepath_list:

        N = int(re.findall("(?<=N_)[0-9]+", filepath)[0])
        hitFreq = int(re.findall("(?<=hitFreq_)[0-9]+", filepath)[0])

        df = pd.read_csv(filepath)

        if 'cluster' in filepath:
            cluster = int(re.findall("(?<=cluster_)[0-9]+", filepath)[0])
            channels = [i for i in range(16)]
        else:
            # standalone TDC
            cluster = None
            channels = ['']

        # in nanoseconds
        # df['real_time'] = df.delay*0.01 # 10 ps step  # MEASUREMENT
        df['real_time'] = df.hitTime*1e9  # SIMU  todo
        df = df.sort_values('real_time')

        for ch in channels:
            ch_str = '_'+str(ch)
            df['toa'] = df['TOAfine'+ch_str] + 31 * df['TOAcoarse'+ch_str]
            df['cal'] = df['CALfine'+ch_str] + 31 * df['CALcoarse'+ch_str]
            df['delta_calib'] = df.cal - df.toa

            df['lsb_fromCAL'] = 2 * 3125 / df.delta_calib

            subset = select_monotonous_data(df, expected_step)

            plot_all_points(subset, N, hitFreq, folder)

            plot_average_per_delay(subset, N, hitFreq, folder, ch, saveDF=True)

            plot_non_linearities(subset, folder, ch, calib_table_filepath, yvar='real_time', saveDF=True)

            plt.show()
            plt.close("all")




def analyse_standalone_code_density(filepath):
    folder_index_str = os.path.basename(filepath)[:1]
    folder = os.path.dirname(filepath) + '/' + folder_index_str + '/'

    if not os.path.exists(folder):
        os.makedirs(folder)

    rangeTDCtoa_ps = 3125  # ps
    filename = os.path.basename(filepath)

    df = pd.read_csv(filepath)

    label_events_dropped, selection = drop_erroneous_events(df)
    df = df.loc[selection, :]
    # df.drop(df[(df.error != 0)].index, inplace=True)

    df['toa'] = df.TOAfine + 31 * df.TOAcoarse
    df['cal'] = df.CALfine + 31 * df.CALcoarse
    df['delta'] = df.cal - df.toa
    df['lsb_fromCAL'] = 2 * rangeTDCtoa_ps / df.delta

    channel_stats = {'channel':[],
                     'cluster':[],
                     'channel_gain':[],
                     'tdc_null_count': [],
                     'lsb_ps':[]}
    channel_stats.update({'%s_%s_%s'%(meas, typeMeas, unit):[] for meas in ['INL', 'DNL'] for typeMeas in ['RMS', 'MIN', 'MAX'] for unit in ['ps', 'lsb']})

    channel = 64
    channel_gain = ''


    cluster = channel // 16
    cluster_channel = channel % 16
    channel_stats['channel'].append(channel)
    channel_stats['channel_gain'].append(channel_gain)
    channel_stats['cluster'].append(cluster)

    channel_suffix = '' # standalone TDC

    # select data for cluster
    df = df[df.cluster==cluster]

    # remove null frames
    null_selection = df['tdc' + channel_suffix] == 0
    null_count_array = null_selection.value_counts()[null_selection.value_counts().index == True].values
    null_count_left_for_this_ch_gain = null_count_array[0] - 1 if null_count_array else 0
    df = df[~null_selection].reset_index()

        # board = config['board'][0]
        # df_filename = '%s_B%d' % (folder_index_str, board)
        # stats_filepath =  folder + df_filename + "_stats.csv"
        # stats_df = pd.read_csv(stats_filepath)
        # null_count_already_removed = stats_df['all_tdc_null_count'].sum(axis=0)
        # total_event_count = stats_df['raw_event_count'].sum(axis=0)
        # null_tdc_field_count = null_count_left_for_this_ch_gain + null_count_already_removed
        # null_tdc_field_fraction = null_tdc_field_count/total_event_count
    null_tdc_field_fraction = -1
    channel_stats['tdc_null_count'].append(null_tdc_field_fraction)

    # delta_list = np.append(0, np.unique(df.delta)) # todo
    delta_list = [0] # always ends with 0 !
    fig2, ax2 = plt.subplots(len(delta_list), 1, figsize=(15, 7), sharex=True)
    if len(delta_list)>1:
        ax2 = ax2.reshape(-1)
    else:
        ax2 = [ax2]
    ax2[0].annotate('\n'.join(filename), xy=(5, 7), xycoords='figure pixels')

    fig3, ax3 = plt.subplots(1, 3, figsize=(15, 7), sharex=True)
    ax3 = ax3.reshape(-1)
    ax3[0].annotate('\n'.join(filename), xy=(5, 7), xycoords='figure pixels')


    for i, delta in enumerate(delta_list):

        # select calibration event according to their self-measured calibration lsb
        if delta!=0:
            subset = df[df['delta'+channel_suffix] == delta]
        else: # take all events without discrimination
            subset = df
        ax2[-1].set_xlabel('TOA [LSB]')

        compute_bin_width(subset, None, rangeTDCtoa_ps)


def get_board_list_from_df(df):
    if 'board' in df.columns:
        board_list = np.unique(df['board'])
    else:
        board_list = np.unique(df.columns.map(lambda row: re.findall("(?<=_B)[0-9]+", row)))
        board_list = board_list[board_list.astype(bool)][0]
        board_list = [int(board[0]) for board in board_list]

    return board_list

def get_board_ch_gain_from_suffix(suffix):
    board = int(re.findall("(?<=_B)[0-9]+", suffix)[0])
    channel = int(re.findall("(?<=_ch)[0-9]+", suffix)[0])
    gain = 'high' if 'high' in suffix else 'low'
    return gain, channel, board

def get_suffix_list_from_frames(df, board=None):
    if board == None:
        return [col[3:] for col in df.columns if 'toa' in col]
    else:
        return [col[3:] for col in df.columns if ('toa' in col) & ('B%d'%board in col)]


def get_suffix_list_from_calib_file(df):
    if ('board' in df.columns) & ('channel' in df.columns) & ('gain' in df.columns):
        return df[['board', 'channel', 'gain']].drop_duplicates()
    else:
        print("Unable to find channel suffix list from df provided with columns :")
        print(df.columns.to_list())
        exit(0)
    return []


def compute_bin_width(df, config, plot=True):
    calib_dict_per_tdc = {'board':[], 'channel': [], 'gain': [], 'toa': [], 'lsb_fromCAL': [], 'bin_width': [],
                          'calibrated_toa_range_fraction': [], 'calibrated_time': []}
    # 'delta_calib': [],

    output_folder = config['output_folder'] + '/bin_width/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    if os.path.exists(config['output_folder'] + 'tdc_data_valid_fraction_per_channel.png'):
        print("Skipping compute_bin_width() : already existing results !")
        return

    toa_tdc_stats = {'board': [],
                     'channel': [],
                     'gain': [],
                     'tdc_data_valid_fraction': [],
                     'calib_lsb_ps': [],
                     'TOA_DR_lsb': []}

    channel_stats_filename = config['output_folder'] + '/tdc_CAL_stats_per_channel.csv'
    calib_table_filename = config['output_folder'] + '/tdc_DNL_TOA_calib_table.csv'
    # calib_table_filename = config['output_folder'] + '/B%d_toa_DNL_TOA_CAL_calib_table.csv' % config['board'][0]

    # board_list = get_board_list_from_df(df)
    channel_suffix_list = get_suffix_list_from_frames(df)

    for channel_suffix in channel_suffix_list:
        gain, channel, board = get_board_ch_gain_from_suffix(channel_suffix)

        tempo_dig_ck = config['config_B%d' % board]['tempo_dig_ck']
        rangeTDCtoa_ps =  1e6/tempo_dig_ck
        # board_config = config['config_B%d' % board]

        # for channel in board_config['enable_TL_ASIC_ch'][0]:
        #     for gain in board_config['tdc_injected'][0]:

        # channel_suffix = '_%s_ch%d_B%d' % (gain, channel, board)
        # print(channel_suffix)

        tdc_has_triggered_selection = df['tdc_data_valid' + channel_suffix]
        tdc_has_triggered_fraction = sum(tdc_has_triggered_selection) / len(df)

        plot_lsb_vs_time_for_one_ch(df, channel, gain, config, board, plot=(channel==0)|(channel==43))
        # stable_lsb_selection =
        # selection = df['tdc_data_valid' + channel_suffix] & stable_lsb_selection
        # subset = df[selection]
        subset = df

        all = True
        if all:
            label = 'toa'
            bins = np.unique(subset[label + channel_suffix])  # maybe has missing codes thus take min max to recreate bining
            totalCounts = len(subset[label + channel_suffix])
            counts, bins_edges = np.histogram(subset[label + channel_suffix],
                                              bins=np.arange(min(bins), max(bins) + 2, 1))
            # binedges = 0.5 * (bins[1:] + bins[:-1]

            # lsb_target = subset['lsb_fromCAL' + channel_suffix].mean() * 1e3
            lsb_target = 2*3125/subset['delta' + channel_suffix].mean()
            TOA_DR_lsb = len(np.unique(subset[label + channel_suffix]))
            TOA_DR_ps = TOA_DR_lsb * lsb_target
            # TOA_DR_ps = rangeTDCtoa_ps
            offset = TOA_DR_ps / 2
            binWidth = counts / totalCounts * TOA_DR_ps
            yerr = binWidth / (counts ** 0.5)
            toa_bins = bins_edges[:-1]
            integral_iMinus1 = np.cumsum(binWidth)
            calibrated_time = integral_iMinus1 - binWidth / 2 + offset
            fractions = counts / totalCounts
            # offset = min(bins)*fit_lsb
            calibrated_fraction = np.cumsum(fractions) - fractions / 2

            calib_dict_per_tdc['board'] += [board] * len(binWidth)
            calib_dict_per_tdc['channel'] += [channel] * len(binWidth)
            calib_dict_per_tdc['gain'] += [gain] * len(binWidth)
            calib_dict_per_tdc['toa'] += list(toa_bins)
            calib_dict_per_tdc['lsb_fromCAL'] += [lsb_target] * len(binWidth)
            calib_dict_per_tdc['bin_width'] += list(binWidth)
            calib_dict_per_tdc['calibrated_toa_range_fraction'] += calibrated_fraction.tolist()
            calib_dict_per_tdc['calibrated_time'] += (calibrated_time / 1e3).tolist()

            # a = subset[['toa' + channel_suffix, 'cal' + channel_suffix]].groupby(
            #     ['toa' + channel_suffix, 'cal' + channel_suffix], as_index=False).size()
            # totalCounts = len(subset['toa' + channel_suffix])
            # counts = a['size']
            # toa_bins = a['toa' + channel_suffix]
            # cal_bins = a['cal' + channel_suffix]
            # # a['ratio'] = a['size'] / a.groupby('toa' + channel_suffix)['size'].transform('sum')
            # TOA_DR_lsb = len(np.unique(subset['toa'+channel_suffix]))
            # TOA_DR_ps = TOA_DR_lsb * lsb_target
            # # TOA_DR should be equal to the clock period
            # offset = TOA_DR_ps / 2
            # binWidth = counts / totalCounts * TOA_DR_ps
            # yerr = binWidth / (counts ** 0.5)
            # calibrated_time = np.cumsum(binWidth) - binWidth / 2 + offset
            # bins_edges = np.arange(0, len(binWidth)+1, 1)
            # fractions = counts / totalCounts
            # calibrated_fraction = np.cumsum(fractions) - fractions / 2
            #
            # calib_dict_per_tdc['channel'] += [channel] * len(binWidth)
            # calib_dict_per_tdc['gain'] += [gain] * len(binWidth)
            # calib_dict_per_tdc['toa'] += list(toa_bins)
            # calib_dict_per_tdc['cal'] += list(cal_bins)
            # calib_dict_per_tdc['bin_width'] += list(binWidth)
            # calib_dict_per_tdc['calibrated_toa_range_fraction'] += calibrated_fraction.tolist()
            # calib_dict_per_tdc['calibrated_time'] += (calibrated_time / 1e3).tolist()

            # (!) this TDC has a variable dynamic range, moving with temperature, voltage
            # and do not start at 0 but around 80 up to 140

            if plot:
                plt.bar(bins_edges[:-1], binWidth, width=1, yerr=yerr, color=plt.rcParams['axes.prop_cycle'].by_key()['color'][0],
                   label='#%d events  TOA DR = %d [lsb]\nbin width : mean from toa = %.2f ps    from cal = %.2f ps\nstd(bin width)_toa = %.1f ps  '
                         'mean(std(bin width)_bin)_toa = %.1f ps'%
                         (totalCounts,  TOA_DR_lsb, np.mean(binWidth), lsb_target, np.std(binWidth), np.nanmean(yerr)))
                        #   mean from non-zero toa = %.2f ps        np.mean(subset.bin_width[np.nonzero(subset.bin_width)])
                plt.ylabel('Bin width [ps]')
                plt.grid()
                plt.legend()

        else:
            totalCounts = len(subset['TOAfine' + channel_suffix])

            TOAcoarse_list = np.sort(np.unique(subset['TOAcoarse' + channel_suffix]))
            plt.subplots(len(TOAcoarse_list) // 2 + 1, 2, figsize=(15, 7), sharex=True)
            # plt.subplots(1, 2, figsize=(15, 7), sharex=True)
            # plt.figure(figsize=(15, 7))
            colors = plt.cm.jet(np.linspace(0, 1, len(TOAcoarse_list)))
            # ax.set_prop_cycle(rcsetup.cycler('color', plt.cm.jet(idx)))
            # colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
            # hatches = ['--', '+', 'x', '\\', '*', 'o', 'O', '.', '//', '\\/...', 'b']

            for i, TOAcoarse in enumerate(TOAcoarse_list):
                plt.subplot(len(TOAcoarse_list) // 2 + 1, 2, (i // 2) * 2 + (i % 2) + 1)
                # plt.subplot(1, 2, (i%2)+1)
                plt.title(TOAcoarse)
                counts, bins_edges = np.histogram(
                    subset.loc[subset['TOAcoarse' + channel_suffix] == TOAcoarse, 'TOAfine' + channel_suffix],
                    bins=np.arange(0, 32, 1))
                # binedges = 0.5 * (bins[1:] + bins[:-1])
                binWidth = counts * rangeTDCtoa_ps / totalCounts
                yerr = binWidth / (counts ** 0.5)

                average_lsb = subset.loc[
                    subset['TOAcoarse' + channel_suffix] == TOAcoarse, 'lsb_fromCAL' + channel_suffix].mean()

                # plt.hist(bins_edges[:-1], bins_edges, weights=binWidth, align='left', color=colors[i], hatch=hatches[i]) #, fill=True, alpha=0.5)

                plt.bar(bins_edges[:-1], binWidth, width=1, yerr=yerr,
                        color=colors[0],
                        label='#%d events   bin width : mean from toa = %.2f ps    from cal = %.2f ps    std(bin width)_tdc = %.1f ps  '
                              'mean(std(bin width)_bin)_tdc = %.1f ps ' %
                              (totalCounts, np.mean(binWidth), average_lsb, np.std(binWidth), np.nanmean(yerr)))
                plt.grid()
                plt.tight_layout()

        toa_tdc_stats['board'].append(board)
        toa_tdc_stats['channel'].append(channel)
        toa_tdc_stats['gain'].append(gain)
        toa_tdc_stats['tdc_data_valid_fraction'].append(tdc_has_triggered_fraction)
        toa_tdc_stats['calib_lsb_ps'].append(lsb_target)
        toa_tdc_stats['TOA_DR_lsb'].append(TOA_DR_lsb)

        tdc_CAL_df = pd.DataFrame(toa_tdc_stats)
        tdc_CAL_df.to_csv(channel_stats_filename, index=None)

        calib_table = pd.DataFrame(calib_dict_per_tdc)
        calib_table.to_csv(calib_table_filename, index=None)

        if plot:
            plt.title('Channel %d %s TDC TOA bin widths - Code density test' % (
                channel, gain))
            plt.xlabel('TOA bin')
            plt.tight_layout()
            plt.savefig(output_folder + 'ch%d_%s_bin_width.png' % (channel, gain))
            # plt.show()
            plt.close()

        # cut = 64
        # binWidth = binWidth[np.nonzero(binWidth)]
        # ax.axhline(y=np.mean(binWidth[0:cut]), xmin=0, xmax=cut / 127,
        #            label='first part : mean bin width = %.1f ps ' % (np.mean(binWidth[0:cut])), color='red')
        # ax.axhline(y=np.mean(binWidth[cut + 1:127]), xmin=(cut + 1) / 127, xmax=1,
        #            label='second part : mean bin width = %.1f ps ' % (np.mean(binWidth[cut + 1:127])), color='orange')

    # PLOT tdc_has_triggered_fraction
    plt.plot(tdc_CAL_df.channel, tdc_CAL_df.tdc_data_valid_fraction,
             label='tdc_data_valid_fraction')
    plt.legend()
    plt.grid()
    plt.xlabel('Channel')
    plt.title('Fraction of TDC data exploitable')
    plt.tight_layout()
    plt.savefig(config['output_folder'] + 'tdc_data_valid_fraction_per_channel.png')
    # plt.show()
    plt.close()



def compute_abs_ps_time_for_all_channels(df, config, time_conversion_method='lsb_fromCAL_moving_avg'):
    for board in config['board']:
        board_config = config['config_B%d'%board]
        tempo_dig_ck = config['config_B%d' % board]['tempo_dig_ck']
        label_xaxis = 'CPT_B%d' % board
        if label_xaxis not in df.columns:
            print("using CPT instead of "+label_xaxis)
            label_xaxis = 'CPT'
        CPT_offset_ns = df[label_xaxis]*1e3/tempo_dig_ck
        for channel in board_config['enable_TL_ASIC_ch'][0]:
            new_df = compute_ps_time_within_one_msb_cpt(df, config, channel, board, time_conversion_method)
            df = pd.concat([df, new_df], axis=1)
            suffix = '_low_ch%d_B%d'%(channel, board)
            df['toa_ns' + suffix] += CPT_offset_ns

def compute_ps_time_within_one_msb_cpt_for_all_channels(df, config, time_conversion_method):
    for board in config['board']:
        board_config = config['config_B%d'%board]
        for channel in board_config['enable_TL_ASIC_ch'][0]:
            gain_list = config['config_B%d' % board]['tdc_injected'][0]
            for gain in gain_list:
                df = compute_ps_time_within_one_msb_cpt(df, config, channel, gain, board, time_conversion_method)
    return df

def compute_ps_time_within_one_msb_cpt(df, config, channel, gain, board, time_conversion_method,
                                       verbose=False, tdc_CAL_df=None,
                                    toa_NL_stats_df=None, ref_DNL_TOA_calib_table_filename=None):
    brand_new_series_set = {}

    suffix = '_%s_ch%d_B%d'%(gain, channel, board)

    if ('toa' + suffix) not in df.columns:
        print('toa'+suffix+" not in df for compute_ps_time_within_one_msb_cpt")
        return df

    # tdc_good_selection = df['tdc_good' + suffix]
    tdc_good_selection = df['time_error' + suffix]==0

    tempo_dig_ck = config['config_B%d' % board]['tempo_dig_ck']
    tdc_dynamic_range = 1e6 / tempo_dig_ck

    if time_conversion_method == 'lsb_fromCAL':

        lsb = 2 * 3125 / df.loc[tdc_good_selection, 'delta' + suffix]
        negative_lsb_count = np.sum(lsb <= 0)
        if negative_lsb_count>0:
            print("(!) %d (%d %%) negative lsb for %s"%(negative_lsb_count, negative_lsb_count/len(df)*100,suffix[1:]))

        brand_new_series_set['toa_ps' + suffix] = (-1) * df.loc[:, 'toa' + suffix] * lsb.mean()

    elif time_conversion_method == 'lsb_fromCAL_mean':
        if not tdc_CAL_df:
            print("tdc_CAL_df not existing !")
            exit(0)

        selection = (tdc_CAL_df.board == board) & (tdc_CAL_df.channel == channel) & (tdc_CAL_df.gain == gain)
        lsb_fromCAL_mean = tdc_CAL_df.loc[selection, 'mean_lsb_fromCAL'].iloc[0]
        brand_new_series_set['toa_ps' + suffix] = (-1) * df.loc[:, 'toa' + suffix] * lsb_fromCAL_mean


    elif time_conversion_method == 'lsb_fromFIT':
        selection = (toa_NL_stats_df.board == board) & (toa_NL_stats_df.channel == channel) & (
                    toa_NL_stats_df.gain == gain)
        lsb_fromCAL_mean = toa_NL_stats_df.loc[selection, 'fit_lsb_ps'].iloc[0]
        brand_new_series_set['toa_ps' + suffix] = (-1) * df.loc[:, 'toa' + suffix] * lsb_fromCAL_mean

    elif time_conversion_method == 'lsb_fromCAL_moving_avg':

        # lsb = df.loc[tdc_good_selection, 'lsb_fromCAL' + suffix]
        lsb = 2 * 3125 / df.loc[tdc_good_selection, 'delta' + suffix]

        moving_average_window = 100
        lsb_moving_average = lsb.rolling(moving_average_window).mean()

        brand_new_series_set['toa_ps' + suffix] = (-1) * df.loc[:, 'toa' + suffix] * lsb_moving_average

    elif time_conversion_method == 'DNL_TOA_CAL_calibrated_time':

        calib_table_filename = "B%d_toa_DNL_TOA_CAL_calib_table.csv"%board
        calib_table_path = config['root_folder'] + "../config/TEMPOROC/"+calib_table_filename

        if os.path.exists(calib_table_path):
            calib_table = pd.read_csv(calib_table_path)
        else:
            print("Could not find TDC TOA calibration table "+calib_table_filename)
            exit()

        # MAP taking into account the lsb obtained from cal
        calib_table_for_channel_gain = (calib_table.loc[
                                            (calib_table.channel == channel) & (calib_table.gain == 'low'), [
                                                'toa', 'cal', 'calibrated_time']]
                                        .rename(columns={'toa': 'toa' + suffix, 'cal': 'cal' + suffix,
                                                         'calibrated_time': 'calibrated_time' + suffix}))
        plt.figure()
        plt.scatter(calib_table_for_channel_gain['toa' + suffix], calib_table_for_channel_gain['cal' + suffix], label='calib')
        plt.scatter(df['toa' + suffix], df['cal' + suffix], label='data')
        plt.legend()
        plt.xlabel("toa")
        plt.ylabel("cal")
        plt.grid()
        plt.show()

        calibrated_time = df[['toa' + suffix, 'cal' + suffix]].merge(
            calib_table_for_channel_gain, on=['toa' + suffix, 'cal' + suffix], how='left')['calibrated_time' + suffix]

        brand_new_series_set['toa_ps' + suffix] = (-1e3) * calibrated_time

    elif time_conversion_method == 'DNL_TOA_calibrated_time':

        if ref_DNL_TOA_calib_table_filename:
            calib_table_path = ref_DNL_TOA_calib_table_filename
        else:
            # calib_table_path = config['output_folder'] + '/tdc_DNL_TOA_calib_table.csv'
            calib_table_path = config['output_folder'] + '/../B%d/code_density_tdc/tdc_DNL_TOA_calib_table.csv'%board
            if not os.path.exists(calib_table_path):
                # find calibration table
                calib_table_files = glob.glob(config['root_folder'] + "output/B%d_TPR*/serial_test/**/**/**/**/tdc_DNL_TOA_calib_table.csv"%board)
                if verbose:
                    print("Found %d DNL TOA calibration tables: (Using first) "%(len(calib_table_files)))
                    print('\n\t'.join(calib_table_files))
                calib_table_path = calib_table_files[0]

        # calib_table_filename = "tdc_DNL_TOA_calib_table.csv"
        # calib_table_path = config['root_folder'] + "../config/TEMPOROC/"+calib_table_filename
        if os.path.exists(calib_table_path):
            calib_table = pd.read_csv(calib_table_path)
            if verbose:
                print("TDC TOA calibration table " + calib_table_path)
        else:
            print("Could not find TDC TOA calibration table "+calib_table_path)
            exit()

        # MAP no matter lsb obtained from cal
        calib_table_for_channel_gain = (calib_table.loc[
                                            (calib_table.channel == channel) & (calib_table.gain == gain), [
                                                'toa', 'calibrated_time']]
                                        .rename(columns={'toa': 'toa' + suffix, 'calibrated_time': 'calibrated_time' + suffix}))

        brand_new_series_set['toa_ps' + suffix] = (-1e3) * df[['toa' + suffix]].merge(
            calib_table_for_channel_gain, on='toa' + suffix, how='left')['calibrated_time' + suffix]

    elif time_conversion_method == 'DNL_TOA_fraction':

        # find calibration table
        search_pattern = config['root_folder'] + "/serial_test/B%d*/**/**/tdc_DNL_TOA_calib_table.csv"%board
        calib_table_files = glob.glob(search_pattern)
        if len(calib_table_files)==0:
            print("No DNL TOA calibration tables found for board %d here: %s" % (board, search_pattern))
            exit()
        if len(calib_table_files)>1:
            print("Found %d DNL TOA calibration tables: " % (len(calib_table_files)) + str(calib_table_files))

        calib_table_path = calib_table_files[0]

        # calib_table_filename = "tdc_DNL_TOA_calib_table.csv"
        # calib_table_path = config['root_folder'] + "../config/TEMPOROC/"+calib_table_filename

        if os.path.exists(calib_table_path):
            calib_table = pd.read_csv(calib_table_path)
            print("TDC TOA calibration table chosen "+calib_table_path)

        else:
            print("Could not find TDC TOA calibration table "+calib_table_path)
            exit()

        # MAP no matter lsb obtained from cal
        calib_table_for_channel_gain = (calib_table.loc[
                                            (calib_table.channel == channel) & (calib_table.gain == 'low'), [
                                                'toa', 'lsb_fromCAL', 'calibrated_toa_range_fraction']]
                                        .rename(columns={'toa': 'toa' + suffix, 'calibrated_toa_range_fraction':'fraction' + suffix}))



        calibrated_fraction = df[['toa' + suffix]].merge(calib_table_for_channel_gain, on='toa' + suffix, how='left')['fraction' + suffix]
        lsb_fromCAL_reference = np.unique(calib_table_for_channel_gain.lsb_fromCAL)

        lsb = 2*3125/df.loc[tdc_good_selection, 'delta' + suffix]
        moving_average_window = 100
        lsb_moving_average = lsb.rolling(moving_average_window).mean()

        brand_new_series_set['toa_ps' + suffix] = - (calibrated_fraction * lsb_moving_average / lsb_fromCAL_reference * tdc_dynamic_range)

        # offset = 1e3 / tempo_dig_ck / 2
        # true offset not null but we don't care about absolute toa value,
        # so let's simplify computation by assuming offset = 0

    else:
        print("time_conversion_method not recognized !")

    # Count unmatch toa or cal codes from TDC to corresponding values
    if (time_conversion_method == 'DNL_TOA_fraction') | (time_conversion_method == 'DNL_TOA_calibrated_time')\
            | (time_conversion_method == 'DNL_TOA_CAL_calibrated_time'):
        unmatched_calib_toa_count = brand_new_series_set['toa_ps' + suffix].isna().sum()
        if unmatched_calib_toa_count > 0:
            print("unmatched_calib_toa_count", unmatched_calib_toa_count)
        config['unmatched_calib_toa_count' + suffix] = unmatched_calib_toa_count

    # Add lsb cpt coarse counter on 320 MHz clock
    brand_new_series_set['toa_ps' + suffix] += df['cpt' + suffix] * tdc_dynamic_range

    new_df = pd.DataFrame(brand_new_series_set)
    df = pd.concat([df, new_df], axis=1)

    return df

def plot_lsb_vs_time_for_all_ch(df, config, plot=True):
    for board in config['board']:
        board_config = config['config_B%d' % board]
        for channel in board_config['injected_channel'][0]:
            plot_lsb_vs_time_for_one_ch(df, channel, 'low', config, board=board, plot=plot)


def plot_lsb_vs_time_for_one_ch(df, ch, gain, config, board, plot=True):
    label_xaxis = 'CPT_B%d'%board
    if label_xaxis not in df.columns:
        label_xaxis = 'CPT'

    channel_suffix = '_%s_ch%d_B%d' % (gain, ch, board)
    # selection = df['tdc_data_valid' + channel_suffix]

    tempo_dig_ck = config['config_B%d' % board]['tempo_dig_ck']
    time = df.loc[:, label_xaxis] * 1e-6 / tempo_dig_ck / 60
    # lsb = df.loc[selection, 'lsb_fromCAL' + channel_suffix] * 1e3
    lsb = 2*3125/df.loc[:, 'delta' + channel_suffix]

    # if len(lsb) == 0:
    #     return selection

    moving_average_window = 100
    if plot:
        plt.scatter(time, lsb)

        if len(lsb) > moving_average_window:
            lsb_moving_average = lsb.rolling(moving_average_window).mean()
            # time_moving_average = time.rolling(moving_average_window).mean()

            coef = 0.0005
            thres_high = (1 + coef) * lsb_moving_average.median()
            thres_low = (1 - coef) * lsb_moving_average.median()
            selection = (lsb_moving_average < thres_high) & (lsb_moving_average > thres_low)

            # plt.plot(time_moving_average, lsb_moving_average, color='tab:orange',
            #          label='moving avg over %d samples' % moving_average_window)
            plt.plot(time, lsb_moving_average, color='tab:orange',
                     label='moving avg over %d samples' % moving_average_window)


            plt.scatter(time[~selection], lsb[~selection], label='rejected for computing stat. bin width', color='tab:red')
            plt.axhline(thres_high, linestyle='--', color='red', label='median + %.2f %%'%(coef*100))
            plt.axhline(thres_low, linestyle='--', color='red', label='median - %.2f %%'%(coef*100))

            plt.legend()
        plt.grid()
        plt.xlabel("Time [minute]")
        plt.ylabel("TDC calibration lsb [ps]")
        plt.title(channel_suffix)

        output_folder = config['output_folder'] + "cal_lsb_vs_injection_time/"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        plt.savefig(output_folder + "cal_lsb_vs_injection_time%s.png" % channel_suffix)
        # plt.show()
        plt.close()


    # return selection

def plot_lsb_vs_time(df, config):

    for gain in config['tdc_injected'][0]:
        for ch in set(config['injected_channel'][0]):
            plot_lsb_vs_time_for_one_ch(df, ch, gain, config)

def plot_Gaussian(fitParam, mean):

    return CTR_FWHM_ps

def plot_Gaussian_exp(fitParam2, mean):
    method = 'Gaussian-exp'
    mu = fitParam2[0]
    sigma = fitParam2[1]
    amp = fitParam2[2]
    lambd = fitParam2[3]
    xmin = mean - 20 * sigma
    xmax = mean + 20 * sigma
    xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
    yfit = modelGaussExp(xfit, mu, sigma, amp, lambd)

    r1, r2, resolution_FWHM = half_max_x(xfit, yfit)

    plt.plot(xfit, yfit, linestyle='--', color='blue',
             label=r'Gaussian-Exp : CTR = %.0f ps FWHM' % (resolution_FWHM * 1e3) + "\nMean : %.3f ns" % mu)
    plt.legend()

def plot_CTR(df, config, channelA, boardA, channelB, boardB, time_conversion_method,
             gainA='low', gainB='low', fit_with_GaussExp=False):

    ch_suffixA = '_%s_ch%d_B%d' % (gainA, channelA, boardA)
    ch_suffixB = '_%s_ch%d_B%d' % (gainB, channelB, boardB)
    # tdc_good_selection = (df['tdc_data_valid' + ch_suffixA] == 1) & (df['tdc_data_valid' + ch_suffixB] == 1) & (~df['error'+ch_suffixA]) & (~df['error'+ch_suffixB])
    tdc_good_selection = df['tdc_good' + ch_suffixA] & df['tdc_good' + ch_suffixB]

    if sum(tdc_good_selection) != len(df):
        print("valid tdc_good_selection")
        print(tdc_good_selection.value_counts())

    # suffixA = '_low_ch%d_B%d' % (channelA, 1)
    # suffixB = '_low_ch%d_B%d' % (channelB, 2)
    # # print(df.loc[tdc_good_selection, param].describe())
    # plt.hist(df.loc[~tdc_good_selection, param], label=param + ' good')
    # plt.hist(df.loc[tdc_good_selection, param], label=param + ' erronous')
    # plt.legend()
    # plt.xlabel(suffixA)
    # plt.ylabel(suffixB)
    # plt.grid()
    # plt.show()

    # for param in ['cpt', 'toa', 'cal', 'TOAcoarse']:
    #     plt.figure()
    #     plt.title(param)
    #     suffixA = '_low_ch%d_B%d' % (channelA, 1)
    #     suffixB = '_low_ch%d_B%d' % (channelB, 2)
    #     # print(df.loc[tdc_good_selection, param].describe())
    #
    #     plt.scatter(df.loc[~non_null_photopeak_selection, param+suffixA], df.loc[~non_null_photopeak_selection, param+suffixB], label=param+' good')
    #     plt.scatter(df.loc[non_null_photopeak_selection, param+suffixA], df.loc[non_null_photopeak_selection, param+suffixB], label=param+' erronous')
    #     plt.legend()
    #     plt.xlabel(suffixA)
    #     plt.ylabel(suffixB)
    #     plt.grid()
    #     plt.show()

    # time_selection = (df['dt']> 3) & (df['dt']<7)
    #& (df['dt'] < 23) & (df['dt'] > 19)

    # dt = df.loc[tdc_good_selection, 'dt_CPT']
    # dt = df.loc[tdc_good_selection, 'dt_cpt']

    # missing_one_msb_cpt = df.loc[df['photopeak'] & non_null_selection , 'dt_cpt'] < 0
    # dt += (missing_one_msb_cpt * 16 * 12.5) # ns

    # dt = df.loc[df['photopeak'] & non_null_selection & time_selection , 'dt']

    output_folder = config['output_folder'] + '/CTR/dt/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)



    # plt.figure()
    # clusterA = channelA//16
    # clusterB = channelB//16
    # df['CPT_6b_A'] = np.bitwise_and(df['CPT_cluster%d_B%d'%(clusterA, boardA)], 0b111111)
    # df['CPT_6b_B'] = np.bitwise_and(df['CPT_cluster%d_B%d'%(clusterB, boardB)], 0b111111)
    # # df['CPT_14b'] = np.bitwise_and(df.CPT, 0b11_1111_1111_1111)
    # # df['CPT_6b'].apply(lambda row: hex(row + (1 << 6)))
    # # df['CPT_14b'].apply(lambda row: hex(row))
    #
    # dt = df.loc[:, 'toa_ps' + ch_suffixA] - df.loc[:, 'toa_ps' + ch_suffixB]
    #
    # step = 10
    # bins = np.arange(dt.min(), dt.max() + step, step)  # lsb
    # counts, bins = np.histogram(dt, bins=bins)
    # dt_highest_index = np.argmax(counts)
    # dt_highest_count = bins[dt_highest_index]
    # dt_second_highest_count = bins[np.argmax(np.delete(counts, dt_highest_index))]
    # dt_threshold = (dt_highest_count + dt_second_highest_count)/2
    #
    #
    # col_related_to_studied_channels = ([meas+ch_suffix for meas in ['toa'] for ch_suffix in [ch_suffixA, ch_suffixB]] + ['CPT_6b_A', 'CPT_6b_B'])
    # a = df.loc[(dt<dt_threshold) & tdc_good_selection, col_related_to_studied_channels]
    # b = df.loc[(dt>dt_threshold) & tdc_good_selection, col_related_to_studied_channels]
    # bins = np.arange(40,140, 1)
    # countsA, binsA = np.histogram(df.loc[(dt<dt_threshold) & tdc_good_selection, 'toa'+ch_suffixA].values, bins=bins)
    # countsB, binsB = np.histogram(df.loc[(dt<dt_threshold) & tdc_good_selection, 'toa'+ch_suffixB].values, bins=bins)
    # binsA = binsA[:-1][countsA<20]
    # binsB = binsB[:-1][countsB<20]
    #
    # # selection_cpt_6b = ((df.CPT_6b_A == df['cpt' + ch_suffixA]) & (df.CPT_6b_B == df['cpt' + ch_suffixB]))
    # # selection_cpt_6b = ((df['toa' + ch_suffixA].isin(itertools.chain(range(60, 70), range(95, 110))))
    # #                     & (df['toa' + ch_suffixB].isin(itertools.chain(range(70, 90), range(110, 120)))))
    #
    # plt.bar(binsA, [1]*len(binsA), label='A')
    # plt.bar(binsB, [1]*len(binsB), label='B')
    # plt.grid()
    # plt.legend()
    # plt.savefig(output_folder+ ch_suffixA+ch_suffixB+'tdc_toa_bin.png')
    # plt.close()




    # plt.figure()
    # plt.axvline(dt_highest_count)
    # plt.axvline(dt_second_highest_count)
    # plt.axvline(dt_threshold)
    # selection_cpt_6b = ((df['toa' + ch_suffixA].isin(binsA))
    #                     & (df['toa' + ch_suffixB].isin(binsB)))
    #
    # # not relevant selection :
    # # selection_cpt_6b = (df.cpt_low_ch6_B1 - df.cpt_low_ch6_B2)==0
    # # selection_cpt_6b = (df.CPT_6b_B == df['cpt' + ch_suffixB])
    # # selection_cpt_6b = (df.CPT_6b_A == df['cpt' + ch_suffixA])
    # # selection_cpt_6b = df.CPT_6b_A == df.CPT_6b_B
    # print("selection_cpt_6b")
    # print(selection_cpt_6b.value_counts())
    # # dt_cpt = df.loc[selection_cpt_6b, 'dt'] - df.loc[selection_cpt_6b, 'dt']
    # # dt_cpt2 = df.loc[~selection_cpt_6b, 'dt'] - df.loc[~selection_cpt_6b, 'dt']
    # # plt.hist([dt_cpt, dt_cpt2], label=['sel', "not "])
    #
    # selection = tdc_good_selection&selection_cpt_6b
    # event_count = sum(selection)
    # dt = df.loc[selection, 'dt']
    # step = 30
    # # dt = df.loc[tdc_good_selection, 'toa_ps' + ch_suffixA] - df.loc[tdc_good_selection, 'toa_ps' + ch_suffixB]
    # bins = np.arange(dt.min(), dt.max() + step, step)  # lsb
    # counts, bins = np.histogram(dt, bins=bins)
    # plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True, label='std %d ps %d %% events'%(np.std(dt), event_count/len(df)*100))
    #
    # not_selection = tdc_good_selection&~selection_cpt_6b
    # event_count = sum(not_selection)
    # col_related_to_studied_channels = ([col for col in df.columns if ch_suffixA in col or ch_suffixB in col]+['CPT_6b_A', 'CPT_6b_B'])
    # # +['CPT_cluster%d_B%d'%(channelA//16, boardA), 'CPT_cluster%d_B%d'%(channelB//16, boardB)])
    # a = df.loc[selection, col_related_to_studied_channels]
    # b = df.loc[not_selection, col_related_to_studied_channels]
    #
    #
    #
    # col_related_to_studied_channels = ([meas+ch_suffix for meas in ['cpt'] for ch_suffix in [ch_suffixA, ch_suffixB]] + ['CPT_6b_A', 'CPT_6b_B'])
    # a = df.loc[(df.dt<750) & tdc_good_selection, col_related_to_studied_channels]
    # b = df.loc[(df.dt>750) & tdc_good_selection, col_related_to_studied_channels]
    #
    # # aA = df.loc[df.dt < 700, 'tdc' + ch_suffixA].apply(lambda tdc_value: get_toa_cal_from_tdc(tdc_value))
    # # aB = df.loc[df.dt < 700, 'tdc' + ch_suffixB].apply(lambda tdc_value: get_toa_cal_from_tdc(tdc_value))
    # # a = pd.concat([aA, aB], axis=1)
    # # b = pd.concat([df.loc[df.dt < 700, 'tdc' + ch_suffixA].apply(lambda tdc_value: get_toa_cal_from_tdc(tdc_value)),
    # #                df.loc[df.dt < 700, 'tdc' + ch_suffixB].apply(lambda tdc_value: get_toa_cal_from_tdc(tdc_value))],
    # #               axis=1)
    #
    # dt = df.loc[not_selection, 'dt']
    # bins = np.arange(dt.min(), dt.max() + step, step)  # lsb
    # counts, bins = np.histogram(dt, bins=bins)
    # plt.hist(bins[:-1], bins, weights=counts, align='left', fill=False, label='NOT std %d ps %d %% events'%(np.std(dt), event_count/len(df)*100))
    # plt.xlabel('dt [ps] '+ch_suffixA+ch_suffixB)
    # plt.legend()
    # plt.grid()
    # plt.savefig(output_folder+ ch_suffixA+ch_suffixB+'_dt.png')
    #
    # # plt.show()
    # plt.close()


    plt.figure()
    plt.title('time_conversion_method: '+ time_conversion_method)
    plt.annotate("B%d\nCh %d\n%s" % (boardA, channelA, gainA), xy=(0.4, 0.65), xycoords='axes fraction')
    plt.annotate("B%d\n   %d\n%s" % (boardB, channelB, gainB), xy=(0.65, 0.65), xycoords='axes fraction',
                 horizontalalignment='right')

    step = 30 # ps
    dt = df.loc[tdc_good_selection, 'dt'+ch_suffixA+ch_suffixB]
    # first 100 values are nan because of rolling average for computing the lsb
    # a = df.loc[dt<0, col_related_to_studied_channels]
    # print(df.loc[dt<0, 'tdc'+ch_suffixA].apply(lambda row: bin(row)))
    # print(df.loc[dt<0, 'toa'+ch_suffixA].apply(lambda row: bin(row)))
    # print(df.loc[dt<0, 'tdc'+ch_suffixA].apply(lambda tdc_value: get_toa_cal_from_tdc(tdc_value)))
    # print(df.loc[dt>0, 'tdc'+ch_suffixA].apply(lambda tdc_value: get_toa_cal_from_tdc(tdc_value)))

    bins = np.arange(dt.min(), dt.max()+step, step)  # lsb
    counts, bins = np.histogram(dt, bins=bins)
    # plt.stairs(counts, bins, fill=True, label='dt' + ch_suffixA + ch_suffixB)
    plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True)
    plt.grid()

    plt.xlabel('dt [ps]' + ch_suffixA + ch_suffixB)
    plt.yscale('log')
    plt.tight_layout()
    plt.savefig(output_folder+ "CTR"+ch_suffixA+ch_suffixB+'_'+time_conversion_method+'.png')
    plt.show()
    plt.close()

    plt.figure()
    plt.annotate("B%d\nCh %d\n%s"%(boardA, channelA, gainA), xy=(0.1, 0.65), xycoords='axes fraction')
    plt.annotate("B%d\n   %d\n%s"%(boardB, channelB, gainB), xy=(0.25, 0.65), xycoords='axes fraction', horizontalalignment='right')
    plt.title('time_conversion_method: '+ time_conversion_method)
    mean_delta_TOA = bins[np.argmax(counts)]
    time_selection = ((df['dt'+ch_suffixA+ch_suffixB] > (mean_delta_TOA - 500))
                      & (df['dt'+ch_suffixA+ch_suffixB] < (mean_delta_TOA + 500)))
    outliers_count = sum(tdc_good_selection & ~time_selection)
    dt = df.loc[tdc_good_selection & time_selection, 'dt'+ch_suffixA+ch_suffixB]
    step = 30 # ps   0.03 # ns
    bins = np.arange(dt.min(), dt.max() + step, step)
    if len(bins) == 0:
        pass
    counts, bins = np.histogram(dt, bins=bins)
    mean_delta_TOA = (bins[np.argmax(counts)] + bins[np.argmax(counts)+1])/2
    plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True)
    plt.xlabel('dt' + ch_suffixA + ch_suffixB+ ' [ns] (%d ps binning)'%step)
    CTR_FWHM_ps_Gaussian = CTR_FWHM_ps_std = 0
    try:
        # GAUSSIAN
        if (channelA == 20) & (channelB == 43) & (boardA == 1) & (boardB == 1):
            pass
        if len(bins) >= 4:
            p0 = [mean_delta_TOA, 20, max(counts)]

            fitParam, cov = curve_fit(modelGauss, bins[:-1], counts, p0=p0)
            # perr = np.sqrt(np.diag(cov))

            method = 'Gaussian'
            mu = fitParam[0]
            sigmaHisto = fitParam[1]
            ampHisto = fitParam[2]
            xmin = mean_delta_TOA - 5 * sigmaHisto
            xmax = mean_delta_TOA + 5 * sigmaHisto
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGauss(xfit, mu, sigmaHisto, ampHisto)

            # resolution_FWHM2 = 2.35 * sigmaHisto * 1e3
            r1, r2, resolution_FWHM = half_max_x(xfit, yfit)
            CTR_FWHM_ps_Gaussian = resolution_FWHM

            plt.plot(xfit, yfit, linestyle='-', color='red',
                     label=r'Gaussian : CTR = %.0f ps FWHM' % CTR_FWHM_ps_Gaussian + "\nMean : %.0f ps" % mu
                     +'\nOutliers: %d (%d %%)'%(outliers_count,outliers_count/sum(tdc_good_selection)*100))
            plt.legend()

        # GAUSSIAN-EXP
        if fit_with_GaussExp:
            if len(bins) >= 5:
                p0 = [mean_delta_TOA, 0.1, max(counts) / 2.718, 5]
                fitParam2, cov2 = curve_fit(modelGaussExp, bins[:-1], counts, p0=p0)  # , full_output=True)
                perr2 = np.sqrt(np.diag(cov2))
                plot_Gaussian_exp(fitParam2, mean_delta_TOA)

        # if (len(bins) >= 5):
        #     if perr[1] < perr2[1]:  # GAUSSIAN is better
        #         plot_Gaussian(fitParam)
        #     else:  # GAUSSIAN-EXP is better
        #         plot_Gaussian_exp(fitParam2)
        # elif (len(bins) >= 4):
        #     plot_Gaussian(fitParam)

        # print(p0, *fitParam2)
    except (RuntimeError, OptimizeWarning) as e:
        print("Fail to fit")
        print(e)
        CTR_FWHM_ps_std = np.std(dt)
        plt.legend(['Std : %.1f ps RMS\nMean : %.0f ps' % (CTR_FWHM_ps_std, mean_delta_TOA)])

    if len(bins) < 4:
        CTR_FWHM_ps_std = np.std(dt)
        plt.legend(['Std : %.1f ps RMS\nMean : %.0f ps' % (CTR_FWHM_ps_std, mean_delta_TOA)])

    plt.grid()
    plt.tight_layout()
    plt.savefig(output_folder + "CTR"+ch_suffixA+ch_suffixB+'_'+time_conversion_method+'_zoom.png')
    # plt.show()
    plt.close()
    return CTR_FWHM_ps_std, CTR_FWHM_ps_Gaussian

def compute_bin_width_study_width_delta(df, config, plot=True):
    rangeTDCtoa_ps = config['rangeTDCtoa_ps']
    calib_dict_per_tdc = {'channel':[], 'gain':[], 'toa': [], 'cal': [], 'delta':[], 'bin_width': [], 'calibrated_toa_range_fraction': [], 'calibrated_time': []}
    #'delta_calib': [],

    output_folder = config['output_folder'] + '/bin_width/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    toa_tdc_stats = {'channel': [],
                     'gain': [],
                     'tdc_data_valid_fraction': [],
                     'calib_lsb_ps': [],
                     'TOA_DR_lsb':[]}

    channel_stats_filename = config['toa_stats_filepath']
    calib_table_filename = config['output_folder'] + '/B%d_toa_DNL_TOA_CAL_calib_table.csv'%config['board'][0]
    for channel in [43]: #config['enable_TL_ASIC_ch'][0]:
        for gain in config['tdc_injected'][0]:

            channel_suffix = '_%s_ch%d'%(gain, channel)
            print(channel_suffix)

            tdc_has_triggered_selection = (df['tdc_data_valid'+channel_suffix] != 0)
            tdc_has_triggered_fraction = tdc_has_triggered_selection.value_counts()[
                                             tdc_has_triggered_selection.value_counts().index == True].values / len(df)
            tdc_has_triggered_fraction = tdc_has_triggered_fraction[0] if tdc_has_triggered_fraction.size > 0 else 0
            subset = df[df['tdc_data_valid'+channel_suffix]]
            subplot = False
            delta_list = np.unique(subset['delta' + channel_suffix])

            if subplot:
                plt.subplots(len(delta_list), 1, figsize=(15, 7), sharex=True)
            else:
                plt.figure(figsize=(15, 7))

            all = True
            if all:

                for di, delta in enumerate(delta_list):

                    delta_subset = subset.loc[subset['delta'+channel_suffix] == delta, :]
                    # label = 'TOAfine'
                    # label = 'CALfine'
                    # label = 'TOAcoarse'
                    label = 'toa'
                    # label = 'cal'
                    bins = np.unique(delta_subset[label+channel_suffix]) # maybe has missing codes thus take min max to recreate bining
                    totalCounts = len(delta_subset[label+channel_suffix])
                    counts, bins_edges = np.histogram(delta_subset[label+channel_suffix], bins=np.arange(min(bins), max(bins) + 2, 1))
                    # binedges = 0.5 * (bins[1:] + bins[:-1]

                    lsb_target = delta_subset['lsb_fromCAL'+channel_suffix].mean()*1e3
                    TOA_DR = len(np.unique(delta_subset[label+channel_suffix])) * lsb_target
                    # TOA_DR = rangeTDCtoa_ps
                    binWidth = counts / totalCounts * TOA_DR
                    # yerr = binWidth / (counts ** 0.5)
                    toa_bins = bins_edges[:-1]
                    integral_iMinus1 = np.cumsum(binWidth)
                    calibrated_time = integral_iMinus1 - binWidth / 2
                    fractions = counts / totalCounts
                    # offset = min(bins)*fit_lsb
                    calibrated_fraction = np.cumsum(fractions) - fractions / 2

                    calib_dict_per_tdc['channel'] += [channel] * len(binWidth)
                    calib_dict_per_tdc['gain'] += [gain] * len(binWidth)
                    calib_dict_per_tdc['toa'] += list(toa_bins)
                    calib_dict_per_tdc['cal'] += [0] * len(binWidth)
                    calib_dict_per_tdc['delta'] += [delta] * len(binWidth)
                    calib_dict_per_tdc['bin_width'] += list(binWidth)
                    calib_dict_per_tdc['calibrated_toa_range_fraction'] += calibrated_fraction.tolist()
                    calib_dict_per_tdc['calibrated_time'] += (calibrated_time / 1e3).tolist()
                    # calib_dict_per_tdc['cumulated_bin_width'] += list(integral_iMinus1)

                    # if plot:
                    #     if subplot:
                    #         plt.subplot(len(delta_list), 1, di+1)
                    #         plt.bar(toa_bins, binWidth, width=1, yerr=yerr,
                    #                 color=plt.rcParams['axes.prop_cycle'].by_key()['color'][0], label='delta %d' % delta)
                    #     else:
                    #         plt.errorbar(toa_bins, binWidth, yerr=yerr, label='delta %d' % delta, ls='none', fmt='o')
                    #
                    #     # plt.scatter(toa_bins, binWidth, label='delta %d' % delta)
                    #     # plt.scatter(delta_subset['toa' + channel_suffix], delta_subset['cal' + channel_suffix], label='delta %d' % delta)
                    #     plt.xlabel('%s bin [lsb]'%label)

                calib_lsb_avg = subset['lsb_fromCAL'+channel_suffix].mean()*1e3



                # a = subset[['toa' + channel_suffix, 'cal' + channel_suffix]].groupby(
                #     ['toa' + channel_suffix, 'cal' + channel_suffix], as_index=False).size()
                # totalCounts = len(subset['toa' + channel_suffix])
                # counts = a['size']
                # toa_bins = a['toa' + channel_suffix]
                # cal_bins = a['cal' + channel_suffix]
                # # a['ratio'] = a['size'] / a.groupby('toa' + channel_suffix)['size'].transform('sum')
                # TOA_DR_lsb = len(np.unique(subset['toa'+channel_suffix]))
                # TOA_DR_ps = TOA_DR_lsb * calib_lsb_avg
                # # TOA_DR should be equal to the clock period
                # offset = TOA_DR_ps / 2
                # binWidth = counts / totalCounts * TOA_DR_ps
                # yerr = binWidth / (counts ** 0.5)
                # calibrated_time = np.cumsum(binWidth) - binWidth / 2 + offset
                # bins_edges = np.arange(0, len(binWidth)+1, 1)
                # fractions = counts / totalCounts
                # calibrated_fraction = np.cumsum(fractions) - fractions / 2
                #
                # calib_dict_per_tdc['channel'] += [channel] * len(binWidth)
                # calib_dict_per_tdc['gain'] += [gain] * len(binWidth)
                # calib_dict_per_tdc['toa'] += list(toa_bins)
                # calib_dict_per_tdc['cal'] += list(cal_bins)
                # calib_dict_per_tdc['bin_width'] += list(binWidth)
                # calib_dict_per_tdc['calibrated_toa_range_fraction'] += calibrated_fraction.tolist()
                # calib_dict_per_tdc['calibrated_time'] += (calibrated_time / 1e3).tolist()


                # (!) this TDC has a variable dynamic range, moving with temperature, voltage
                # and do not start at 0 but around 80 up to 140


                # if plot:
                #     plt.bar(bins_edges[:-1], binWidth, width=1, yerr=yerr, color=plt.rcParams['axes.prop_cycle'].by_key()['color'][0],
                #        label='#%d events   bin width : mean from toa = %.2f ps    from cal = %.2f ps    std(bin width)_tdc = %.1f ps  '
                #              'mean(std(bin width)_bin)_tdc = %.1f ps '%
                #              (totalCounts,  np.mean(binWidth), calib_lsb_avg, np.std(binWidth), np.nanmean(yerr)))
                #             #   mean from non-zero toa = %.2f ps        np.mean(subset.bin_width[np.nonzero(subset.bin_width)])
                #     plt.ylabel('Bin width [ps]')
                #     plt.grid()
                #     plt.legend()

            else:
                totalCounts = len(subset['TOAfine' + channel_suffix])

                TOAcoarse_list = np.sort(np.unique(subset['TOAcoarse'+channel_suffix]))
                plt.subplots(len(TOAcoarse_list)//2+1, 2, figsize=(15, 7), sharex=True)
                # plt.subplots(1, 2, figsize=(15, 7), sharex=True)
                # plt.figure(figsize=(15, 7))
                colors = plt.cm.jet(np.linspace(0, 1, len(TOAcoarse_list)))
                # ax.set_prop_cycle(rcsetup.cycler('color', plt.cm.jet(idx)))
                # colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
                # hatches = ['--', '+', 'x', '\\', '*', 'o', 'O', '.', '//', '\\/...', 'b']

                for i, TOAcoarse in enumerate(TOAcoarse_list):
                    plt.subplot(len(TOAcoarse_list)//2+1, 2, (i//2)*2+(i%2)+1)
                    # plt.subplot(1, 2, (i%2)+1)
                    plt.title(TOAcoarse)
                    counts, bins_edges = np.histogram(subset.loc[subset['TOAcoarse'+channel_suffix]==TOAcoarse, 'TOAfine' + channel_suffix],
                                                      bins=np.arange(0, 32, 1))
                    # binedges = 0.5 * (bins[1:] + bins[:-1])
                    binWidth = counts * rangeTDCtoa_ps / totalCounts
                    yerr = binWidth / (counts ** 0.5)

                    average_lsb = subset.loc[subset['TOAcoarse'+channel_suffix]==TOAcoarse, 'lsb_fromCAL' + channel_suffix].mean()

                    # plt.hist(bins_edges[:-1], bins_edges, weights=binWidth, align='left', color=colors[i], hatch=hatches[i]) #, fill=True, alpha=0.5)

                    plt.bar(bins_edges[:-1], binWidth, width=1, yerr=yerr,
                            color=colors[0],
                            label='#%d events   bin width : mean from toa = %.2f ps    from cal = %.2f ps    std(bin width)_tdc = %.1f ps  '
                                  'mean(std(bin width)_bin)_tdc = %.1f ps ' %
                                  (totalCounts, np.mean(binWidth), average_lsb, np.std(binWidth), np.nanmean(yerr)))
                    plt.grid()
                    plt.tight_layout()



            # toa_tdc_stats['channel'].append(channel)
            # toa_tdc_stats['gain'].append(gain)
            # toa_tdc_stats['tdc_data_valid_fraction'].append(tdc_has_triggered_fraction)
            # toa_tdc_stats['calib_lsb_ps'].append(calib_lsb_avg)
            # toa_tdc_stats['TOA_DR_lsb'].append(TOA_DR_lsb)

            # tdc_CAL_df = pd.DataFrame(toa_tdc_stats)
            # tdc_CAL_df.to_csv(channel_stats_filename, index=None)

            calib_table = pd.DataFrame(calib_dict_per_tdc)
            calib_table.to_csv(calib_table_filename, index=None)

            plot_horizontal_bin_width = False
            if plot_horizontal_bin_width:
                a = pd.pivot_table(calib_table, index='toa', columns='delta', values='bin_width').T.fillna(0.0).to_dict('list')
                bottom = np.zeros(len(delta_list))
                for delta, bin_width_for_each_toa_code in a.items():
                    plt.barh(tuple(delta_list), bin_width_for_each_toa_code, left=bottom)
                    bottom += bin_width_for_each_toa_code
                plt.xlabel('Bin width [ps]')
                plt.show()
                pass

            # if plot:
            #     plt.suptitle('Channel %d %s TDC TOA bin widths - Code density test assuming a dynamic range of %d ps  ' % (
            #         channel, gain, 0)) # TOA_DR_ps))
            #     plt.tight_layout()
            #     plt.ylabel('Bin width [ps]')
            #     plt.grid()
            #     plt.legend()
            #     plt.savefig(output_folder + 'ch%d_%s_bin_width.png' % (channel, gain))
            #     plt.show()
            #     plt.close()

            # cut = 64
            # binWidth = binWidth[np.nonzero(binWidth)]
            # ax.axhline(y=np.mean(binWidth[0:cut]), xmin=0, xmax=cut / 127,
            #            label='first part : mean bin width = %.1f ps ' % (np.mean(binWidth[0:cut])), color='red')
            # ax.axhline(y=np.mean(binWidth[cut + 1:127]), xmin=(cut + 1) / 127, xmax=1,
            #            label='second part : mean bin width = %.1f ps ' % (np.mean(binWidth[cut + 1:127])), color='orange')


    # PLOT tdc_has_triggered_fraction
    plt.plot(tdc_CAL_df.channel, tdc_CAL_df.tdc_data_valid_fraction,
             label='tdc_data_valid_fraction')
    plt.legend()
    plt.grid()
    plt.xlabel('Channel')
    plt.title('Fraction of TDC data exploitable')
    plt.tight_layout()
    plt.savefig(config['output_folder'] + 'tdc_data_valid_fraction_per_channel.png')
    # plt.show()
    plt.close()

def compute_non_linearities(config, plot=True):

    output_folder = config['output_folder'] + '/NL_per_channel/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    channel_stats_filename = config['output_folder'] + '/tdc_NL_stats_per_channel.csv'

    if os.path.exists(channel_stats_filename):#'fit_lsb_ps' in tdc_CAL_df0.columns:
        print("Skipping compute_non_linearities() : already existing results !")
        return
    else:
        print("compute_non_linearities")

    # calib_table_filename = config['output_folder'] + '/B%d_toa_DNL_TOA_CAL_calib_table.csv'% board
    calib_table_filename = config['output_folder'] + '/tdc_DNL_TOA_calib_table.csv'
    calib_table = pd.read_csv(calib_table_filename)

    toa_tdc_stats = {'board':[],
                     'channel': [],
                     'gain': [],
                     'fit_lsb_ps': [],
                     'fit_offset_ps':[]}

    toa_tdc_stats.update(
        {'%s_%s_%s' % (meas, typeMeas, unit): [] for meas in ['INL', 'DNL'] for typeMeas in
         ['RMS', 'MIN', 'MAX'] for
         unit in ['ps', 'lsb']})

    channel_suffix_list = get_suffix_list_from_calib_file(calib_table)

    for channel_suffix in channel_suffix_list.iterrows():

        board = channel_suffix[1].board
        channel = channel_suffix[1].channel
        gain = channel_suffix[1].gain

        subset = calib_table[(calib_table.channel==channel) & (calib_table.gain==gain)]
        toa_bins = subset['toa']
        calibrated_time = subset['calibrated_time']*1e3
        bin_width = subset['bin_width']
        if len(calibrated_time) == 0:
            print(channel_suffix)
            pass
        fitParam, cov = opt.curve_fit(modelFitLinear, toa_bins, calibrated_time)
        lsb = fitParam[0]
        delayOffset = fitParam[1]
        # delayOffset = rangeTDCtoa_ps/2

        # calibrated_time += delayOffset
        yfit = modelFitLinear(toa_bins, *fitParam)
        # yfit = modelFitLinear(toa_bins, *fitParam)+delayOffset

        # label="offset=%.0f lsb: fit=%.2f cal=any #null tdc = %.2f %%" % (delayOffset, lsb, null_tdc_field_fraction*100)
        # else:
        start_step = calibrated_time - bin_width / 2
        stop_step = calibrated_time + bin_width / 2
        # step = start_step+stop_step
        # step[::2] = start_step
        # step[1::2] = stop_step
        # step = np.array(step)
        step = np.array(list(itertools.chain(*zip(start_step, stop_step))))
        toa_bins_interlaced = np.array(list(itertools.chain(*zip(toa_bins, toa_bins))))

        if plot:
            plt.subplots(1, 3, figsize=(18, 11))
            label = "offset=%.0f ps  lsb: fit=%.2f ps cal=any" % (delayOffset, lsb)
            plt.subplot(1, 3, 1)
            ax = plt.plot(toa_bins_interlaced, step, label=label)
            plt.plot(toa_bins, yfit, linestyle='dashed', color='tab:orange') #ax[0].get_color())
            # plt.scatter(toa_bins, calibrated_time, color=ax[0].get_color())
            plt.xlabel("TOA [LSB]")
            plt.title("Reconstructed TDC characteristic")
            plt.ylabel("Time [ps]")
            plt.ylim([1500, 5000])
            plt.grid()
            plt.legend()


        DNL = (bin_width - lsb) / lsb
        # INL2 = np.cumsum(DNL)

        INL = (yfit - calibrated_time) / lsb
        # INLserieWithoutOutliers = INL.loc[(np.abs(stats.zscore(INL)) < 3)]
        # infINL.append(INLserieWithoutOutliers.min())
        # supINL.append(INLserieWithoutOutliers.max())

        if plot:
            plt.subplot(1, 3, 2)
            plt.plot(toa_bins, INL, marker='.',
                       label='INL RMS: {0:.1f} LSB = {1:.1f} ps'.format(np.std(INL), np.std(
                           INL) * lsb) + '\n min/max: {0:.1f}/{1:.1f} LSB = {2:.1f}/{3:.1f} ps'
                       .format(np.nanmin(INL), np.nanmax(INL), np.nanmin(INL) * lsb, np.nanmax(INL) * lsb))
            plt.ylabel("INL [LSB]")
            plt.title("Integral non-linearity")
            plt.xlabel("TOA [dacUnit]")
            plt.grid()
            plt.legend()

            plt.subplot(1, 3, 3)
            # ax3[2].plot(x, INL2, marker='.', label='INL2')
            # +'\n'+'Excluding |INL| > %d'%inl_cut)
            plt.plot(toa_bins, DNL, marker='.',
                       label='DNL RMS {0:.1f} LSB = {1:.1f} ps'.format(np.std(DNL), np.std(
                           DNL) * lsb) + '\n min/max: {0:.1f}/{1:.1f} LSB = {2:.1f}/{3:.1f} ps'
                       .format(np.nanmin(DNL), np.nanmax(DNL), np.nanmin(DNL) * lsb, np.nanmax(DNL) * lsb))

            plt.ylabel("DNL [LSB]")
            plt.title("Differential non-linearity")
            plt.xlabel("TOA [dacUnit]")
            plt.grid()
            plt.legend()

            plt.suptitle('Channel %d %s TOA TDC - Code density test' % (channel, gain))

            # mng = plt.get_current_fig_manager()
            # mng.full_screen_toggle()
            plt.tight_layout()

            plt.savefig(output_folder + '/ch%d_%s_non_linearities.png' % (channel, gain))
            # plt.show()
            plt.close()


        toa_tdc_stats['board'].append(board)
        toa_tdc_stats['channel'].append(channel)
        toa_tdc_stats['gain'].append(gain)
        toa_tdc_stats['fit_lsb_ps'].append(lsb)
        toa_tdc_stats['fit_offset_ps'].append(delayOffset)

        toa_tdc_stats['INL_RMS_ps'].append(np.std(INL)*lsb)
        toa_tdc_stats['INL_MIN_ps'].append(np.nanmin(INL)*lsb)
        toa_tdc_stats['INL_MAX_ps'].append(np.nanmax(INL)*lsb)

        toa_tdc_stats['INL_RMS_lsb'].append(np.std(INL))
        toa_tdc_stats['INL_MIN_lsb'].append(np.nanmin(INL))
        toa_tdc_stats['INL_MAX_lsb'].append(np.nanmax(INL))

        toa_tdc_stats['DNL_RMS_ps'].append(np.std(DNL) * lsb)
        toa_tdc_stats['DNL_MIN_ps'].append(np.nanmin(DNL) * lsb)
        toa_tdc_stats['DNL_MAX_ps'].append(np.nanmax(DNL) * lsb)

        toa_tdc_stats['DNL_RMS_lsb'].append(np.std(DNL))
        toa_tdc_stats['DNL_MIN_lsb'].append(np.nanmin(DNL))
        toa_tdc_stats['DNL_MAX_lsb'].append(np.nanmax(DNL))

    tdc_CAL_df = pd.DataFrame(toa_tdc_stats)
    # tdc_CAL_df0 = pd.read_csv(channel_stats_filename)
    # if os.path.exists(channel_stats_filename):
    #     tdc_CAL_df = tdc_CAL_df0.merge(tdc_CAL_df, how='outer', on=['board','channel', 'gain'])
    tdc_CAL_df.to_csv(channel_stats_filename, index=None)



    # histtype = 'step',
    # # Comparaison avec code density test
    # coef = (1 / 40e6 - 1 / (8 * 5000010)) * 1e12
    # files = glob.glob("firmware/ALTIROCx_PY_r3/output/TDCscan/allMatrixON_vdda_1v30_vdd_1v29/pixel_120/" + "timing_data_cDelay_1.csv")
    # for file in files:
    #     timingdf = pd.read_csv(file)
    #
    #     if len(timingdf) != 0:
    #         chattyPixels = (timingdf.pixel != 120).sum()
    #         print('\t', chattyPixels, ' events from other pixels than injected')
    #
    #         timingdf = timingdf.loc[:, ['timestamp', 'toa']]
    #
    #     try:
    #         middle = timingdf.index[timingdf.toa == 65][0]
    #         subsetLow = timingdf[:middle]
    #         start = subsetLow.loc[(subsetLow.toa == 127).rolling(3, center=True).sum() == 3].index[-1]
    #         timingdf = timingdf.drop(timingdf[:start + 10].index).reset_index()
    #         stop = timingdf.loc[(timingdf.toa == 127).rolling(5, center=True).sum() == 5].index[0]
    #         timingdf.drop(timingdf[stop:].index, inplace=True)
    #         timingdf.timestamp -= timingdf.timestamp.min()
    #         timingdf.timestamp *= coef  # = (16/40e6 - 2/16/5000100)*1e12
    #
    #         cDelay = int(re.findall("(?<=cDelay_)[0-9]+", file)[0])
    #         subset = timingdf[(timingdf.toa != 127) & (timingdf.toa != 0)]
    #         totalCounts = len(subset)
    #
    #
    #         ax.hist(subset.toa, weights=[rangeTDCtoa / totalCounts] * totalCounts, bins=np.arange(128), histtype = 'step', align='left', label='Fixed 0.8 ps delay step with %d events'%totalCounts, linewidth=1.5, color='tab:orange')

            # alternative plot
            # counts, bins = np.histogram(subset.toa, bins=np.arange(128))
            # binedges = 0.5 * (bins[1:] + bins[:-1])
            # binWidth = counts * rangeTDCtoa / totalCounts
            # ax.bar(binedges, binWidth, width=1, label='Code density (0.8 ps step) with %d events' % totalCounts, fill=False, edgecolor='tab:orange')

            # df_toaCode_mean = pd.pivot_table(subset, values='timestamp', index='toa', aggfunc="mean").reset_index()
            # ax.bar(df_toaCode_mean.toa, df_toaCode_mean.timestamp.diff(1), width=1, label='cDelay ' + str(cDelay), fill=False)
        #
        # except:
        #     print("Fail selecting events for file ", file)
        #



    # df_toaCode_mean = pd.pivot_table(timingdf, values='pulseDelay', index='toa', aggfunc="mean").reset_index()
    # df_toaCode_std = pd.pivot_table(timingdf, values='pulseDelay', index='toa', aggfunc="std").reset_index()
    # df_toaCode_count = pd.pivot_table(timingdf, values='pulseDelay', index='toa', aggfunc="count").reset_index()
    #
    # # ax[2].plot(df_toaCode_mean.toa, df_toaCode_mean.timestamp.diff(1))
    # ax[2].bar(df_toaCode_mean.toa, df_toaCode_mean.pulseDelay.diff(1), width=1)
    # ax[3].plot(df_toaCode_std.toa, df_toaCode_std.pulseDelay, label='Mean jitter = %.1f ps '%(np.mean(df_toaCode_std.pulseDelay)))
    #
    # ax[2].set_xlabel('TOA code [lsb]')
    # ax[2].set_ylabel('Mean bin width [ps]')
    # ax[2].set_title('')
    # ax[2].grid()
    #
    # ax[3].set_xlabel('TOA code [lsb]')
    # ax[3].set_ylabel('RMS [ps]')
    # ax[3].set_title("TDC jitter")
    # idealTDCJitter = lsb / (12 ** 0.5)
    # ax[3].axhline(y=idealTDCJitter, label='lsb/sqrt(12) = %.1f ps' % idealTDCJitter, linestyle='--', color='tab:red')
    # ax[3].legend()
    # ax[3].grid()
    #
    # for toa_code in [90, 93]:  # np.unique(timingdf.toa)
    #     counts, bins = np.histogram(timingdf[timingdf.toa == toa_code].pulseDelay, bins=100)
    #     ax[0].stairs(counts, bins, label="toa_code %d RMS : %.1f ps" % (
    #     toa_code, df_toaCode_std.pulseDelay[df_toaCode_std.toa == toa_code]))
    #     ax[1].axhline(y=toa_code, linestyle='--', color='tab:gray')
    #     ax[3].axvline(x=toa_code, linestyle='--', color='tab:gray')
    # ax[0].legend()
    # ax[0].set_xlabel('Time [ps]')
    # ax[0].set_ylabel('Count')
    # ax[0].set_title('Histogram for given codes')
    # ax[0].grid()
    #
    # ax[1].errorbar(df_toaCode_mean.pulseDelay, df_toaCode_mean.toa, xerr=df_toaCode_std.pulseDelay,
    #                ecolor='tab:red', label='RMS errorbar')
    # ax[1].set_xlabel('Time [ps]')
    # ax[1].set_ylabel('TOA [LSB]')
    # ax[1].set_title('TDC TOA linearity (zoom)')
    # ax[1].legend()
    # yrange = [48, 100]
    # ax[1].set_ylim(yrange)
    # ax[1].set_xlim((yrange-fitParam[1])/fitParam[0])
    # ax[1].grid()
    # plt.tight_layout()
    #
    # fig.savefig(rootFolder + "/tdc_toa_projection_time_axis.png")
    # # plt.show()
    # plt.close()
    #
    #
    #
    # fig, ax = plt.subplots(1, 1, figsize=(15, 7))
    # totalCounts = len(timingdf)
    # rangeTDCtoa = abs(lsb)*128
    #
    # counts = df_toaCode_count.toa
    # binWidth = df_toaCode_mean.pulseDelay.diff(1)
    # yerr=binWidth/(counts**0.5)
    # ax.bar(df_toaCode_mean.toa, binWidth, width=1, yerr=yerr, label='Time projection mean bin width = %.2f ps'%np.mean(binWidth)
    #                                                           +'measuring std(bin width)_TDC = %.1f ps   mean(std(bin width)_code i)_TDC = %.1f ps '%(np.std(binWidth), np.nanmean(yerr)))
    #
    # counts, bins = np.histogram(timingdf.toa, bins=np.arange(128))
    # bins = np.arange(-0.5,127.5,1)
    # binWidth = counts * rangeTDCtoa / totalCounts
    # ax.stairs(binWidth, bins,  linewidth=1.5, color='tab:orange', label='Bin projection')
    # # ax.hist(timingdf.toa, weights=[rangeTDCtoa / totalCounts] * totalCounts, bins=np.arange(128), histtype = 'step', align='left', label='Bin projection', linewidth=1.5, color='tab:orange')
    # ax.set_xlabel('TOA [LSB]')
    # ax.set_ylabel('Bin width [ps]')
    # ax.set_title('Fixed 10 ps delay step with %d events'%totalCounts+'\nTDC TOA mean bin width assuming a mean LSB of %.2f ps for a 7 bits TDC aka a dynamic range of %d ps'%(abs(lsb),rangeTDCtoa))
    # ax.set_ylim([-1, ax.get_ylim()[1]])
    # ax.grid()
    # plt.tight_layout()
    #
    #
    # binWidth = binWidth[np.nonzero(binWidth)]
    # cut=64
    # ax.axhline(y=np.mean(binWidth[0:cut]), xmin=0, xmax=cut / 127,
    #            label='first from time projection %.1f ps '%(np.mean(binWidth[0:cut])), color='red')
    # ax.axhline(y=np.mean(binWidth[cut+1:127]), xmin=(cut+1) / 127, xmax=1,
    #            label='second from time projection %.1f ps '%(np.mean(binWidth[cut+1:127])), color='orange')
    # ax.legend()
    # # binWidthCumulative = np.cumsum(binWidth)
    # # ax.bar(bins[:-1], binWidthCumulative, width=1, yerr=yerr, label='integral')
    #
    #
    # fig.savefig(rootFolder + "/toa_bin_width.png")
    # plt.show()
    #

def build_dataframe_from_clusters(folder):
    # MERGE data into 1 dataframe per cluster
    for cluster in range(4):
        filepath_list = glob.glob(folder + "/cluster_%d*.csv"%cluster)
        if filepath_list==0:
            print("No events for cluster %d"%cluster)
            break

        df = pd.DataFrame()

        for filepath in filepath_list:
            df_tmp = pd.read_csv(filepath)
            df_tmp['delay'] = int(re.findall("(?<=delay_)[0-9]+", filepath)[0])
            df_tmp['temp'] = int(re.findall("(?<=temp_)[0-9]+", filepath)[0])
            df_tmp['iter'] = df_tmp.index
            df = pd.concat([df, df_tmp])

        df.to_csv(folder+"/../data_cluster_%d.csv"%cluster)





def plot_tdc_linearity(df, config, output_folder, folder_suffix='', tvar='real_time_ns', row=2, col=['TOAcoarse', 'TOAfine', 'toa', 'CALcoarse', 'CALfine', 'delta'], src_file=''):

    if os.path.exists(output_folder+'calib_stats.csv'):
        calib_stats_df = pd.read_csv(output_folder+'calib_stats.csv')
        apply_filter = True
    else:
        apply_filter = False

    apply_filter = False

    modeRO_list = np.unique(df.modeRO)
    injected_channel_list = config['enable_TL_ASIC_ch']

    with alive_bar(len(modeRO_list) * len(injected_channel_list) * 2, force_tty=True) as bar:
        for mi, modeRO in enumerate(modeRO_list):
            modeRO_output_folder = output_folder + "linearity/%s_%s/" % (modeRO, folder_suffix)
            if not os.path.exists(modeRO_output_folder):
                os.makedirs(modeRO_output_folder)

            for channel in injected_channel_list:
                for channel_gain in ['high', 'low']:
                    bar()
                    cluster =  channel//16
                    cluster_channel = channel%16
                    ch_gain_suffix_at_cluster_level = '_%s_ch%d' % (channel_gain, cluster_channel)
                    mode_cluster_selection = (df.cluster == cluster) & (df.modeRO == modeRO)
                    matrix_channel = cluster * 16 + cluster_channel

                    # contains_null_coarse_values = (df.loc[mode_cluster_selection, 'TOAcoarse'+ch_gain_suffix_at_cluster_level]==0).all() | (df.loc[mode_cluster_selection, 'CALcoarse'+ch_gain_suffix_at_cluster_level]==0).all()
                    # if contains_null_coarse_values:
                    #     print('null values')
                    #     continue

                    # plt.figure(0, figsize=(10, 8))
                    plt.subplots(row, len(col)//row, sharex=True, figsize=(10, 8))

                    for i, field in enumerate(col):
                        plt.subplot(row, len(col)//row, i + 1)

                        if 0:
                            for correction in np.unique(df['overflown_TOA'+ch_gain_suffix_at_cluster_level]):
                                selection = mode_cluster_selection & (df['overflown_TOA'+ch_gain_suffix_at_cluster_level]==correction)
                                plt.scatter(df.loc[selection, tvar], df.loc[selection, field+ch_gain_suffix_at_cluster_level], label=str(correction), marker='x', linewidths=1)
                        else:
                            plt.scatter(df.loc[mode_cluster_selection, tvar],
                                        df.loc[mode_cluster_selection, field + ch_gain_suffix_at_cluster_level], marker='x', linewidths=1)

                        plt.title(field + " for channel %d" % matrix_channel)


                        # if folder_suffix=='fitted':
                        #     if field == 'delta':
                        #
                        #         plt.axhline(meanHisto, color='red', linestyle='solid', linewidth=1)
                        #         t0 = df.loc[good_tdc_selection, 'real_time_ns'].min()
                        #         plt.text(t0, meanHisto, "average lsb =  %.1f ps " % (6250 / meanHisto), color='red',
                        #                  path_effects=[pe.withStroke(linewidth=2, foreground="white")])
                        #
                        #         plt.axhline(xmin, color='red', linestyle='--', linewidth=1)
                        #         plt.axhline(xmax, color='red', linestyle='--', linewidth=1)
                        #
                        #         plt.text(t0, xmin, r"lsb +2$\sigma$ = %.0f ps" % (6250 / xmin), color='red',
                        #                  path_effects=[pe.withStroke(linewidth=2, foreground="white")])
                        #         plt.text(t0, xmax, r"lsb -2$\sigma$ = %.0f ps" % (6250 / xmax), color='red',
                        #                  path_effects=[pe.withStroke(linewidth=2, foreground="white")])
                        #
                        #     if field == 'toa':
                        #         time_selection = (df.loc[ROmode_selection, 'real_time_ns'] < 13) & good_tdc_selection
                        #
                        #         fitParam, cov = opt.curve_fit(modelFitLinear, df.loc[time_selection, 'real_time_ns'],
                        #                                       df.loc[time_selection, 'toa' + ch_gain_suffix_at_cluster_level])
                        #         # delayOffset = fitParam[1]
                        #         lsb = 1 / fitParam[0]
                        #
                        #         # df.loc[time_selection, 'toa_fit' + ch_gain_suffix_at_cluster_level]
                        #         yfit = modelFitLinear(df.loc[time_selection, 'real_time_ns'], *fitParam)
                        #         plt.plot(df.loc[time_selection, 'real_time_ns'], yfit,
                        #                  '--', linewidth=1, color='red',
                        #                  label='Fit : TDC lsb : %.1f ps' % (lsb * 1e3))
                        #
                        #         plt.legend()
                        plt.ylabel("[lsb]")
                        plt.grid()
                        if i > 3:
                            if tvar=='delay':
                                plt.xlabel('Delay code')
                            else:
                                plt.xlabel('Real time [ns]')

                    plt.suptitle("TDC linearity with a step of 10 ps (supposely) ")
                    plt.tight_layout()
                    plt.annotate(src_file, xy=(5, 7), xycoords='axes pixels')
                    plt.savefig(modeRO_output_folder + "ch%d_%s.png" % (matrix_channel, channel_gain))
                    plt.show()
                    plt.close()


def analyse_calib_lsb(df, config, plot=False):

    calib_stats = {'board':[],
                   'channel':[],
                   'gain':[],
                   'mean_delta':[],
                   'std_delta': [],
                   'median_delta': [],
                   'min_delta': [],
                   'max_delta': []
                   }

    local_output_folder = config['output_folder'] + '/calib_lsb_per_channel/'
    channel_stats_filename = config['output_folder'] + '/tdc_CAL_stats_per_channel.csv'

    # Let's forget about trying to fit distribution with only between 2 and 5 different values (delta, lsb_fromCAL)
    if not os.path.exists(local_output_folder):
        os.makedirs(local_output_folder)

    if os.path.exists(channel_stats_filename):
        stats_df = pd.read_csv(channel_stats_filename)
        if 'std_delta' in stats_df.columns:
            print("Skipping analyse_calib_lsb() : already existing results !")
            return
    print("Analysing calibration lsb ")

    channel_suffix_list = get_suffix_list_from_frames(df)

    for channel_suffix in channel_suffix_list:

        gain, channel, board = get_board_ch_gain_from_suffix(channel_suffix)

        board_config = config['config_B%d'%board]

        calib_stats['board'].append(board)
        calib_stats['channel'].append(channel)
        calib_stats['gain'].append(gain)

        non_null_delta_channel_selection = df['tdc_data_valid' + channel_suffix]
        delta = df.loc[non_null_delta_channel_selection, 'delta'+channel_suffix].values
        std_delta = np.std(delta)
        calib_stats['mean_delta'].append(np.mean(delta))
        calib_stats['std_delta'].append(std_delta)
        calib_stats['median_delta'].append(np.median(delta))
        calib_stats['min_delta'].append(np.min(delta))
        calib_stats['max_delta'].append(np.max(delta))

        if plot :
            plt.figure(figsize=(10, 8))
            plt.title('Delta')
            bin_step = 1  # lsb
            bins = np.arange(delta.min(), delta.max() + bin_step, bin_step)
            counts, bins = np.histogram(delta, bins=bins) #, density=True)

            plt.hist(bins[:-1], bins, align='left', edgecolor='white', linewidth=2, weights=counts,
                     label="Ch %d %s RMS = %.2f lsb" % (channel, gain, std_delta))
            rangeTDCtoa_ps = 1e6/board_config['tempo_dig_ck']
            plt.xlabel("TDC delta [lsb] = TOA-CAL = 2 * %d ps"%rangeTDCtoa_ps)
            plt.ylabel('Count')
            plt.grid()
            plt.yscale('log')
            plt.legend()
            plt.tight_layout()
            plt.savefig(local_output_folder + '/ch%d_%s_%s.png'%(channel, gain, 'delta'))
            # plt.show()
            plt.close()


    new_stats_df = pd.DataFrame(calib_stats)
    # new_stats_df.std_lsb_fromCAL = new_stats_df.std_lsb_fromCAL.abs()
    assert (new_stats_df.std_delta > 0).all(), "Negative std from delta from TDC calibration !"

    new_stats_df['mean_lsb_fromCAL'] = np.abs(2 * 3125 / new_stats_df['mean_delta'])
    new_stats_df['std_lsb_fromCAL'] = np.abs(2 * 3125 / (new_stats_df['mean_delta']**2) * new_stats_df['std_delta'])
    new_stats_df['median_lsb_fromCAL'] = np.abs(2 * 3125 / new_stats_df['median_delta'])
    new_stats_df['max_lsb_fromCAL'] = np.abs(2 * 3125 / new_stats_df['max_delta'])
    new_stats_df['min_lsb_fromCAL'] = np.abs(2 * 3125 / new_stats_df['min_delta'])

    if os.path.exists(channel_stats_filename):
        stats_df = pd.read_csv(channel_stats_filename).merge(new_stats_df, how='outer', on=['board', 'channel', 'gain'])
    else:
        stats_df = new_stats_df
    stats_df.to_csv(channel_stats_filename, index=False)

    return


def plot_lsb(calib_stats_df, output_folder):

    plt.figure(0, figsize=(10, 8))
    calib_stats_df = calib_stats_df.sort_values(by=['channel'])
    asic_col(calib_stats_df.loc[:, 'mean_lsb_fromCAL'])
    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(0.4, 0.01),
    #              xycoords='axes fraction')
    plt.title("TDC LSB")
    plt.savefig(output_folder + "tdc_lsb_map.png")
    plt.close()
    # plt.show()



def analyse_jitter(df, config, output_folder):
    injected_channel_list = config['enable_TL_ASIC_ch']

    # with alive_bar(len(injected_channel_list) * 2, force_tty=True) as bar:
    output_folder =  output_folder+'/jitter/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    jitter_res = {'channel':[],
                   'gain':[],
                    'max_jitter_toa_lsb':[],
                    'fraction_delay_in_one_toa_bin':[]
                  }
    if 1:
        for channel in injected_channel_list:
            for channel_gain in ['low', 'high']:
                # bar()
                cluster_channel = channel % 16
                cluster = channel // 16
                cluster_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)
                cluster_selection = df.cluster == cluster
                columns_to_apply = ['%s' % meas + cluster_suffix for meas in ['toa', 'cal', 'delta']]

                max_jitter_toa = 0
                fraction_delay_in_one_toa_bin = 0
                delay_count = 0
                for monotonic in np.unique(df.loc[cluster_selection, 'monotonic'+cluster_suffix]):
                    if monotonic==0:
                        continue
                    subset = df[cluster_selection & (df['monotonic'+cluster_suffix]==monotonic)]

                    df_jitter = pd.pivot_table(subset, values=columns_to_apply, index=['delay'], aggfunc=lambda x: np.std(x))
                    # df_count = pd.pivot_table(subset, values=columns_to_apply, index=['delay'], aggfunc='count')
                    df_unique_count = pd.pivot_table(subset, values=columns_to_apply, index=['delay'], aggfunc = lambda x: len(x.unique()))

                    fraction_delay_in_one_toa_bin += (df_unique_count[columns_to_apply[0]]==1).value_counts().iloc[0]
                    delay_count += len(df_unique_count)

                    i = 0 # toa
                    serie = df_jitter.loc[df_unique_count[columns_to_apply[i]]>=3, columns_to_apply[i]] # at least 3 differents bins to compute sdev
                    # max_jitter_toa += np.square(np.sum(np.square(serie), axis=0)/len(serie))
                    max_jitter_toa = max(max(serie), max_jitter_toa)

                    # for i, field in enumerate(columns_to_apply):
                    #     plt.subplot(1, 3, i+1)
                    #     # delay = subset.delay.iloc[0]
                    #     # plt.errorbar(df_jitter.index, df_jitter[field], yerr = df_jitter[field]/(np.sqrt(2*(df_count[field]-1))), label=field + ' RMS %.2f lsb'%df_jitter[field].std())
                    #     plt.scatter(df_jitter.index, df_jitter[field], label=field + ' RMS %.2f lsb'%df_jitter[field].std())
                    #     # plt.hist(subset.loc[subset.delay==delay, field], label=str(delay))
                    #
                    #
                    #     # serie = df_jitter.loc[:, field]
                    #     # if (serie==0).all():
                    #     #     continue
                    #     # selection = df_count[field]!=0
                    #     # plt.scatter(df_jitter[selection].index, serie[selection], label=field + ' RMS %.2f lsb'%serie.std())
                    #
                    #     plt.ylabel('Jitter [lsb]')
                    #     plt.xlabel('Delay [lsb]')
                    #     # plt.ylim([0, 1])
                    #     plt.grid()
                    #     plt.legend()
                    #     plt.title(field)

                    plt.figure(0, figsize=(15, 8))
                    df_jitter = pd.pivot_table(subset, values='real_time_ns', index=columns_to_apply[0], aggfunc=lambda x: np.std(x))
                    plt.scatter(df_jitter.index, df_jitter["real_time_ns"]*1e3, label='average %.1f ps' % (df_jitter["real_time_ns"].mean()*1e3))


                    pass
                fraction_delay_in_one_toa_bin /= delay_count
                jitter_res['fraction_delay_in_one_toa_bin'].append(fraction_delay_in_one_toa_bin)
                jitter_res['max_jitter_toa_lsb'].append(max_jitter_toa)
                jitter_res['channel'].append(channel)
                jitter_res['gain'].append(channel_gain)

                plt.figure(0, figsize=(15, 8))
                pulser_jitter = 12
                plt.axhline(pulser_jitter, color='tab:red', linestyle='--', label="%d ps : jitter envelope between probed latched trigger vs external pulser" % pulser_jitter)
                plt.ylabel('Jitter [ps]')
                plt.xlabel('TOA [lsb]')
                plt.title('TOA jitter for ch %d %s'%(channel, channel_gain))
                plt.grid()
                plt.legend()
                plt.tight_layout()
                plt.savefig(output_folder + 'jitter_ch%d_%s.png'%(channel, channel_gain))
                plt.close()

                plt.figure(1, figsize=(15, 8))
                df_unique_count = pd.pivot_table(df, values=columns_to_apply, index=['delay'], aggfunc=lambda x: len(x.unique()))
                for i, field in enumerate(columns_to_apply):
                    plt.subplot(1, 3, i + 1)
                    if i==0: # toa
                        plt.hist(df_unique_count[field], label='%.1f %% in one bin\nJitter envelope found : %.1f toa tdc bin '%(fraction_delay_in_one_toa_bin*100, max_jitter_toa))
                        plt.legend()
                    else:
                        plt.hist(df_unique_count[field])
                    plt.title(field)
                    plt.ylabel('Count')
                    plt.xlabel('Number of distinct bins ')
                    plt.grid()
                plt.suptitle('# distinct bins obtained per delay tested for ch %d %s'%(channel, channel_gain))
                plt.tight_layout()
                plt.savefig(output_folder + 'distinct_bins_ch%d_%s.png'%(channel, channel_gain))
                # plt.show()
                plt.close()

    calib_stats_df = pd.read_csv(output_folder + 'calib_stats.csv')
    calib_stats_df = calib_stats_df.merge(pd.DataFrame(jitter_res), on=['channel', 'gain'], how='outer')
    calib_stats_df.to_csv(output_folder + 'calib_stats.csv')



def classify_tdc_cpt_data(df, config, output_folder, hitPeriod_in_320MHz_ck_cycles):
    # classify TDC & CPT data for each mode for each channel
    print("Classifying TDC & CPT data : ")
    injected_channel_list = config['enable_TL_ASIC_ch']

    quality_stats = {'modeRO':[],
                     'cluster':[],
                     'channel':[],
                     'good_tdc':[],
                     'CALc_corrected_tdc':[],
                     'good_cpt':[],
                     'bad_cpt':[]
                     }

    df = df.sort_values(by=['delay'])
    # df = df[df.delay<10]

    modeRO_list = np.unique(df.modeRO)
    # with alive_bar(len(modeRO_list) * len(injected_channel_list) * 2, force_tty=True) as bar:
    if 1:
        for mi, modeRO in enumerate(modeRO_list):
            for channel in injected_channel_list:
                for channel_gain in ['low', 'high']:
                    # bar()
                    cluster_channel = channel % 16
                    cluster = channel // 16
                    # cluster_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)

                    ch_gain_suffix_at_cluster_level = '_%s_ch%d' % (channel_gain, cluster_channel)
                    mode_cluster_selection = (df.cluster==cluster) & (df.modeRO == modeRO)

                    quality_stats['modeRO'].append(modeRO)
                    quality_stats['cluster'].append(cluster)
                    quality_stats['channel'].append(channel)

                    # TDC data quality
                    CALc_corrected_mode_cluster_selection = df.loc[mode_cluster_selection, 'CALc_corrected' + ch_gain_suffix_at_cluster_level]
                    CALc_corrected_count = CALc_corrected_mode_cluster_selection.value_counts()[CALc_corrected_mode_cluster_selection.value_counts().index == True].values
                    CALc_corrected_count = CALc_corrected_count[0] if CALc_corrected_count.size > 0 else 0
                    quality_stats['CALc_corrected_tdc'].append(CALc_corrected_count)

                    not_corrected = ~CALc_corrected_mode_cluster_selection
                    not_corrected_count = not_corrected.value_counts()[not_corrected.value_counts().index == True].values
                    not_corrected_count = not_corrected_count[0] if not_corrected_count.size > 0 else 0
                    quality_stats['good_tdc'].append(not_corrected_count)

                    # CPT data quality
                    CPT_modulo_hit_period = df['CPT' + ch_gain_suffix_at_cluster_level] % hitPeriod_in_320MHz_ck_cycles
                    good_cpt_selection = []

                    for delay in np.unique(df.loc[mode_cluster_selection, 'delay']):
                        delay_mode_cluster_selection = (df.delay == delay) & mode_cluster_selection

                        clock_phases = CPT_modulo_hit_period[delay_mode_cluster_selection].value_counts()
                        if clock_phases.size > 0:
                            dominant_clock_phase = clock_phases[clock_phases == np.max(clock_phases)].index[0]
                            event_with_dominant_ck_phase = CPT_modulo_hit_period[delay_mode_cluster_selection] == dominant_clock_phase
                            clock_phase_above_modulo = (df.loc[event_with_dominant_ck_phase & delay_mode_cluster_selection, 'CPT' + ch_gain_suffix_at_cluster_level] // hitPeriod_in_320MHz_ck_cycles).min()
                            clock_phase_above_modulo = clock_phase_above_modulo * hitPeriod_in_320MHz_ck_cycles

                            expected_CPT = df.loc[delay_mode_cluster_selection, 'index'] * hitPeriod_in_320MHz_ck_cycles + dominant_clock_phase + clock_phase_above_modulo

                            matching_CPT = df.loc[delay_mode_cluster_selection, 'CPT' + ch_gain_suffix_at_cluster_level] == expected_CPT
                            good_cpt_selection += list(matching_CPT)
                            pass
                            # df.loc[delay_mode_cluster_selection, 'good_cpt_selection'] = df.loc[delay_mode_cluster_selection, 'CPT' + ch_gain_suffix_at_cluster_level] == expected_CPT

                        else:
                            good_cpt_selection += [False]*len(delay_mode_cluster_selection)
                            # df.loc[delay_mode_cluster_selection, 'good_cpt_selection'] = False

                    good_cpt_selection = np.array(good_cpt_selection)
                    # df.loc[mode_cluster_selection, 'good_cpt_selection'+ch_gain_suffix_at_cluster_level] = good_cpt_selection

                    pass

                    df.loc[mode_cluster_selection, 'good_cpt_selection'+ch_gain_suffix_at_cluster_level] = good_cpt_selection
                    df.loc[mode_cluster_selection, 'bad_cpt_selection'+ch_gain_suffix_at_cluster_level] = ~good_cpt_selection

                    good_cpt_count = df.loc[mode_cluster_selection, 'good_cpt_selection'+ch_gain_suffix_at_cluster_level].value_counts()[df.loc[mode_cluster_selection, 'good_cpt_selection'+ch_gain_suffix_at_cluster_level].value_counts().index == True].values
                    good_cpt_count = good_cpt_count[0] if good_cpt_count.size > 0 else 0

                    bad_cpt_count =  df.loc[mode_cluster_selection, 'bad_cpt_selection'+ch_gain_suffix_at_cluster_level] .value_counts()[ df.loc[mode_cluster_selection, 'bad_cpt_selection'+ch_gain_suffix_at_cluster_level].value_counts().index == True].values
                    bad_cpt_count = bad_cpt_count[0] if bad_cpt_count.size > 0 else 0

                    quality_stats['good_cpt'].append(good_cpt_count)
                    quality_stats['bad_cpt'].append(bad_cpt_count)


    quality_stats_df = pd.DataFrame(quality_stats)
    quality_stats_df.to_csv(output_folder+'data_quality.csv')

    return df

def plot_tdc_cpt_quality(config, output_folder):
    injected_channel_list = config['enable_TL_ASIC_ch']

    quality_stats_df = pd.read_csv(output_folder + 'data_quality.csv')

    for modeRO in np.unique(quality_stats_df.modeRO):
        category_names_TDC_data = [col for col in quality_stats_df.columns if 'tdc' in col]
        category_names_CPT_data = [col for col in quality_stats_df.columns if 'cpt' in col]

        tdc_quality = {}
        cpt_quality = {}
        for channel in injected_channel_list:
            tdc_quality['Channel %d'%channel] = quality_stats_df.loc[(quality_stats_df.modeRO==modeRO) & (quality_stats_df.channel==channel), :].iloc[:, 3:5].values[0].tolist()
            cpt_quality['Channel %d'%channel] = quality_stats_df.loc[(quality_stats_df.modeRO==modeRO) & (quality_stats_df.channel==channel), :].iloc[:, 5:7].values[0].tolist()

        plot_data_quality(category_names_TDC_data, tdc_quality, 'TDC_data_quality_'+modeRO, output_folder)
        plot_data_quality(category_names_CPT_data, cpt_quality, 'CPT_data_quality_'+modeRO, output_folder)



def build_unique_dataframe_from_clusters(folder):
    # MERGE data into 1 dataframe per cluster

    df = None
    for cluster in range(4):
        filepath_list = glob.glob(folder + "/cluster_%d*.csv" % cluster)
        if filepath_list == 0:
            print("No events for cluster %d" % cluster)
            break

        for filepath in filepath_list:
            df_tmp = pd.read_csv(filepath)
            for col in df_tmp.columns:
                if 'ch' in col:
                    ch = int(re.findall("(?<=ch)[0-9]+", filepath)[0])
                    df_tmp.rename({col: col.replace("ch%d"%ch, "ch%d"%(ch+cluster*16))})  #todo
                else: # shared within cluster
                    df_tmp.rename({col:col+'_cluster%d'%cluster})

            df_tmp['delay'] = int(re.findall("(?<=delay_)[0-9]+", filepath)[0])
            df_tmp['temp'] = int(re.findall("(?<=temp_)[0-9]+", filepath)[0])
            df_tmp['iter'] = df_tmp.index

            nb_events_recorded_new = len(df_tmp)
            if df is None:
                df = df_tmp
            else:
                nb_events_recorded_old = len(df)
                df = df.merge(df_tmp, how='outer') # merge on indexes
                if (len(df)-nb_events_recorded_old) < nb_events_recorded_new:
                    print("Events were lost while being merged with other cluster")
                    exit(0)

        df.to_csv(folder + "/../data.csv")

def find_step(hit_freq, tdc_clock):
    # hit_given_by = 'PLL' if tdc_clock % 40e6 == 0 else 'FPGA'
    # if hit_given_by == 'PLL':
    #     N = tdc_clock // (hit_freq * 2)
    #     dt = 2 * N / tdc_clock - 2 / hit_freq

    # elif hit_given_by == 'FPGA':
    #     N2 = round(tdc_clock // hit_freq)
    #     dt = 1 / hit_freq - N2 / tdc_clock
    # else:
    #     print("unknown custom step mode : a delta frequency is either added to the hit freq or tdc ck freq ")
    #     exit(0)
    N = round(tdc_clock / hit_freq)
    dt =  N / tdc_clock - 1 / hit_freq
    return dt  # ps


def find_ck_cycles_in_between_2_hits(hit_freq, tdc_clock):
    hit_given_by = 'PLL' if tdc_clock%40e6 == 0 else 'FPGA'
    if hit_given_by == 'PLL':
        N = tdc_clock // (hit_freq * 2)
        ck_cycles_in_between_2_hits = 2 * N
    elif hit_given_by == 'FPGA':
        ck_cycles_in_between_2_hits = round(tdc_clock//hit_freq)
    else:
        print("unknown custom step mode : a delta frequency is either added to the hit freq or tdc ck freq ")
        exit(0)
    return ck_cycles_in_between_2_hits


def frequency_planner(target_hit_frequency, target_time_step, tdc_clock_freq=320e6, hit_given_by='PLL', readout_mode='low_tdc'):
    max_hit_rate_for_this_ROmode = tdc_clock_freq/CONSTANTS.FRAME_LENGTH_RO_MODE_STR[readout_mode][0]
    if target_hit_frequency > max_hit_rate_for_this_ROmode:
        print(Fore.RED+" Target hit frequency %d Hz is above Temporoc max hit rate capability in ROmode %s %d! "%
              (target_hit_frequency, readout_mode, max_hit_rate_for_this_ROmode) + Style.RESET_ALL)
        pass

    if hit_given_by == 'PLL':  # input D of the DFF

        N = tdc_clock_freq//(target_hit_frequency*2)
        df = target_time_step * tdc_clock_freq ** 2 / (2 * N ** 2 - tdc_clock_freq * target_time_step * N)
        # hit_frequency = int(tdc_clock/N + df)
        hit_frequency = tdc_clock_freq/N + df
        dt = 2*N/tdc_clock_freq - 2/hit_frequency
        required_samples = round(1/tdc_clock_freq/dt)
        print("PLL OUTPUT 0 (input D  of DFF) and OUT 7 (ck input of DFF) should configured to %f Hz \n"
              "NB : OUT 0 is divided by 2 inside the FPGA (=> %f Hz)\n"
              "Achieving a step of %.5f ps \n"
              "Resulting in one TDC hit every %d x %dM clock cycles \n"
              "Full TDC caracteristic is covered in %d samples"%(hit_frequency, hit_frequency/2, dt*1e12, 2*N, tdc_clock_freq/1e6, required_samples))

        ck_cycles_in_between_2_hits = 2*N
        hit_frequency = hit_frequency / 2
        fpga_divider = 2 # default

    elif hit_given_by == 'FPGA':
        # goal : have a pulser of smaller width
        print("PLL output 0 should provide a 80 MHz to the FPGA")
        # assert_frequency_in_pulser range
        assert target_hit_frequency <= 40e6
        assert target_hit_frequency > 80e6 // 0xffff

        FPGA_pulser_freq = 80e6
        N1 = round(FPGA_pulser_freq//target_hit_frequency) # ck_submultiple
        hit_frequency = FPGA_pulser_freq/N1

        N2 = round(tdc_clock_freq//hit_frequency) # ck_submultiple
        df = tdc_clock_freq - N2/(target_time_step+(1/hit_frequency))
        new_tdc_ck = tdc_clock_freq + df

        dt = 1 / hit_frequency - N2 / new_tdc_ck

        # dff_ck_frequency = tdc_clock/ck_submultiple + df
        required_samples = round(1 / new_tdc_ck / dt)
        ck_cycles_in_between_2_hits = round(new_tdc_ck//hit_frequency)

        print("PLL output 0 (input D  of DFF) should configured to %f Hz \n"
              "PLL output 6 (TDC & dig clock) -------------------- %f Hz \n"
              "PLL output 7 (ck input of DFF) -------------------- %f Hz (sufficiently far away from TDC clock to reduce coupling)\n"
              "Giving a step of ~%.0f ps \n"
              "Resulting in one TDC hit every %d x %dM clock cycles \n"
              "Full TDC caracteristic is covered in %d samples" % (
              FPGA_pulser_freq, new_tdc_ck, tdc_clock_freq*8, dt * 1e12, ck_cycles_in_between_2_hits, tdc_clock_freq / 1e6, required_samples))
        fpga_divider = 2 # default

    elif hit_given_by == "best":
        # goal : have a pulser of smaller width -
        # => PLL output  should be close to 80 MHz to have a pulse width close about 12.5 ns

        N = int(tdc_clock_freq//target_hit_frequency)
        df = target_time_step * tdc_clock_freq ** 2 / (N ** 2 - tdc_clock_freq * target_time_step * N)
        hit_frequency = tdc_clock_freq/N + df
        dt = N/tdc_clock_freq - 1/hit_frequency
        required_samples = round(1/tdc_clock_freq/dt)
        fpga_divider = N
        pll_out0 = fpga_divider*hit_frequency
        print(f"PLL OUTPUT 0 (input D  of DFF) should configured to {pll_out0:_.3f} Hz \n"
              f"FPGA divider -------------------------------------- {fpga_divider:n} -> External trigger = {hit_frequency:_.3f} Hz\n"
              f"PLL output 7 (ck input of DFF) -------------------- {2*pll_out0:_.3f} (= exactly 2*OUT0, for sampling ext trigger signal from FPGA)\n"
              f"Achieving a step of {dt*1e12:.1f} ps \n"
              f"Resulting in one TDC hit every {N:n} x {tdc_clock_freq/1e6:n}M clock cycles \n"
              f"Full TDC caracteristic is covered in {required_samples:n} samples")

        ck_cycles_in_between_2_hits = N

    else:
        print("incorrect arg hit_given_by")
        exit(0)
    pass
    return dt, ck_cycles_in_between_2_hits, hit_frequency, fpga_divider



def compare_bit_conversion_method_for_tdc_channel_data(folder):
    files = glob.glob(folder)

    channel = 0
    channel_gain = 'low'

    df_all = pd.DataFrame()
    for file in files:
        df = build_dataframe_from_file(file)

        df['delay'] = int(re.findall("(?<=delay)[0-9]+", file)[0])

        # tdc_value = df['tdc_%s_ch%d'%(channel_gain, channel)].apply(lambda x: (reverse_mask(x) >> (32 - 18)))
        tdc_value = df['tdc_%s_ch%d' % (channel_gain, channel)]

        # t = ['TOAcoarse', 'TOAfine', 'CALcoarse', 'CALfine', 'toa', 'cal', 'delta']

        df['TOAfine0'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000_0000) >> 14)
        df['TOAcoarse0'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000_0000) >> 9)
        df['CALfine0'] = tdc_value.apply(lambda x: (x & 0b1_1111_0000) >> 4)
        df['CALcoarse0'] = tdc_value.apply(lambda x: x & 0b1111)
        df['toa0'] = df.TOAfine0 + 31 * df.TOAcoarse0
        df['cal0'] = df.CALfine0 + 31 * df.CALcoarse0
        df['delta0'] = df.cal0 - df.toa0
        df['toa_ns0'] = df.toa0 * 2*3.125/np.abs(df.delta0)

        # print("method 0 :")
        # print(df[t])

        df['CALfine1'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000_0000) >> 14)
        df['CALcoarse1'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000_0000) >> 9)
        df['TOAfine1'] = tdc_value.apply(lambda x: (x & 0b1_1111_0000) >> 4)
        df['TOAcoarse1'] = tdc_value.apply(lambda x: x & 0b1111)
        df['toa1'] = df.TOAfine1 + 31 * df.TOAcoarse1
        df['cal1'] = df.CALfine1 + 31 * df.CALcoarse1
        df['delta1'] = df.cal1 - df.toa1
        df['toa_ns1'] = df.toa1 * 2 * 3.125 / np.abs(df.delta1)
        # print("method 1 :")
        # print(df[t])

        # second best
        df['TOAcoarse2'] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 14)  # 4 bits
        df['TOAfine2'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000) >> 9)  # 5 bits
        df['CALcoarse2'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000) >> 5)  # 4 bits
        df['CALfine2'] = tdc_value.apply(lambda x: x & 0b1_1111)  # 5 bits
        df['toa2'] = df.TOAfine2 + 31 * df.TOAcoarse2
        df['cal2'] = df.CALfine2 + 31 * df.CALcoarse2
        df['delta2'] = df.cal2 - df.toa2
        df['toa_ns2'] = df.toa2 * 2 * 3.125 / np.abs(df.delta2)
        # print("method 2 :")
        # print(df[t])

        # best
        df['CALcoarse3'] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 14)  # 4 bits
        df['CALfine3'] = tdc_value.apply(lambda x: (x & 0b11_1110_0000_0000) >> 9)  # 5 bits
        df['TOAcoarse3'] = tdc_value.apply(lambda x: (x & 0b1_1110_0000) >> 5)  # 4 bits
        df['TOAfine3'] = tdc_value.apply(lambda x: x & 0b1_1111)  # 5 bits
        df['toa3'] = df.TOAfine3 + 31 * df.TOAcoarse3
        df['cal3'] = df.CALfine3 + 31 * df.CALcoarse3
        df['delta3'] = df.cal3 - df.toa3
        df['toa_ns3'] = df.toa3 * 2*3.125/np.abs(df.delta3)

        # print("method 3 :")
        # print(df[t])

        # df['CPT'] = df.time.apply(lambda x: x << 14) + df.msb_cpt.apply(lambda x: x << 4) + df[
        #     'cpt_%s_ch%d' % (channel_gain, channel)]
        df['CPT'] = df.msb_cpt.apply(lambda x: x << 4) + df['cpt_%s_ch%d' % (channel_gain, channel)]
        # df['CPT'] -= df.CPT.min()

        df['msb_cpt_modulo_4096'] = df.CPT % 4096
        # modulo_val, modulo_count = np.unique(df.msb_cpt_modulo_4096, return_counts=True)
        # print(modulo_val, modulo_count, modulo_val[1] - modulo_val[0])
        # print(df.loc[:, ['delta0', 'delta1', 'delta2', 'delta3', 'msb_cpt_modulo_4096']].drop_duplicates())

        # df['selection'] = df['msb_cpt_modulo_4096'] == modulo_val[np.where(modulo_count == max(modulo_count))][0]
        df_all = pd.concat([df_all, df])

    fig, axs = plt.subplots(3, 4, figsize=(10, 8))
    axs = axs.reshape(-1)

    # selection = df_all['tdc_%s_ch%d' % (channel_gain, channel)] != 0
    # events_dropped = selection.value_counts()[selection.value_counts().index == False].values
    # if events_dropped.size > 0:
    #     events_dropped = events_dropped[0]
    #     label_events_dropped = "%d (or %.2f %%)" % (events_dropped, (events_dropped / len(df_all) * 100))
    #     print(label_events_dropped+" events dropped because null TDC data")
    # df_all = df_all[selection]

    # for method in range(4):
    #     print(len(df_all.delay))
    #     plt.subplot(2,2,method+1)
    #     plt.scatter(df_all.delay, df_all['toa%d'%method], marker='x', label='toa%d'%method)
    #     # axs[method].scatter(df_all.delay, df_all['cal%d'%method], marker='x', label='cal%d'%method)
    #     # axs[method].scatter(df_all.delay, df_all['delta%d'%method], marker='x', label='delta%d'%method)
    #     plt.title("method %d"%method)
    #     plt.legend()
    #     plt.grid()

    # selection = (50 < df_all['delta2']) & (df_all['delta2'] < 150)
    # events_dropped = selection.value_counts()[selection.value_counts().index == False].values
    # if events_dropped.size > 0:
    #     events_dropped = events_dropped[0]
    #     label_events_dropped = "%d (or %.2f %%)" % (events_dropped, (events_dropped / len(df_all) * 100))
    #     print(label_events_dropped + " events dropped because absurd delta")
    # df_all = df_all[selection]

    # selection = df_all['selection']
    for method in range(4):
        for i, field in enumerate(['toa', 'toa_ns', 'delta']):
            print(len(df_all['delay']))
            plt.subplot(3, 4, method + i * 4 + 1)
            plt.scatter(df_all.loc[:, 'delay'], df_all.loc[:, '%s%d' % (field, method)], marker='x', label=field)
            # plt.scatter(df_all.loc[selection, 'delay'], df_all.loc[selection, '%s%d' % (field, method)], marker='x',
            #             label=field)
            # plt.scatter(df_all.loc[~selection, 'delay'], df_all.loc[~selection, '%s%d' % (field, method)], marker='x',
            #             label='absurd delta')
            # axs[method].scatter(df_all.delay, df_all['cal%d'%method], marker='x', label='cal%d'%method)
            # axs[method].scatter(df_all.delay, df_all['delta%d'%method], marker='x', label='delta%d'%method)
            if i == 0:
                plt.title("method %d" % method)
                # plt.title("%s" % field)
            plt.legend()
            plt.grid()

    plt.show()



def plot_tdc_histo(df, config, file_suffix):

    board = config['board'][0]
    board_config = config['config_B%d' % board]
    # ASIC_channel_selection = [33, 35, 41, 46, 28, 20, 25]  # inner 7 channels
    # ASIC_channel_selection += [52, 54, 51, 43, 31, 23, 15, 17, 14, 22, 38, 44]  # + ring channels around
    ASIC_channel_selection = board_config['enable_TL_ASIC_ch'][0]

    for gain in ['high', 'low']:
        for meas in ['toa', 'cal']:
            tdc_has_triggered_col_list = ['tdc_data_valid' + '_%s_ch%d_B%d' % (gain, channel, board) for channel in
                                          ASIC_channel_selection]
            col_list = [meas + '_%s_ch%d_B%d' % (gain, channel, board) for channel in ASIC_channel_selection]
            array = df.loc[df[tdc_has_triggered_col_list].any(axis=1), col_list]
            if len(array) > 0:
                step = 10
                bins = np.arange(array.min().min(), array.max().max()+step, step)
            else:
                print("plot_tdc_histo : skip gain %s meas %s"%(gain, meas))
                continue
            plt.subplots(8, 8)
            for i, channel in enumerate(ASIC_channel_selection):
                plt.subplot(8, 8, i+1)
                event_selection = 'tdc_data_valid_%s_ch%d_B%d' % (gain, channel, board)
                channel_col = meas + '_%s_ch%d_B%d' % (gain, channel, board)
                df.loc[df[event_selection], channel_col].hist(bins=bins)
                plt.grid()
                plt.title(gain+' ch%d'%channel)
            # df.loc[df[row_selection_list], col_list].hist(bins=bins)
            # df[col_list].hist(bins=bins)
            plt.suptitle(meas+' histograms')
            mng = plt.get_current_fig_manager()
            mng.full_screen_toggle()
            plt.tight_layout()
            plt.savefig(config['save_folder']+'../'+file_suffix+'/frame/'+meas+'_'+gain+'_histo_all_channels.png')
            # plt.show()
            plt.close()
    # plt.show()


if __name__ == '__main__':

    # output_dir =
    # analyse_code_density("data/code_density/")
    # analyse_linearity_quick("data/5ps_step/")
    # analyse_linearity("data/5ps_step/", "data/code_density/output/toa_non_linearity_calib_table.csv")

    # frequency_planner(1.25e6, 2e-12)
    # frequency_planner(8e6, 4e-12)
    # tdc_scan_custom_step()
    # analyse_linearity_quick_file("0_B2_VDDD_1.2V_hit_1250003_Hz_CK_2500006_Hz_step_1.92ps_truncated.csv")
    # analyse_linearity_quick_file(output_dir+"custom_step/2_B2_VDDD_1.2V_hit_8000256_Hz_CK_16000512_Hz_step_4ps_delay_37.csv")
    # analyse_linearity_quick_file("output/standalone_tdc/custom_step/3_B1_VDDD_1.3V_hit_8000256_Hz_CK_16000512_Hz_step_3ps_delay_37.csv")

    # analyse_code_density(output_dir+"code_density/1_B2_VDDD_1.2V_hit_1150000_Hz_CK_2300000_Hz.csv") # is the hit random enough ?
    # analyse_code_density(output_dir+"code_density/2_B2_VDDD_1.2V_hit_9000000_Hz_CK_18000000_Hz.csv") # is not random at all !
    # analyse_code_density(output_dir+"code_density/3_B2_VDDD_1.2V_hit_450000_Hz_CK_900000_Hz.csv")

    # compare_bit_conversion_method_for_tdc_channel_data("output/internal_tdc/ch_2/delaybox_step/13*.csv")
    # compare_bit_conversion_method_for_tdc_channel_data("output/internal_tdc/delaybox_step/raw/4/B*.csv")

    # analyse_linearity_quick_folder("output/standalone_tdc/delaybox_step/3*.csv")

    pass