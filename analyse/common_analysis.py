import glob
import os
import re
import shutil
import subprocess
import time

import yaml
from scipy.optimize import curve_fit, OptimizeWarning
import warnings
warnings.simplefilter("error", OptimizeWarning)
import matplotlib as mpl

from src.CONSTANTS import get_SiPM_ch, get_ASIC_ch

mpl.use('TkAgg')
import matplotlib.pyplot as plt

from src.utils import plot_hex_sipm, modelGauss, ScurveFit, half_max_x, ScurveFitA, ScurveFit_Delagnes, ScurveFit_noDen, \
    get_hex_sipm_XY_ch_coordinates
from scipy.stats import gaussian_kde

import pandas as pd
import numpy as np

from pylatex import (
    Alignat,
    Axis,
    Document,
    Figure,
    Math,
    Matrix,
    Plot,
    Section,
    Subsection,
    Tabular,
    TikZ, Command, NoEscape, Subsubsection, Itemize, Package, SubFigure, LongTable,
)
from pylatex.utils import (bold)


def analyse_scurve(df, output_folder, figname, board, figtitle='', plot=True, dac_step=5, channel_to_ignore_for_each_gain=[[],[]], discri_list = [1,2]):
    local_thresh_in_global_dacu_for_each_gain = [[], []]
    noise_in_global_dacu_for_each_gain = [[], []]

    for discri in discri_list:

        dac_col_label = 'T%d_thres_dac'%discri
        efficiency_col_label = 'T%d_efficiency'%discri

        if dac_col_label in df.columns:

            # simple check
            if any(df.loc[df[dac_col_label]==df[dac_col_label].min(), efficiency_col_label]!=1.0):
                print("Threshold out of discri range for some channels. Ib_calib_dac probably too low")
                assert 1

            # fit scurves
            gi = discri-1

            for channel in range(64):
                if channel in channel_to_ignore_for_each_gain[gi]:
                    local_thresh_in_global_dacu_for_each_gain[gi].append(np.nan)
                    noise_in_global_dacu_for_each_gain[gi].append(np.nan)
                    continue
                serie = df.loc[(df.channel == channel) & (df[efficiency_col_label] < 1), :]
                if len(serie)>0:
                    most_likely_threshold = serie[dac_col_label].iloc[(np.abs(serie[efficiency_col_label] - 0.5)).argmin()]
                    # return first index if all efficiency are null
                    # most_likely_threshold = serie[dac_col_label].iloc[0]
                    local_thresh_in_global_dacu_for_each_gain[gi].append(most_likely_threshold)
                    noise_in_global_dacu_for_each_gain[gi].append(0) # default value

                else:
                    print("No threshold dac found for channel %d T%d"%(channel, discri))
                    pass

            for channel in range(64):
                if channel in channel_to_ignore_for_each_gain[gi]:
                    continue

                serie = df.loc[df.channel == channel, [dac_col_label, efficiency_col_label]].dropna(axis=0)
                transition_values = sum((serie[efficiency_col_label]<1) & (serie[efficiency_col_label]>0))
                estimated_threshold = local_thresh_in_global_dacu_for_each_gain[gi][channel]
                serie = serie[(serie[dac_col_label]>estimated_threshold-20) & (serie[dac_col_label]<estimated_threshold+20)]

                estimated_sigma = 1 if transition_values>1 else 0.1
                estimated_one_over_sigma = 1/estimated_sigma if transition_values>0 else 0
                # p0_init = [estimated_threshold, 0.1, 0.5]
                # p0_init = [estimated_threshold, estimated_sigma]
                p0_init = [estimated_threshold, estimated_one_over_sigma]
                # p0_init = [estimated_threshold, 1, 63]
                x = serie[dac_col_label].values
                y = serie[efficiency_col_label].values
                try:
                    # fit, cov = curve_fit(f=ScurveFit, xdata=x, ydata=y, p0=p0_init)
                    fit, cov = curve_fit(f=ScurveFit_noDen, xdata=x, ydata=y, p0=p0_init)
                    # https://stackoverflow.com/questions/56607312/how-can-fit-a-curve-to-step-function
                    local_thresh_in_global_dacu_for_each_gain[gi][channel] = fit[0]
                    noise_in_global_dacu_for_each_gain[gi][channel] = 1/fit[1]

                    if abs(local_thresh_in_global_dacu_for_each_gain[gi][channel]-fit[0])>10:
                        print("Fit result (%d) for channel %d seems far from first estimation (%d). Keeping first guess."%(fit[0], channel, local_thresh_in_global_dacu_for_each_gain[gi][channel]))

                        plt.figure(0, figsize=(13, 10))
                        plt.scatter(x, y)
                        plt.plot(x, ScurveFit_noDen(x, *fit), color='red', label='fit mean %.2f sigma %.2f'%(fit[0], 1/fit[1]))
                        plt.title(figtitle+" Weird fit")
                        plt.axvline(fit[0], color='red', ls='dashed', label="fit = value saved ")
                        plt.axvline(estimated_threshold, color='green', ls='dashed', label="closest to 50%")
                        plt.grid(visible=True)
                        plt.xlabel(dac_col_label)
                        plt.ylabel(efficiency_col_label)
                        plt.legend()
                        plt.tight_layout()
                        plt.savefig(output_folder + figname+"_ch%d_"%channel+figtitle+".png")
                        plt.close()
                        pass

                except (OptimizeWarning, RuntimeError):

                    if all(y)==0:
                        print("Error fitting scurve for channel %d : all efficiencies value null" % channel)
                    else:
                        print("Error fitting scurve for channel %d : check plot " % channel)
                        plt.figure(0, figsize=(13, 10))
                        plt.scatter(x, y)
                        sigma = 1 / p0_init[1] if p0_init[1]!=0 else np.inf
                        plt.plot(x, ScurveFit_noDen(x, *p0_init), label='p0_init mean %.2f sigma %.2f' % (p0_init[0], sigma))
                        plt.title(figtitle+" Error fit")
                        plt.axvline(estimated_threshold, color='green', ls='dashed', label="closest to 50% = value saved")
                        plt.grid(visible=True)
                        plt.xlabel(dac_col_label)
                        plt.ylabel(efficiency_col_label)
                        plt.legend()
                        plt.tight_layout()
                        plt.savefig(output_folder + figname + "_ch%d_" % channel + figtitle + ".png")
                        plt.close()

                    pass

            if plot:
                fig, ax = plt.subplots(1, 1, figsize=(13, 10))

                # 2D
                # for channel in range(11,21): #config['enable_TL_ASIC_ch'][0]:
                #     selection = (df.channel == channel)
                #     not_nan_selection = ~(df.loc[:, dac_col_label].isna())
                #     thres_dac = df.loc[selection & not_nan_selection, dac_col_label]
                #     trigger_effiency = df.loc[selection & not_nan_selection, efficiency_col_label]
                #
                #     plt.plot(thres_dac, trigger_effiency, label="%d"%channel, marker='+') #  %d, %d, %d, hv,patGain, patComp),
                #
                # plt.grid()
                # plt.legend()
                # plt.title('Trigger efficiency')
                # plt.suptitle("legend: ch") # hv, patGain, patComp
                # plt.tight_layout()
                #     # plt.savefig(output_folder+'ch%d.png'%channel)

                # 3D
                # effDf['thres'] = effDf['thres'].astype(np.int32)
                map = df.pivot_table(index='channel', columns=dac_col_label,
                                     values=efficiency_col_label)  # , fill_value=np.nan)

                # write down strange high efficiency
                # xOffset=effDf['thres'].min()
                # coordinatesToAnnotate = effDf[effDf['efficiency'] > 0.99]
                # plt.show()
                # for c in coordinatesToAnnotate.values:
                #     ax.text(c[2], c[0]-xOffset, "%.2f"%float(c[1]), ha="center", va="center", color="w", fontsize=6)  # '%.2f' %
                dac_map = np.reshape(np.array(map.columns.values), (-1, len(map.columns))).repeat(len(map), axis=0)
                thresh_map = np.reshape(local_thresh_in_global_dacu_for_each_gain[gi], (-1, len(local_thresh_in_global_dacu_for_each_gain[gi]))).T.repeat(len(map.columns), axis=1)
                map[(dac_map < thresh_map) & np.isnan(map)] = 1
                map[(dac_map > thresh_map) & np.isnan(map)] = 0
                min_dac = min(local_thresh_in_global_dacu_for_each_gain[gi])-5
                map = map.loc[:,map.columns>min_dac]
                vmax = 1 #map.values.max()
                vmin = 0

                im = ax.imshow(map.values, origin='lower', vmin=vmin, vmax=vmax, aspect='auto')

                for channel in range(64):
                    if channel in channel_to_ignore_for_each_gain[gi]:
                        continue
                    # first_dac_swept = df.loc[df.channel == channel, dac_col_label].iloc[0]
                    first_dac_swept = map.columns[0]
                    ax.axvline(x=local_thresh_in_global_dacu_for_each_gain[gi][channel]-first_dac_swept, ymin=channel/64, ymax=(channel+1)/64, color='red')

                ax.set_xticks(range(0, len(np.int32(map.columns)), dac_step), np.int32(map.columns[::dac_step]))
                ax.set_yticks(range(len(map.index)), map.index)
                # ax.tick_params(axis='both', which='major', labelsize=8)
                ax.set_xlabel("Threshold")
                ax.set_ylabel("Channel")
                cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                cbar.ax.tick_params(labelsize=20)

                plt.title(figtitle+(" B%d "%board)+'T%d'%discri+" SCURVE : MEDIAN %d MEAN %d STD %d" % (np.nanmedian(local_thresh_in_global_dacu_for_each_gain[gi]), np.nanmean(local_thresh_in_global_dacu_for_each_gain[gi]), np.nanstd(local_thresh_in_global_dacu_for_each_gain[gi])))
                plt.tight_layout()

                plt.savefig(output_folder + figname + '_'+ 'T%d '%discri + "_trigger_efficiency_map.png", dpi=120)
                # plt.show()
                plt.close()


    # if plot:
        # plt.figure(0, figsize=(13, 10))
        # for i, discri in enumerate(discri_list):
        #     if discri in discri_list:
        #         plt.scatter(range(64), noise_in_global_dacu_for_each_gain[i], label=('T%d '%discri)+figname)
        #
        # plt.title(("B%d" % board) + " Noise from scurve fit")
        # plt.grid(visible=True)
        # plt.xlabel("Channel")
        # plt.ylabel("Noise [global dac unit]")
        # plt.tight_layout()
        # plt.legend()
        # plt.savefig(output_folder + figname+"_noise.png")
        # plt.close()

    for i in range(len(noise_in_global_dacu_for_each_gain)):
        noise_in_global_dacu_for_each_gain[i] = np.array(noise_in_global_dacu_for_each_gain[i])
        local_thresh_in_global_dacu_for_each_gain[i] = np.array(local_thresh_in_global_dacu_for_each_gain[i])
    return local_thresh_in_global_dacu_for_each_gain[0], local_thresh_in_global_dacu_for_each_gain[1], noise_in_global_dacu_for_each_gain

def analyse_poor_granularity_scurve(df, output_folder, figname, board, figtitle='', discri_list = [1,2], plot=True):

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    local_thresh_in_global_dacu_for_each_discri = []
    channel_to_ignore_for_each_gain = []

    for gi, discri in enumerate(discri_list):
        dac_col_label = 'T%d_thres_dac'%discri
        efficiency_col_label = 'T%d_efficiency'%discri

        assert dac_col_label in df.columns
        local_thresh_in_global_dacu_for_each_discri.append([])
        channel_to_ignore_for_each_gain.append([])

        # df_pivot = df.pivot_table(index=dac_col_label, columns='channel', values=efficiency_col_label)
        #
        # if len(df_pivot[(df_pivot == 1).all(axis=1)])==0:
        #     problematic_channels = df_pivot.iloc[0][df_pivot.iloc[0]!=1].to_dict()
        #     channel_to_ignore_for_each_gain[gi] += list(problematic_channels.keys())
        #     print("Problematic values for {channel : normalised hit freq}", problematic_channels)
        #     if df_pivot.index[0] == 0: #Likely channel not connected and should be ignored for defining next range !
        #         new_col_list = list(set(df_pivot.columns) ^ set(problematic_channels.keys()))
        #         df_pivot1 = df_pivot.iloc[:, list(new_col_list)].copy()
        #         global_dac_min = min(global_dac_min, int(max(df_pivot1.loc[(df_pivot1 == 1).all(axis=1)].index)))
        #
        # else:
        #     global_dac_min = min(global_dac_min, int(max(df_pivot[(df_pivot == 1).all(axis=1)].index)))
        #
        #
        # if len(df_pivot[(df_pivot == 0).all(axis=1)])==0:
        #     # global_dac_max = df_pivot.index[-1] # maximum explored
        #     pass
        # else:
        #     global_dac_max = max(global_dac_max, int(min(df_pivot[(df_pivot == 0).all(axis=1)].index)))


        # find threshold
        gi = discri-1
        for channel in range(64):
            local_thresh_in_global_dacu_for_each_gain_for_each_ch = \
            np.where(df.loc[df.channel == channel, efficiency_col_label] < 1)[0]
            if len(local_thresh_in_global_dacu_for_each_gain_for_each_ch) > 0:
                local_thresh_in_global_dacu_for_each_discri[gi].append(df.loc[df.channel == channel, dac_col_label]
                    .iloc[min(local_thresh_in_global_dacu_for_each_gain_for_each_ch)])
            else:
                print("Could not find coarse threshold for channel %d"%channel)
                pass
        if plot:
            fig, ax = plt.subplots(1, 1, figsize=(13, 10))
            map = df.pivot_table(index='channel', columns=dac_col_label, values=efficiency_col_label)
            vmax = map.values.max()
            vmin = 0
            im = ax.imshow(map.values, origin='lower', vmin=vmin, vmax=vmax, aspect='auto')

            for channel in range(64):
                first_dac_swept = df.loc[df.channel == channel, dac_col_label].iloc[0]
                imshow_virtual_offset = 5
                ax.axvline(x=(local_thresh_in_global_dacu_for_each_discri[gi][channel]
                              - imshow_virtual_offset - first_dac_swept)/10,
                           ymin=channel / 64, ymax=(channel + 1) / 64, color='red')

            ax.set_xticks(range(len(np.int32(map.columns))), np.int32(map.columns)+5)
            ax.set_yticks(range(len(map.index)), map.index)
            ax.set_xlabel("Threshold")
            ax.set_ylabel("Channel")
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.ax.tick_params(labelsize=20)


            ax.set_title(figtitle+" B%d T%d"%(board, discri) +" SCURVE ")  # : MIN %d MAX %d"%(global_dac_min, global_dac_max) MEAN %D STD %d
            fig.tight_layout()
            fig.savefig(output_folder + figname + "_T%d_trigger_efficiency_map_coarse_step.png"%discri, dpi=120)
            # plt.show()
            plt.close(fig)

        channel_to_ignore_for_each_gain[gi] += [ch for ch,val in enumerate(local_thresh_in_global_dacu_for_each_discri[gi]) if val == 0]

    if np.count_nonzero(np.nonzero(local_thresh_in_global_dacu_for_each_discri))==0:
        print("All value null ! No scurve detectable. Review parameters Ibcalibdac or 6bcalibdac or global threshold")
        exit(0)

    local_thresh_in_global_dacu_for_each_discri = np.array(local_thresh_in_global_dacu_for_each_discri)

    return  local_thresh_in_global_dacu_for_each_discri, channel_to_ignore_for_each_gain

def plot_adc_sum(serie, file_suffix, config, offset = 0):
    if len(serie)>0:
        board = config['board'][0]
        extra_label = " %d events = %d %% of acquired "%(config['merge_success_count_B%d'%board], config['merge_success_%%_B%d'%board])

        plt.figure(figsize=(9, 7))
        bins = np.arange(serie.min(), serie.max() + 5, 2)
        counts, bins = np.histogram(serie, bins=bins)
        # plt.stairs(counts, bins, color='darkcyan', fill=True, label=file_suffix[1:]) # remove _ otherwise ignore label legend
        plt.hist(bins[:-1], bins, weights=counts, align='left', color='darkcyan', label=file_suffix[1:]+extra_label)
        plt.yscale('linear')
        # plt.title(channel_selection)
        # GAUSSIAN fit

        offset_baseline = int(offset * len(bins))
        photopeak_index = offset_baseline + np.argmax(counts[offset_baseline:])
        # photopeak_index = argrelmax(counts, order=5)[0][2]
        mu = bins[photopeak_index]

        # index_xmax = photopeak_index + argrelmin(counts[photopeak_index:], order = 3)[0][0]
        # index_xmin = argrelmin(counts[:photopeak_index], order = 3)[0][-1]

        index_xmin = np.clip(photopeak_index - 5, 0, len(bins) - 1)
        index_xmax = np.clip(photopeak_index + 5, 0, len(bins) - 1)
        xmax = bins[index_xmax]
        xmin = bins[index_xmin]
        sigmaHisto = (xmax - xmin) / 5
        try:
            # plt.show()
            # xmin = bins[:photopeak_index][argrelmin(counts[:photopeak_index], order = 5)[0][-1]]
            # plt.axvline(photopeak, color='red', label='photopeak')
            # plt.axvline(photopeak_sup, color='red', linestyle='--', label='photopeak inf')
            # plt.axvline(photopeak_inf, color='red', linestyle='--', label='photopeak sup')

            # bins = np.arange(df['adc_sum_ch_selection'].min(), df['adc_sum_ch_selection'].max() + 10, 30)
            # counts, bins = np.histogram(df['adc_sum_ch_selection'], bins=bins)
            # plt.stairs(counts, bins, color='darkblue', fill=False, label='only 19 central channels supposely below small cristal')

            p0 = [mu, sigmaHisto, counts[photopeak_index]]

            fitParam, cov = curve_fit(modelGauss, bins[index_xmin: index_xmax], counts[index_xmin: index_xmax], p0=p0)
            # fitParam, cov = curve_fit(modelGauss, bins[photopeak_index-5:photopeak_index+5], counts[photopeak_index-5:photopeak_index+5], p0=p0)

            mu = fitParam[0]
            sigmaHisto = fitParam[1]
            ampHisto = fitParam[2]
            xmin = mu - 3 * sigmaHisto
            xmax = mu + 3 * sigmaHisto
            xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
            yfit = modelGauss(xfit, mu, sigmaHisto, ampHisto)

            # resolution_FWHM2 = 2.35 * sigmaHisto * 1e3
            r1, r2, FWHM = half_max_x(xfit, yfit)

            plt.plot(xfit, yfit, linestyle='-', color='red',
                     label="E = %d "%mu + r"$\Delta E/E$ " + '= %.0f %% FWHM' % (FWHM / mu * 100))
            # df3_filepath = config['output_folder'] + '3' + file_suffix + '.feather'
            # df.to_feather(df3_filepath)

            xmin = mu - 0.5* sigmaHisto
            xmax = mu + 0.5* sigmaHisto
            # xmin = mu + sigmaHisto
            # xmax = mu + 2* sigmaHisto
        except:
            print("Error fit energy resolution")
            plt.yscale('log')
            plt.axvline(mu, label='photopeak')
            plt.axvline(xmax, color='green', label='xmax')
            plt.axvline(xmin, color='green', label='xmin')



        plt.xlabel('ADC [lsb]')
        plt.ylabel('Count')
        plt.grid()
        plt.legend()
        return xmin, xmax, mu, sigmaHisto
    else:
        print("No data to plot ADC sum")
        exit()

def plot_frame_by_frame(df, config, file_suffix):
    board = config['board'][0]
    board_config = config['config_B%d' % board]
    if board_config['SiPM_model']=='Hamamatsu_S13361_6597':
        plot_frame_hexagonal_Hamamatsu(df, config, file_suffix)
    else:
        print("Need to be implemented !")

def plot_frame_hexagonal_Hamamatsu(df, config, file_suffix):

    # plot SiPM map frame-by-frame
    mpl.rcParams['savefig.directory'] = config['save_folder']+'../'+file_suffix+'/frame/'
    mpl.rcParams['savefig.format'] = 'png'

    board = config['board'][0]
    ASIC_channels_injected = get_ASIC_ch(list(range(1,62)), 'Hamamatsu_S13361_6597') # ORDER MATTERS !
    # should be in the SiPM channel order
    # missing_SiPM_channels = list(set(config['injected_channel_SiPM'][0]) ^ set(range(1, 62)))
    # missing_ASIC_channels_values = [0]*len(missing_SiPM_channels)

    adc_col_list_low = ['adc_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channels_injected]
    adc_col_list_high = ['adc_%s_ch%d_B%d' % ('high', channel, board) for channel in ASIC_channels_injected]

    # energy_selection = (df[adc_col_list_low] > 600).any(axis=1) & (df[adc_col_list_low] < 800).all(axis=1)
    energy_selection = (df[adc_col_list_low] > 200).any(axis=1)
    print(energy_selection.value_counts())

    tdc_has_triggered_col_list_high = ['tdc_data_valid_%s_ch%d_B%d' % ('high', channel, board) for channel in
                                       ASIC_channels_injected]
    toa_ns_col_list_high = ['toa_ns' + '_%s_ch%d_B%d' % ('high', channel, board) for channel in ASIC_channels_injected]
    toa_ns_col_list_low = ['toa_ns' + '_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channels_injected]

    tdc_has_triggered_col_list_low = ['tdc_data_valid_%s_ch%d_B%d' % ('low', channel, board) for channel in
                                      ASIC_channels_injected]
    # toa_col_list_low = ['toa' + '_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channels_injected]
    # toa_col_list_high = ['toa' + '_%s_ch%d_B%d' % ('high', channel, board) for channel in ASIC_channels_injected]

    lsb_fromCAL_col_list_low = ['lsb_fromCAL' + '_%s_ch%d_B%d' % ('low', channel, board)for channel in ASIC_channels_injected]
    lsb_fromCAL_col_list_high = ['lsb_fromCAL' + '_%s_ch%d_B%d' % ('high', channel, board) for channel in ASIC_channels_injected]

    cpt_col_list_low = ['cpt' + '_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channels_injected]
    cpt_col_list_high = ['cpt' + '_%s_ch%d_B%d' % ('high', channel, board) for channel in ASIC_channels_injected]

    # it happens that col are in the SiPM ranking order, ready to plot !
    # df1 = df.loc[energy_selection, time_col_list]
    # df1 = df1.rename(columns={col:get_SiPM_ch(int(col[13:]), 'Hamamatsu_S13361_6597') for col in df1.columns})
    # df1 = df1.rename(columns={col:get_SiPM_ch(int(col[7+len(time_measure):]), 'Hamamatsu_S13361_6597') for col in df1.columns})

    # df.loc[energy_selection, 'ch_suffix_photopeak'] = df[energy_selection].apply(lambda row: row[adc_col_list_low][row[adc_col_list_low] == row[adc_col_list_low].max()].index[0][3:], axis=1)
    # df.loc[energy_selection, 'min_toa_ns_matrix'] = df[energy_selection].apply(lambda row: row['toa_ns' + row['ch_suffix_photopeak']], axis=1)
    # df.loc[energy_selection, toa_ns_col_list_low] = df.loc[energy_selection, toa_ns_col_list_low].sub(df.loc[energy_selection, 'min_toa_ns_matrix'], axis=0)
    # df.loc[energy_selection, toa_ns_col_list_high] = df.loc[energy_selection, toa_ns_col_list_high].sub(df.loc[energy_selection, 'min_toa_ns_matrix'], axis=0)

    subset = df.loc[energy_selection, :]
    # subset = df.iloc[18:, :]
    for i, frame in subset.iterrows():

        fig, ax = plt.subplots(2, 4, figsize=(16, 9))
        fig.canvas.manager.set_window_title('Frame_%d'%i)

        plt.subplot(2, 4, 1)
        # im = plot_hex_sipm(frame[adc_col_list_low].to_list()+missing_ASIC_channels_values, 'Energy low gain')  # for frame %d'%i)
        im = plot_hex_sipm(frame[adc_col_list_low].to_list(), 'Energy low gain', font_size=8, plot_center_mass=True)  # for frame %d'%i)
        cb = plt.colorbar(im, label='LG Energy - pedestal [adc]', location='bottom', shrink=0.6)
        im.set_clim(0, 1023)

        plt.subplot(2, 4, 2)
        val = frame[toa_ns_col_list_low].where(frame[tdc_has_triggered_col_list_low].values, 0.0)
        val[val == 0] = -1
        val[val != -1] -= val[val != -1].min()
        val = val.to_list() #(val*1e3).to_list()
        im = plot_hex_sipm(val, 'TOA low', hidden_value=-1, label_format='%.1f')  # for frame %d'%i)
        cb = plt.colorbar(im, label='TOA [ns]', location='bottom', shrink=0.6)

        # plt.show()
        plt.subplot(2, 4, 3)
        val = frame[cpt_col_list_low].where(frame[tdc_has_triggered_col_list_low].values, 0.0).to_list()
        im = plot_hex_sipm(val, 'cpt low')
        cb = plt.colorbar(im, label='cpt [%.1f ns]'%(1e3/tempo_dig_ck), location='bottom', shrink=0.6)

        plt.subplot(2, 4, 4)
        # val = frame[overflown_TOA_col_list_low].to_list()
        # im = plot_hex_sipm(val, 'overflown_TOA_low')
        # cb = plt.colorbar(im, label='[1]', location='bottom', shrink=0.6)
        val = (frame[lsb_fromCAL_col_list_low].where(frame[tdc_has_triggered_col_list_low].values, 0.0)*1e3)
        val = (val-40)/40 * 100
        val = val.to_list()
        im = plot_hex_sipm(val, 'LSB from calibration low', hidden_value=-100, label_format='%.1f')
        cb = plt.colorbar(im, label='LSB relative variation\nfrom 40 ps [%]', location='bottom', shrink=0.6)
        # im.set_clim(val.min(), val.max())
        im.set_clim(-2, 3)

        plt.subplot(2, 4, 5)
        im = plot_hex_sipm(frame[adc_col_list_high].to_list(), 'Energy high gain', plot_values=False, plot_center_mass=True)  # for frame %d'%i)
        cb = plt.colorbar(im, label='HG Energy - pedestal [adc]', location='bottom', shrink=0.6)
        im.set_clim(0, 1023)

        plt.subplot(2, 4, 6)
        val = frame[toa_ns_col_list_high].where(frame[tdc_has_triggered_col_list_high].values, 0.0)
        val[val !=0] -= val[val!=0].min()
        val = val.to_list()
        im = plot_hex_sipm(val, 'TOA high')  # for frame %d'%i)
        cb = plt.colorbar(im, label='TOA [ps]', location='bottom', shrink=0.6)

        plt.subplot(2, 4, 7)
        val = frame[cpt_col_list_high].where(frame[tdc_has_triggered_col_list_high].values, 0.0).to_list()
        im = plot_hex_sipm(val, 'cpt high')
        cb = plt.colorbar(im, label='cpt [%.1f ns]'%(1e3/tempo_dig_ck), location='bottom', shrink=0.6)

        plt.subplot(2, 4, 8)
        # val = frame[overflown_TOA_col_list_high].to_list()
        # im = plot_hex_sipm(val, 'overflown_TOA_high')
        # cb = plt.colorbar(im, label='[1]', location='bottom', shrink=0.6)

        val = (frame[lsb_fromCAL_col_list_high].where(frame[tdc_has_triggered_col_list_high].values, 0.0)*1e3).to_list()
        # val = (frame[lsb_fromCAL_col_list_high] * 1e3).to_list()
        im = plot_hex_sipm(val, 'LSB from calibration high', hidden_value=0, label_format='%.1f')
        cb = plt.colorbar(im, label='LSB [ps]', location='bottom', shrink=0.6)
        im.set_clim(38, 42)

        plt.suptitle("Frame %d/%d - \n%s" % (i, len(subset), config['save_folder']))
        plt.tight_layout()
        mng = plt.get_current_fig_manager()
        mng.full_screen_toggle()

        plt.show()
        # plt.close()


def plot_flood_map(df, config, ASIC_channel_selection=None, file_label=None):
    # If source too close from the crystal, all recorded counts will be in the center !

    # Flood map
    dx = 1.875 * 2
    dy = 3.25
    X = [-2 * dx, -dx, 0, dx, 2 * dx]
    Y = [4 * dy for i in range(5)]
    X += [-5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2]
    Y += [3 * dy for i in range(6)]
    X += [-3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx]
    Y += [2 * dy for i in range(7)]
    X += [-7 * dx / 2, -5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2, 7 * dx / 2]
    Y += [dy for i in range(8)]
    X += [-4 * dx, -3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx, 4 * dx]
    Y += [0 for i in range(9)]
    X += [-7 * dx / 2, -5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2, 7 * dx / 2]
    Y += [-dy for i in range(8)]
    X += [-3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx]
    Y += [-2 * dy for i in range(7)]
    X += [-5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2]
    Y += [-3 * dy for i in range(6)]
    X += [-2 * dx, -dx, 0, dx, 2 * dx]
    Y += [-4 * dy for i in range(5)]
    X = np.array(X)
    Y = np.array(Y)

    # slow method
    # xg_list = []
    # yg_list = []
    # for i, row in df[(df[adc_col_list] > 200).any(axis=1)].iterrows():
    #     xg = 0
    #     yg = 0
    #     adc_sum = 0
    #     for SiPM_channel, adc_value in enumerate(row[adc_col_list].values):
    #         # if adc_value>50:
    #         xg += X[SiPM_channel] * adc_value
    #         yg += Y[SiPM_channel] * adc_value
    #         adc_sum += adc_value
    #     xg_list.append(xg/adc_sum)
    #     yg_list.append(yg/adc_sum)

    board = config['board'][0]
    if not ASIC_channel_selection:
        ASIC_channel_selection = get_ASIC_ch(list(range(1, 62)), 'Hamamatsu_S13361_6597')  # ORDER MATTERS !
        file_label = 'all_channels'
    else:  # channel defined externally: check if array is sorted with increasing SiPM channel !!
        SiPM_channel_selection = np.array(get_SiPM_ch(ASIC_channel_selection, 'Hamamatsu_S13361_6597'))
        array_sorted_index = SiPM_channel_selection.argsort()
        ASIC_channel_selection = np.array(ASIC_channel_selection)[array_sorted_index].tolist()
        # SiPM_channel_selection = np.array(get_SiPM_ch(ASIC_channel_selection, 'Hamamatsu_S13361_6597'))

    adc_col_list_selection = ['adc_%s_ch%d_B%d' % (gain, channel, board) for channel in ASIC_channel_selection for gain
                              in ['high']]
    SiPM_channel_selection = np.array(get_SiPM_ch(ASIC_channel_selection, 'Hamamatsu_S13361_6597')) - 1

    plt.figure(figsize=(6, 6))

    xg_list = df.loc[:, 'xg'] = df.loc[:, adc_col_list_selection].mul(X[SiPM_channel_selection]).sum(axis=1) / (
        df.loc[:, adc_col_list_selection].sum(axis=1))
    yg_list = df.loc[:, 'yg'] = df.loc[:, adc_col_list_selection].mul(Y[SiPM_channel_selection]).sum(axis=1) / (
        df.loc[:, adc_col_list_selection].sum(axis=1))
    bins = 300
    step = (max(X) - min(X)) / 100
    bins = np.arange(min(X), max(X) + step, step)
    plt.hist2d(xg_list, yg_list, bins=bins, cmap='plasma')
    plt.title(config['datapath_to_display'])
    # plt.legend("bin_size %d mm"%((max(xg_list)-min(xg_list))/bins))
    plt.legend("bin_size %.1f mm" % step)
    plt.tight_layout()
    plt.savefig(config['output_folder'] + 'flood_map_' + file_label + '.png')
    plt.show()
    plt.close()



def plot_flood_map2(df, config, threshold_dict):

    gain_photopeak = "high"
    energy_selection = df["photopeak_selection_"+gain_photopeak]
    print(energy_selection.value_counts())

    X,Y = get_hex_sipm_XY_ch_coordinates()

    board = config["board"][0]
    board_config = config["config_B%d" % board]


    # get the channel list in the right order = SIPM order
    SiPM_channel_injected = list(np.sort(board_config["injected_channel_SiPM"][0]))
    ASIC_channels_injected = get_ASIC_ch(SiPM_channel_injected, "Hamamatsu_S13361_6597")

    center_mass = {'X_low':[], 'Y_low':[], 'X_high':[], 'Y_high':[]}

    # energy_selection
    for i, frame in df.loc[:, :].iterrows():
        for gain in ['low', 'high']:
            column_label_list = ["adc_%s_ch%d_B%d" % (gain, channel, board) for channel in ASIC_channels_injected]

            threshold = threshold_dict[gain]
            SiPM_channel_value = frame[column_label_list].values
            SiPM_channel_value[SiPM_channel_value < threshold] = 0

            xg = sum(a[0] * a[1] for a in zip(SiPM_channel_value, X)) / sum(SiPM_channel_value)
            yg = sum(b[0] * b[1] for b in zip(SiPM_channel_value, Y)) / sum(SiPM_channel_value)
            center_mass['X_'+gain].append(xg)
            center_mass['Y_' + gain].append(yg)

    pd.DataFrame(center_mass).to_csv(config['output_folder']+f"center_mass_photopeak_{gain_photopeak}.csv")

    plt.subplots(1, 2, figsize=(9, 6))
    step = (max(X) - min(X)) / 100
    bins = np.arange(min(X), max(X) + step, step)

    for gi,gain in enumerate(['low', 'high']):
        ax = plt.subplot(1,2,gi+1)
        plt.hist2d(center_mass['X_'+gain], center_mass['Y_'+gain], bins=bins, cmap='plasma')
        plt.title(gain)
        ax.set_aspect("equal")

    plt.suptitle("Flood map = hist2d of center of mass of photopeak events bin_size %.1f mm" % step)
    plt.tight_layout()
    plt.savefig(config['output_folder'] + 'flood_map.png')
    for gi,gain in enumerate(['low', 'high']):
        ax = plt.subplot(1,2,gi+1)
        for x, y in zip(X, Y):
            plt.plot(x, y, "+", markersize=2, color="white")
    plt.savefig(config['output_folder'] + 'flood_map_with_channel_position.png')
    plt.show()
    plt.close()


    # slow method
    # xg_list = []
    # yg_list = []
    # for i, row in df[(df[adc_col_list] > 200).any(axis=1)].iterrows():
    #     xg = 0
    #     yg = 0
    #     adc_sum = 0
    #     for SiPM_channel, adc_value in enumerate(row[adc_col_list].values):
    #         # if adc_value>50:
    #         xg += X[SiPM_channel] * adc_value
    #         yg += Y[SiPM_channel] * adc_value
    #         adc_sum += adc_value
    #     xg_list.append(xg/adc_sum)
    #     yg_list.append(yg/adc_sum)

    # board = config['board'][0]
    # if not ASIC_channel_selection:
    #     ASIC_channel_selection = get_ASIC_ch(list(range(1, 62)), 'Hamamatsu_S13361_6597')  # ORDER MATTERS !
    #     file_label = 'all_channels'
    # else:  # channel defined externally: check if array is sorted with increasing SiPM channel !!
    #     SiPM_channel_selection = np.array(get_SiPM_ch(ASIC_channel_selection, 'Hamamatsu_S13361_6597'))
    #     array_sorted_index = SiPM_channel_selection.argsort()
    #     ASIC_channel_selection = np.array(ASIC_channel_selection)[array_sorted_index].tolist()
    #     # SiPM_channel_selection = np.array(get_SiPM_ch(ASIC_channel_selection, 'Hamamatsu_S13361_6597'))
    #
    # adc_col_list_selection = ['adc_%s_ch%d_B%d' % (gain, channel, board) for channel in ASIC_channel_selection for
    #                           gain
    #                           in ['high']]
    # SiPM_channel_selection = np.array(get_SiPM_ch(ASIC_channel_selection, 'Hamamatsu_S13361_6597')) - 1
    #
    # plt.figure(figsize=(6, 6))
    #
    # xg_list = df.loc[:, 'xg'] = df.loc[:, adc_col_list_selection].mul(X[SiPM_channel_selection]).sum(axis=1) / (
    #     df.loc[:, adc_col_list_selection].sum(axis=1))
    # yg_list = df.loc[:, 'yg'] = df.loc[:, adc_col_list_selection].mul(Y[SiPM_channel_selection]).sum(axis=1) / (
    #     df.loc[:, adc_col_list_selection].sum(axis=1))
    # bins = 300
    # step = (max(X) - min(X)) / 100
    # bins = np.arange(min(X), max(X) + step, step)
    # plt.hist2d(xg_list, yg_list, bins=bins, cmap='plasma')
    # plt.title(config['datapath_to_display'])
    # # plt.legend("bin_size %d mm"%((max(xg_list)-min(xg_list))/bins))
    # plt.legend("bin_size %.1f mm" % step)
    # plt.tight_layout()
    # plt.savefig(config['output_folder'] + 'flood_map_' + file_label + '.png')
    # plt.show()
    # plt.close()
    #

def plot_correlation_adc_vs_toa(df, config, file_suffix):
    # selection = (df[adc_col_list] > 200).any(axis=1)

    board = config['board'][0]
    board_config = config['config_B%d' % board]

    adc_gain = 'low'
    # adc_gain = 'high'
    cluster_range = [slice(0, 13), slice(13, 13+16), slice(13+16, 13+16+16), slice(13+16+16, 13+16+16+16)]
    color_list= ['blue', 'red', 'orange', 'green']
    for cluster in range(4):

        ASIC_channel_selection = board_config['really_injected_ASIC_channels'][0][cluster_range[cluster]]
        print('Cluster %d ASIC_channel_selection '%cluster, ASIC_channel_selection)
        adc_col_list = ['adc'+'_%s_ch%d_B%d' % (adc_gain, channel, board) for channel in ASIC_channel_selection]
        tdc_has_triggered_col_list = ['tdc_data_valid' + '_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channel_selection]
        time_variable = 'toa_ns'
        time_variable = 'cpt' # lsb_cpt
        time_col_list = [time_variable+'_%s_ch%d_B%d'%('low', channel, board) for channel in ASIC_channel_selection]

        # Substract min arrival TOA per frame
        # CASE 1 : taking the min TOA
        # min_TOA_per_frame = df[time_col_list].replace(0, np.nan).min(axis=1, skipna=True).replace(np.nan, 0)
        # df[time_col_list] = df[time_col_list].sub(min_TOA_per_frame, axis=0)

        # CASE 2 (better): take the TOA of the highest energy event
        # highest_energy_channel = [int(col[10:11])-3 if '_' in col[10:12] else int(col[10:12])-3 for col in df[adc_col_list].replace(0, np.nan).idxmax(axis=1, skipna=True).values]
        # df["TOA_highest_NRJ_col"] = ['toa_ns'+col[3:] for col in df[adc_col_list].replace(0, np.nan).idxmax(axis=1, skipna=True).values]
        df[time_variable+"_highest_NRJ_col"] = [time_variable+col[3:] for col in df[adc_col_list].replace(0, np.nan).idxmax(axis=1, skipna=True).values]
        idx, cols = pd.factorize(df[time_variable+'_highest_NRJ_col'])
        time_highest_NRJ_per_frame = df.reindex(cols, axis=1).to_numpy()[np.arange(len(df)), idx]
        df[time_col_list] = df[time_col_list].sub(time_highest_NRJ_per_frame, axis=0)

        # Flatten dataframe to one long array (channels per frame are concatenated frame by frame)
        time_array = df[time_col_list].stack().to_numpy()
        hit = df[tdc_has_triggered_col_list].stack().to_numpy()
        adc = df[adc_col_list].stack().to_numpy()

        time_array = time_array[hit]
        adc = adc[hit]
        plt.scatter(time_array, adc, s=2, label='Cluster %d'%cluster) #marker='.', color=color_list[cluster]

        # # Calculate the point density
        # xy = np.vstack([toa_ns, adc])
        # z = gaussian_kde(xy)(xy)
        # idx = z.argsort() # Sort the points by density, so that the densest points are plotted last
        # toa_ns, adc, z = toa_ns[idx], adc[idx], z[idx]
        # plt.scatter(toa_ns, adc, c=z, s=50)
    # plt.title("Cluster %d"%cluster)
    plt.title("For all 4 clusters, merged based on MSB CPT")
    plt.ylabel("Energy - pedestal [adc]")
    plt.xlabel("Relative lsb cpt arrival [ns] (assuming first arrived event has highest energy) ")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['save_folder'] + '../' + file_suffix + 'correlation_adc_vs_toa_%s.png'%adc_gain)
    plt.show()
    plt.close()

def plot_correlation_ch_vs_cpt(df, config, file_suffix):
    # selection = (df[adc_col_list] > 200).any(axis=1)

    board = config['board'][0]
    board_config = config['config_B%d' % board]

    gain = 'low'
    # adc_gain = 'high'
    ASIC_channel_selection = np.array(board_config['really_injected_ASIC_channels'])
    # adc_col_list = ['adc'+'_%s_ch%d_B%d' % (gain, channel, board) for channel in ASIC_channel_selection]
    tdc_has_triggered_col_list = ['tdc_data_valid' + '_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channel_selection]
    # toa_ns_col_list = ['toa_ns_%s_ch%d_B%d'%('low', channel, board) for channel in ASIC_channel_selection]
    cpt_col_list = ['cpt_%s_ch%d_B%d'%('low', channel, board) for channel in ASIC_channel_selection]

    # Substract min arrival TOA per frame
    # min_cpt_per_frame = df[cpt_col_list].replace(0, np.nan).min(axis=1, skipna=True).replace(np.nan, 0)
    # df[cpt_col_list] = df[cpt_col_list].sub(min_cpt_per_frame, axis=0)

    for i, row in df.iterrows():
        hit = row[tdc_has_triggered_col_list].values
        cpt = row[cpt_col_list][hit]
        hit_channels = ASIC_channel_selection[hit.tolist()]
        if len(hit_channels)==0:
            continue # no channel hit, strange conversion happenned !?
        if len(np.unique(cpt))<3:
            continue # not erroneous case
        plt.scatter(cpt, hit_channels, marker='.', color='blue')
        plt.title(f"Acquistion : OVF counter = {row.CPT>>14:^#04x}   CPT = {(row.CPT & 0b11_1111_1111_0000)>>4:^#04x}")
        plt.ylabel("Channel")
        plt.xlabel("cpt [lsb]")
        plt.grid()
        plt.tight_layout()
        plt.savefig(config['save_folder'] + '../' + file_suffix + 'correlation_ch_vs_cpt_%s.png' % gain)
        plt.show()
        # plt.close()

    # Flatten dataframe to one long array (channels per frame are concatenated frame by frame)
    # cpt = df[cpt_col_list].stack().to_numpy()
    # hit = df[tdc_has_triggered_col_list].stack().to_numpy()
    # adc = df[adc_col_list].stack().to_numpy()
    # ch = np.array([ASIC_channel_selection]*len())

    # cpt = cpt[hit]
    # toa_ns = toa_ns[hit]
    # adc = adc[hit]


    # # Calculate the point density
    # xy = np.vstack([toa_ns, adc])
    # z = gaussian_kde(xy)(xy)
    # idx = z.argsort() # Sort the points by density, so that the densest points are plotted last
    # toa_ns, adc, z = toa_ns[idx], adc[idx], z[idx]
    # plt.scatter(toa_ns, adc, c=z, s=50)



def plot_correlation_lsb_vs_toa(df, config, file_suffix):
    # selection = (df[adc_col_list] > 200).any(axis=1)
    mpl.rcParams['savefig.directory'] = config['save_folder']+'../'+file_suffix+'/'
    mpl.rcParams['savefig.format'] = 'png'

    board = config['board'][0]
    board_config = config['config_B%d' % board]

    ASIC_channel_selection = board_config['really_injected_ASIC_channels']
    lsb_col_list = ['lsb_fromCAL'+'_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channel_selection]
    tdc_has_triggered_col_list = ['tdc_data_valid' + '_%s_ch%d_B%d' % ('low', channel, board) for channel in ASIC_channel_selection]

    hit = df[tdc_has_triggered_col_list].stack().to_numpy()
    lsb_stack = (df[lsb_col_list] * 1e3).stack()[hit]

    ck_period = 1e6 / tempo_dig_ck

    for meas in ['toa', 'cal']:
        plt.figure(0)
        meas_col_list = [meas+'_%s_ch%d_B%d'%('low', channel, board) for channel in ASIC_channel_selection]

        # Flatten dataframe into one long array (channels per frame are concatenated frame by frame)
        meas_stack = df[meas_col_list].stack()[hit]
        plt.scatter(lsb_stack.to_numpy(), meas_stack.to_numpy(), marker='.', color='blue', label=meas +' raw hits')

        # Caracterise TDC border effect and actual delay line length
        a = pd.concat([lsb_stack.reset_index(drop=True), meas_stack.reset_index(drop=True)],
                  axis=1, keys=['lsb', meas])
        a = a[a[meas]!=0].groupby('lsb')[meas]
        meas_min_vs_lsb = a.min()
        meas_max_vs_lsb = a.max()
        plt.plot(meas_min_vs_lsb)
        plt.plot(meas_max_vs_lsb)

        plt.figure(1)
        plt.plot((meas_max_vs_lsb-meas_min_vs_lsb)*a.min().index, label=meas, marker='o')

        plt.figure(2)
        plt.plot((ck_period/(meas_max_vs_lsb-meas_min_vs_lsb)-a.min().index)/a.min().index*100, label=meas, marker='o')


    plt.xlabel("TDC lsb from CAL [ps]")
    plt.ylabel("Ideal lsb relative error [%]")
    plt.grid()
    plt.legend()
    plt.title("What should be the ideal TDC lsb ?\nto match delay line length = %.1f ns"%(ck_period/1e3))
    plt.tight_layout()
    plt.savefig(config['save_folder'] + '../' + file_suffix + '/'+ 'TDC_lsb_should_be_vs_lsb_fromCAL.png')
    plt.close()

    plt.figure(1)
    plt.xlabel("TDC lsb from CAL [ps]")
    plt.ylabel("Delay line length [ps]")
    plt.axhline(ck_period, linestyle='--', color='red', label='Theory at %d MHz'%tempo_dig_ck)
    plt.ylim([0.96*ck_period, 1.01*ck_period])
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['save_folder'] + '../' + file_suffix + '/'+ 'TDC_delay_line_length_vs_lsb_fromCAL.png')
    plt.close()

    plt.figure(0)
    plt.xlabel("TDC lsb from CAL [ps]")
    plt.ylabel("toa (below) & cal (above) [lsb]")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['save_folder'] + '../' + file_suffix + '/'+ 'TDC_vs_lsb_fromCAL.png')
    plt.close()

    # plt.show()


def generate_report(config):

    post_analysis_config_file = config["save_folder"]+'config_post_analysis.yaml'
    if os.path.exists(post_analysis_config_file):
        with open(post_analysis_config_file, 'r') as outfile:
            config = yaml.safe_load(outfile)
        outfile.close()
    cluster_stats_df = pd.read_csv(config['stats_filepath'])

    report_folder = config["save_folder"]+"../report/"
    if os.path.exists(report_folder):
        shutil.rmtree(report_folder)
    os.makedirs(report_folder)

    geometry_options = {"tmargin": "1cm", "lmargin": "1cm"}
    doc = Document(documentclass='article', geometry_options=geometry_options)
    doc.preamble.append(
        Command("title", "Serial tests report of evaluation board v1 B" + str(config['board'])))
    doc.preamble.append(Command("author", "Maxime Morenas (Weeroc)"))
    doc.preamble.append(Command("date", NoEscape(r"\today")))
    doc.append(NoEscape(r"\maketitle"))

    doc.packages.append(Package('booktabs'))
    doc.packages.append(Package('float'))

    # SCURVE
    with doc.create(Section("S-curve")):
        doc.append("Discriminator trigger efficiency as a function of its global threshold, once aligned (localDAC correction of the global threshold"
                   " is applied channel-wise). ")

        for board in config['board']:
            scurve_filepath = config["save_folder"] + f'../../../../B{board}/**/**/B{board}_calib_discri.csv'
            scurve_filepath = glob.glob(scurve_filepath)

            if len(scurve_filepath) == 0:
                print("No scurve results for board B%d"%board)
                continue
            elif not os.path.exists(scurve_filepath[0]):
                print("No scurve results for board B%d"%board)
                continue
            # Pick one result
            creation_time = time.ctime(os.path.getctime(scurve_filepath[0]))
            scurve_root_folder = os.path.dirname(scurve_filepath[0])

            with doc.create(Subsection("B%d "%board)):
                doc.append("Data taking: %s"%creation_time)
                doc.append("\nData folder: " + scurve_root_folder)

                with doc.create(Figure(position="H")) as figure:
                    for discri in ['TL', 'TH']:
                        filename = "3_dacLocal_channelwise_"+discri+"_trigger_efficiency_map"
                        image_filename = os.path.abspath(scurve_root_folder + '/' + filename + '.png')
                        with doc.create(SubFigure(position="b", width=NoEscape(r"0.5\linewidth"))) as sub_fig:
                            sub_fig.add_image(image_filename, width=NoEscape(r"\linewidth"))
                            sub_fig.add_caption(discri)
                    figure.add_caption("B%d trigger efficiency map: channel vs discriminator threshold"%board)
                doc.append("Channels that never trigger (blue line) are considered dead (Preamplifier or discriminator manufacturing default). ")
                doc.append("\n")

                for discri in ['TL', 'TH']:
                    filename = discri+'_thresholds'
                    image_filename = os.path.abspath(scurve_root_folder + '/'  + filename + '.png')
                    with doc.create(Figure(position="H")) as figure: #!htb
                        figure.add_image(image_filename, width=NoEscape(r"0.8\linewidth"))
                        figure.add_caption("B%d "%board+filename.replace('_', ' '))
                doc.append("NB: Threshold misalignment is a known ASIC default for this version (v2) due to the limited range of the local DAC (in orange). ")
                doc.append("\n")

            doc.append("  ")

    creation_time = time.ctime(os.path.getctime(config["save_folder"]+'config.yaml'))
    with doc.create(Section("Data taking: "+creation_time)):
        doc.append("Test type: \n" + config['test'])
        doc.append("\nRaw data can be found on " + os.environ['COMPUTERNAME'])
        doc.append("\n" + os.path.abspath(config['save_folder']))

        # for board in config['board']:
        #     board_config = config['config_B%d'%board]

        with doc.create(Subsection("Data merging statistics")):
            doc.append("Data are merged based on CPT = {time;msb_cpt} where time is the overflow counter located in"
                       " the FPGA and msb_cpt the 10-bit msb coarse counter in TEMPOROC2")

            for board in config['board']:
                doc.append(
                    f"\nBetween clusters of B{board:d}: {config['merge_success_count_B%d' % board]} ({config['merge_success_%%_B%d' % board]:d} %) successfully merged events")
            if len(config['board']) > 1:
                doc.append(f"\nBetween boards : {config['merge_success_count']} ({config['merge_success_%%']:d} %) successfully merged events")

            doc.append("\n\nEvents removed because identified as :")
            frame_error_list = set(cluster_stats_df.columns) ^ {'raw_event_count', 'exploitable_event_count', 'len_after_merging', 'cluster', 'injected_channels', 'file'}
            for frame_error in frame_error_list:
                with doc.create(Subsubsection(frame_error)):
                    with doc.create(Itemize()) as itemize:
                        for i, cluster in enumerate(cluster_stats_df['cluster']):
                            init_len = cluster_stats_df['raw_event_count'].iloc[i]
                            retriggering_frames_count = cluster_stats_df[frame_error].iloc[i]
                            retriggering_frames_percent = retriggering_frames_count / init_len * 100
                            filename = cluster_stats_df['file'].iloc[i]
                            itemize.add_item(f"{filename}: {retriggering_frames_count:d} ({retriggering_frames_percent:.2f} %) ")


            with doc.create(Subsubsection("Initial -> final frame count")):
                with doc.create(Itemize()) as itemize:
                    for i, cluster in enumerate(cluster_stats_df['cluster']):
                        init_len = cluster_stats_df['raw_event_count'].iloc[i]
                        final_len = cluster_stats_df["len_after_merging"].iloc[i]
                        filename = cluster_stats_df['file'].iloc[i]
                        itemize.add_item(f"{filename}: {init_len:d} -> {final_len:d} ")

            with doc.create(Subsubsection("Frame acquisition rate")):
                filename = f'Frame_acquisition_rate'
                image_filename = os.path.abspath(config['save_folder'] + '../' + filename + '.png')
                with doc.create(Figure(position="!htb")) as figure:
                    figure.add_image(image_filename, width=NoEscape(r"0.8\linewidth"))
                    figure.add_caption(filename.replace('_', ' '))

        with doc.create(Subsection("MSB CPT errors")):
            for board in config['board']:
                doc.append(f"For board B{board:d}: {config['CPT_matching_error_count_B%d' % board]} CPT matching errors")
                with doc.create(Itemize()) as itemize:

                    for error in ['CPT_found_in_3clusters_out_of_4_count']:
                        error_count = config[error+'_B%d' % board]
                        final_len = cluster_stats_df["len_after_merging"].iloc[i]
                        error_percent = error_count/final_len * 100
                        itemize.add_item(f"{error_count:d}  ({error_percent:.1f} %) "+error)

        # ADD SPECIFIC PART
        CTR_results = config['save_folder'] + '../CTR.csv'
        if os.path.exists(CTR_results) & (config['test']=="CTR between 2 boards with external trigger "):
            with doc.create(Subsection("CTR results with ext trigger")):
                doc.append("Allows to determine the best possible achievable CTR taking all jitter contributions due to TDC, "
                           "clocks, digital readout activity but not the analog front-end. ")
                df = pd.read_csv(CTR_results)

                # remove all _ for latex
                df_tmp = df[['boardA','channelA','gainA','boardB','channelB','gainB','CTR_FWHM_ps_Gaussian']].copy()
                df_tmp = df_tmp.rename(columns={'CTR_FWHM_ps_Gaussian':'CTR FWHM ps Gaussian'})  # : 'CTR FWHM ps std'  'time_conversion_method':'time conversion method',

                for time_conversion_method in np.unique(df['time_conversion_method']):
                    selection = df['time_conversion_method'] == time_conversion_method
                    doc.append("Time conversion method: "+time_conversion_method+":\n\n")
                    doc.append(NoEscape(df_tmp[selection].to_latex(index=False,formatters={"name": str.upper}, float_format="{:.1f}".format)))
                    doc.append(NoEscape(r"\newline"))

            # time_conversion_method = 'lsb_fromCAL'
            time_conversion_method = 'DNL_TOA_fraction'

            with doc.create(Subsubsection("Best result between channels of the same board")):
                for board in np.unique(df['boardA']):
                    selection = ((df['time_conversion_method']==time_conversion_method)
                                & (df['boardA']==board)
                                & (df['boardB']==board))
                    gainA = df.loc[selection, 'gainA'].iloc[0]
                    channelA = df.loc[selection, 'channelA'].iloc[0]
                    boardA = df.loc[selection, 'boardA'].iloc[0]
                    gainB = df.loc[selection, 'gainB'].iloc[0]
                    channelB = df.loc[selection, 'channelB'].iloc[0]
                    boardB = df.loc[selection, 'boardB'].iloc[0]
                    filename = f'CTR_{gainA}_ch{channelA}_B{boardA}_{gainB}_ch{channelB}_B{boardB}_{time_conversion_method}'
                    image_filename = os.path.abspath(config['save_folder']+'../CTR/'+filename+'_zoom.png')
                    with doc.create(Figure(position="!htb")) as figure:
                        figure.add_image(image_filename, width="320px")
                        figure.add_caption(filename.replace('_', ' '))

            with doc.create(Subsubsection("Best CTR between 2 boards")):
                selection = ((df['boardA']!=df['boardB']) & (df['time_conversion_method']==time_conversion_method))
                best_index = df.loc[selection].index[df.loc[selection, 'CTR_FWHM_ps_Gaussian']==df.loc[selection, 'CTR_FWHM_ps_Gaussian'].min()][0]

                gainA = df['gainA'].iloc[best_index]
                channelA = df['channelA'].iloc[best_index]
                boardA = df['boardA'].iloc[best_index]
                gainB = df['gainB'].iloc[best_index]
                channelB = df['channelB'].iloc[best_index]
                boardB = df['boardB'].iloc[best_index]
                filename = f'CTR_{gainA}_ch{channelA}_B{boardA}_{gainB}_ch{channelB}_B{boardB}_{time_conversion_method}'
                image_filename = os.path.abspath(config['save_folder']+'../CTR/'+filename+'_zoom.png')
                with doc.create(Figure(position="!htb")) as figure:
                    figure.add_image(image_filename, width="320px")
                    figure.add_caption(filename.replace('_', ' '))


    try:
        doc.generate_pdf(config['output_folder'] + "report/serial_test_report") #, compiler='pdfLaTex')
        os.startfile(os.path.abspath(config['output_folder'] + "report/serial_test_report.pdf"))
    except:
        print("Failed to generate report: check TeX Live install.")


def generate_report_DC_comparison(output_folder, search_string):

    report_folder = output_folder+'/report/'
    if not os.path.exists(report_folder):
        os.makedirs(report_folder)
    previous_report_filepath = report_folder+'serial_test_report_DC_comparison.pdf'
    if os.path.exists(previous_report_filepath):
        shutil.rmtree(previous_report_filepath)
        # shutil.rmtree(report_folder)

    geometry_options = {"tmargin": "1cm", "bmargin": "1cm", "lmargin": "1cm", "rmargin": "1cm"}
    doc = Document(documentclass='article', geometry_options=geometry_options)
    doc.packages.append(Package('placeins'))
    doc.preamble.append(
        Command("title", "Serial tests report of evaluation board v1 DC points comparison"))
    doc.preamble.append(Command("author", "Maxime Morenas (Weeroc)"))
    doc.preamble.append(Command("date", NoEscape(r"\today")))
    doc.append(NoEscape(r"\maketitle"))

    doc.append("Raw data can be found on " + os.environ['COMPUTERNAME'])
    doc.append("\n" + os.path.abspath(output_folder))

    doc.append("\nFor serial tests, the digital runs at 80 MHz in full_adc_tdc RO mode "
               "(the longest possible serialised frame)")

    with doc.create(Section("ASIC power consumption")):
        with doc.create(Subsection("Static power conso")):
            doc.append("Asic ON after reset with 80 MHz clock running without any injection.\n")
            with doc.create(LongTable("r c c c ")) as table:
                table.add_hline()
                table.add_row(('Board', 'Analog [mW]', 'Digital [mW]', 'Measurement date'))
                table.add_hline()
                table.end_table_header()

                csv_files = glob.glob(search_string+'conso*.csv')
                for csv_file in csv_files:
                    df = pd.read_csv(csv_file)
                    board = int(re.findall("(?<=\\B)[0-9]+", csv_file)[0])
                    selection = df['conditions']=='asic on after reset with 80 MHz clock'
                    analog_power = "%d" % (df.loc[selection, 'analog_current'].iloc[0]*1.2)
                    digital_power = "%d" % (df.loc[selection, 'digital_current'].iloc[0]*1.35)
                    creation_time = time.ctime(os.path.getctime(csv_file))
                    table.add_row((board, analog_power, digital_power, creation_time))
                    # table.add_hline()
                table.end_table_footer()
                table.add_hline()

        with doc.create(Subsection("Dynamic analog conso")):
            doc.append("A variable number of channels are injected at a 200 kHz pace (8/32/64 evenly spaced channels injected with external trigger) such as all 4 clusters always convert & serialise data. ")

            filename = 'ASIC_analog_conso_vs_channels'
            image_filename = os.path.abspath(output_folder+ filename+'.png')
            with doc.create(Figure(position="!htb")) as figure:
                figure.add_image(image_filename, width="320px")
                figure.add_caption(filename.replace('_', ' '))
            doc.append(NoEscape(r"\FloatBarrier")) # to force position figure within subsection

        with doc.create(Subsection("Dynamic digital conso")):
            doc.append("Digital power conso is constant with the number of channels to readout. "
                       "NB: Digital power conso is also unchanged if only one cluster (out of 4) works.")
            filename = 'ASIC_digital_conso_vs_channels'
            image_filename = os.path.abspath(output_folder + filename + '.png')
            with doc.create(Figure(position="!htb")) as figure:
                figure.add_image(image_filename, width="320px")
                figure.add_caption(filename.replace('_', ' '))
            doc.append(NoEscape(r"\FloatBarrier"))

        with doc.create(Subsection("ASIC conso vs frequency")):
            with doc.create(Subsubsection("Extract TDC dynamic conso from analog")):
                doc.append("TDC are connected to analog power supply. All 128 TDC are injected simultaneously. ")
                doc.append("Consumption increases linearly with the injection frequency. "
                           "The only limit to frequency injection rate is the TDC dead time (7 clock periods = 87.5 ns = 11.5 MHz) "
                           "as triggers are unlatched internally (digital RO is not possible, thus no TDC data). Above this frequency limit "
                           "the consumption saturates. ")

                filename = 'analog_current_vs_freq'
                image_filename = os.path.abspath(output_folder + filename + '.png')
                with doc.create(Figure(position="!htb")) as figure:
                    figure.add_image(image_filename, width=NoEscape(r"0.8\linewidth"))
                    figure.add_caption(filename.replace('_', ' '))
                doc.append(NoEscape(r"\FloatBarrier"))
                doc.append("The 128 TDC conso rises by about 10 µA per kHz of injection.")

            with doc.create(Subsubsection("Digital conso")):
                doc.append("The trigger latch is operated without any latch, thus the digital is not working normally.")

                filename = 'digital_current_vs_freq'
                image_filename = os.path.abspath(output_folder + filename + '.png')
                with doc.create(Figure(position="!htb")) as figure:
                    figure.add_image(image_filename, width=NoEscape(r"0.8\linewidth"))
                    figure.add_caption(filename.replace('_', ' '))
                doc.append(NoEscape(r"\FloatBarrier"))

        with doc.create(Section("InputDAC")):

            filename = 'InputDAC_mV_range_vs_channel'
            image_filename = os.path.abspath(output_folder + filename + '.png')
            with doc.create(Figure(position="!htb")) as figure:
                figure.add_image(image_filename, width=NoEscape(r"0.9\linewidth"))
                figure.add_caption(filename.replace('_', ' '))
            doc.append(NoEscape(r"\FloatBarrier"))

        with doc.create(Section("Bandgap voltage reference (ASIC internal)")):
            doc.append("Find best configuration value for Vbias_1V to equal 1V. BG is fixed at 8 dac here. "
                       "BG value should be tuned with temperature test for each ASIC if the ASIC operating "
                       "temperature is not stable.")

            filename = 'Vbias1V_vs_dac'
            image_filename = os.path.abspath(output_folder + filename + '.png')
            with doc.create(Figure(position="!htb")) as figure:
                figure.add_image(image_filename, width="320px")
                figure.add_caption(filename.replace('_', ' '))
            doc.append(NoEscape(r"\FloatBarrier"))



            with doc.create(Subsection("Voltage values for Vbg (dac=8) and temp (diode connected)")):
                with doc.create(LongTable("r c c c ")) as table:
                    table.add_hline()
                    table.add_row(('board', 'BG_mV_avg', 'temp_mVa_vg', 'Measurement date'))
                    table.add_hline()
                    table.end_table_header()

                    csv_files = glob.glob(search_string+'BG_dac_range*.csv')
                    for csv_file in csv_files:
                        df = pd.read_csv(csv_file)
                        board = int(re.findall("(?<=\\B)[0-9]+", csv_file)[0])
                        BG_mV_avg = "%.1f"%df['BG_mV'].mean()
                        temp_mVa_vg = "%.1f"%df['temp_mV'].mean()
                        creation_time = time.ctime(os.path.getctime(csv_file))
                        table.add_row((board, BG_mV_avg, temp_mVa_vg, creation_time))
                        # table.add_hline()
                    table.end_table_footer()
                    table.add_hline()

        with doc.create(Section("Discriminator threshold sweep")):

            with doc.create(Subsection("Vth1")):
                doc.append("The full DAC range is swept.")
                filename = 'Vth1_vs_channel'
                image_filename = os.path.abspath(output_folder + filename + '.png')
                inl_image_filename = os.path.abspath(output_folder + 'INL_'+ filename + '.png')

                with doc.create(Figure(position="!htb")) as figure:
                    # figure.add_image(image_filename, width="320px")
                    # figure.add_caption(filename.replace('_', ' '))
                    # figure.add_image(inl_image_filename, width="320px")
                    # figure.add_caption("INL " + filename.replace('_', ' '))
                    with doc.create(SubFigure(position="b", width=NoEscape(r"0.5\linewidth"))) as left_fig:
                        left_fig.add_image(image_filename, width=NoEscape(r"\linewidth"))
                        left_fig.add_caption("Linearity")

                    with doc.create(SubFigure(position="b", width=NoEscape(r"0.5\linewidth"))) as right_fig:
                        right_fig.add_image(inl_image_filename, width=NoEscape(r"\linewidth"))
                        right_fig.add_caption("INL")

                figure.add_caption(filename.replace('_', ' '))
                doc.append(NoEscape(r"\FloatBarrier"))
                doc.append("Abnormal constant discriminator threshold voltage for board B5 is probably "
                           "a wrong bonding between the testpoint and the BGA.")


            with doc.create(Subsection("VthQ")):
                doc.append("The full DAC range is swept. Saturation due to the 1.2 V power supply rail.\n")
                filename = 'VthQ_vs_channel'
                image_filename = os.path.abspath(output_folder + filename + '.png')
                inl_image_filename = os.path.abspath(output_folder + 'INL_'+ filename + '.png')
                # with doc.create(Figure(position="!htb")) as figure:
                #     figure.add_image(image_filename, width="320px")
                #     figure.add_caption(filename.replace('_', ' '))
                with doc.create(Figure(position="h!")) as figure:
                    with doc.create(SubFigure(position="b", width=NoEscape(r"0.5\linewidth"))) as left_fig:
                        left_fig.add_image(image_filename, width=NoEscape(r"\linewidth"))
                        left_fig.add_caption("Linearity")
                    with doc.create(SubFigure(position="b", width=NoEscape(r"0.5\linewidth"))) as right_fig:
                        right_fig.add_image(inl_image_filename, width=NoEscape(r"\linewidth"))
                        right_fig.add_caption("INL")
                    figure.add_caption(filename.replace('_', ' '))

                doc.append(NoEscape(r"\FloatBarrier"))

    doc.generate_tex(report_folder + "serial_test_report_DC_comparison")
    doc.generate_pdf(report_folder+ "serial_test_report_DC_comparison")

    os.startfile(os.path.abspath(report_folder + "serial_test_report_DC_comparison.pdf"))


