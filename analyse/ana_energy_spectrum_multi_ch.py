import re, os, glob
import numpy as np
import pandas as pd
from colorsys import rgb_to_hsv, hsv_to_rgb
import yaml
from matplotlib import pyplot as plt
from scipy.signal import argrelextrema, argrelmin, argrelmax
import matplotlib as mpl
from scipy.stats import gaussian_kde

from analyse.common_analysis import *

# from common_analysis import *

mpl.use("TkAgg")
# from analysis_TDC import *
# from analyse_ADC import *
# from common_data_decoding import *

from analyse.common_analysis_TDC import *
from analyse.common_analyse_ADC import *
from analyse.common_data_decoding import *


def plot_staircase(local_output_dir):

    folder = os.path.dirname(local_output_dir)
    folder_index_str = re.findall("[0-9]+(?=/raw)", folder)
    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ")
        return

    config_file = folder + "/config.yaml"
    with open(config_file, "r") as outfile:
        config = yaml.safe_load(outfile)

    thres_scan_df_filename = (
        local_output_dir
        + "B%d_trigger_counting_threshold_scan.csv" % (config["board"][0])
    )
    thres_scan_df = pd.read_csv(thres_scan_df_filename)
    gain = "TL"
    plt.figure(figsize=(14, 8))

    not_nan_selection = ~(thres_scan_df.loc[:, gain + "_dac"].isna())
    for channel in config["injected_channel"][0]:
        selection = thres_scan_df.channel == channel
        thres_dac = thres_scan_df.loc[selection & not_nan_selection, gain + "_dac"]
        counts = thres_scan_df.loc[selection & not_nan_selection, gain + "_freq"]

        plt.plot(thres_dac, counts, label="ch%d" % channel)
    plt.grid()
    plt.legend()
    plt.yscale("log")
    # plt.title(gain + ' threshold scan')

    # plt.suptitle("Channel %d" % channel)
    plt.tight_layout()
    # plt.savefig(folder + 'ch%d.png' % channel)
    plt.show()
    pass


def analyse_pedestal(root_folder, search_folder):
    file_suffix = "_pedestal"

    config = read_config(root_folder, search_folder, file_suffix=file_suffix)
    df0 = analyse_init(search_folder, config, file_suffix=file_suffix, merge_clusters_based_on="raw_file_index")
    # because ADC pedestal analysis don't care about TDC/time values

    if len(df0) == 0:
        print("No data")
        exit(0)

    board = config["board"][0]
    board_config = config["config_B%d" % board]
    injected_SiPM_channels = get_SiPM_ch(
        board_config["enable_TL_ASIC_ch"][0], board_config["SiPM_model"]
    )
    board_config["really_injected_ASIC_channels"] = [[int(ch) for ch in
        np.sort(get_ASIC_ch(injected_SiPM_channels, board_config["SiPM_model"]))]]

    board_config["not_injected_ASIC_channels"] = list(
        set(board_config["really_injected_ASIC_channels"][0])
        ^ set(board_config["enable_TL_ASIC_ch"][0])
    )

    pedestal_df = analyse_pedestal_core(df0, search_folder, config)

    selection = ((pedestal_df['gain']=='low')
                 & (pedestal_df['board']==board))
                 # & (pedestal_df['channel'].apply(lambda row: row in board_config["really_injected_ASIC_channels"][0])))

    pedestal_mean = pedestal_df.loc[selection, 'pedestal_mean']
    pedestal_std = pedestal_df.loc[selection, 'pedestal_std']

    return pedestal_mean, pedestal_std, config


def plot_22Na_spectrum(root_folder, search_folder):

    print(search_folder[len(root_folder) :])

    pedestal_mean, pedestal_std, config = analyse_pedestal(root_folder, search_folder)

    config["datapath_to_display"] = search_folder[len(root_folder) :]

    file_suffix_list = glob.glob(search_folder+'B*_22Na*.csv')
    # file_suffix_list = [os.path.basename(file)[19:-4] for file in file_suffix_list]
    file_suffix_list = ["_" + os.path.basename(file).split(".")[0].split("_")[-1] for file in file_suffix_list]
    file_suffix_list = glob.glob(search_folder + "B*_22Na*.csv")
    file_suffix_list = [os.path.basename(file)[19:-4] for file in file_suffix_list]
    file_suffix_list = np.unique(file_suffix_list)

    # file_suffix_list = ['_22Na_HV_57.0_palgGain_9_tauLG_2_patgain_32']
    # file_suffix_list = ['_22Na_HV_57.0_palgGain_9_tauLG_2_patgain_20']
    # file_suffix_list = file_suffix_list[8:]

    for file_suffix in file_suffix_list:
        print("Analysing :", file_suffix)

        analyse_data_with_source(root_folder, search_folder, file_suffix, pedestal_mean)


def analyse_data_with_source(root_folder, search_folder, file_suffix, pedestal_mean):

    # last_foldername = os.path.basename(os.path.normpath(search_folder+'../../'))
    config = read_config(root_folder, search_folder, file_suffix=file_suffix)

    df2_filepath = config['output_folder']  + "2" + file_suffix + ".feather"
    board = config["board"][0]
    board_config = config["config_B%d" % board]

    if not os.path.exists(df2_filepath):

        df = analyse_init(search_folder, config, file_suffix=file_suffix)
        if len(df) == 0:
            print("No data")
            exit(0)

        mpl.rcParams["savefig.directory"] = config['output_folder']
        mpl.rcParams["savefig.format"] = "png"

        channel_folder = config['output_folder'] + "/channel/"
        if not os.path.exists(channel_folder):
            os.makedirs(channel_folder)

        frame_folder = config['output_folder'] + "/frame/"
        if not os.path.exists(frame_folder):
            os.makedirs(frame_folder)

        # Substract pedestal
        not_injected_adc_col = [
            "adc_low_ch%d_B%d" % (ch, board)
            for ch in board_config["not_injected_ASIC_channels"]
        ]
        injected_adc_col = [
            "adc_low_ch%d_B%d" % (ch, board)
            for ch in board_config["really_injected_ASIC_channels"][0]
        ]
        df.drop(labels=not_injected_adc_col, axis="columns", inplace=True)
        pedestal_mean = pedestal_mean.iloc[board_config["really_injected_ASIC_channels"][0]].tolist()
        df[injected_adc_col] -= pedestal_mean

        # plot_lsb_vs_time_for_all_ch(df, config, board = board, plot=True)
        df = compute_ps_time_within_one_msb_cpt_for_all_channels(
            df, config, time_conversion_method="lsb_fromCAL"
        )  #'lsb_fromCAL_moving_avg')

        df.to_feather(df2_filepath)
    else:
        df = pd.read_feather(df2_filepath)

    if "light_source" not in board_config:
        board_config["light_source"] = board_config["crystal"]

    if board_config["light_source"] == "CeBr3_quartz_encapsulated":
        analysis_for_CeBr3(df, config, file_suffix)
    elif board_config["light_source"] == "full_segmented_alu_coated_LYSO":
        analysis_for_large_LYSO(df, config, file_suffix)
    else:
        print("Analysis steps for such light source are yet to be implemented ! :)"
              "\nLet's try without cutting any data...")
        df, threshold_dict = plot_spectrum_sum_channels(df, config, file_suffix)
        # plot_map_of_mean_frame(df, config)
        plot_flood_map2(df, config, threshold_dict)


        plot_map_of_each_frame(df, config, file_suffix, threshold_dict)

        plot_spectrum_per_channel(df, config, file_suffix)

def analysis_for_CeBr3(df, config, file_suffix):
    plot_correlation_adc_vs_toa(df, config, file_suffix)

    # plot_correlation_ch_vs_cpt(df, config, file_suffix)
    # plot_frame_by_frame(df, config, file_suffix)
    # plot_correlation_adc_vs_toa(df, config, file_suffix)
    # plot_correlation_lsb_vs_toa(df, config, file_suffix)
    # plot_tdc_histo(df, config, file_suffix)

    plot_spectrum_sum_channels(df, config, file_suffix)

    plot_spectrum_sum_channels_gain_corrected_for_CeBr3(df, config, file_suffix)


    # plot_flood_map(df, config)


def analysis_for_large_LYSO(df, config, file_suffix):

    board = config["board"][0]
    board_config = config["config_B%d" % board]
    injected_adc_col = [
        "adc_low_ch%d_B%d" % (ch, board)
        for ch in board_config["really_injected_ASIC_channels"][0]
    ]
    # df2_filepath = output_folder + '2' + file_suffix + '.feather'
    #     if not os.path.exists(df2_filepath):
    # Hide all energies below energy cut

    new_cols = {}
    for col in injected_adc_col:
        new_cols[col] = df[col] * (df[col] >= 10)
    df.drop(labels=list(new_cols.keys()), axis="columns", inplace=True)
    df = pd.concat([df, pd.DataFrame(new_cols)], axis=1)

    # energy_cut = 5
    # energy_cut = 50
    energy_cut = 100
    # # energy_cut = 200
    energy_selection = (df[injected_adc_col] > energy_cut).any(axis=1)
    energy_selection_count = energy_selection.value_counts()[
        energy_selection.value_counts().index == True
    ].values
    energy_selection_count = energy_selection_count[0] if (energy_selection_count.size>0) else 0
    new_field = {
        "frame_%%_with_at_least_1ch_above_%d_adc_above_pedestal"
        % energy_cut: round(energy_selection_count / len(df) * 100)
    }
    print(new_field)
    board_config.update(new_field)
    df = df[energy_selection]
    # save_config_file_copy(config)

    # df.to_feather(df2_filepath)
    # else:
    #     df = pd.read_feather(df2_filepath)

    # plot_map_of_each_frame_compare_TDC(df, config, file_suffix)

    plot_spectrum_sum_channels(df, config, file_suffix)

    # for channel in [29]:
    #     plt.figure(figsize=(9, 7))
    #     col_label = 'adc_%s_ch%d' % ('low', channel)
    #     # serie = df.loc[(df['photopeak_selection']) & (df[col_label] == df[injected_adc_col].max(axis=1)), :]
    #     # serie = df.loc[(df['photopeak_selection']), :]
    #     serie = df.loc[(df[col_label] == df[injected_adc_col].max(axis=1)), :]
    #     # serie = df
    #     bins = np.arange(serie[col_label].min(), serie[col_label].max() + 1, 10)
    #     counts, bins = np.histogram(serie[col_label], bins=bins)
    #     plt.stairs(counts, bins, color='darkcyan', fill=True,
    #                label=file_suffix[1:])  # remove _ otherwise ignore label legend
    #     # plt.yscale('log')
    #     plt.title(channel)
    #     plt.grid()
    #
    #     # plt.figure(figsize=(9, 7))
    #     # plt.scatter(serie.CPT, serie[col_label])
    #     # plt.grid()
    #
    #
    #     plt.show()

    plot_spectrum_per_channel_for_large_LYSO(df, config, file_suffix)

    return 0

    energy_cut = 600
    energy_selection = (df[adc_col_list] > energy_cut).any(axis=1)
    energy_selection_count = energy_selection.value_counts()[
        energy_selection.value_counts().index == True
    ].values
    energy_selection_count = energy_selection_count[0] if energy_selection_count else 0
    new_field = {
        "frame_%%_with_at_least_1ch_above_%d_adc_above_pedestal"
        % energy_cut: round(energy_selection_count / len(df) * 100)
    }
    board_config.update(new_field)
    print(new_field)
    # df['unique_CPT_count'] = df[['CPT_cluster_%d'%cluster for cluster in range(4)]].replace(0, np.nan).nunique(axis=1)
    # unique_CPT_pourcentage = {'%d'%i:int(count) for i, count in (df['unique_CPT_count'].value_counts()/len(df)*100).items()}
    # print('unique_CPT_pourcentage', unique_CPT_pourcentage)
    # config.update({'unique_CPT_pourcentage': unique_CPT_pourcentage})
    #
    # df['unique_msb_cpt_count'] = df[['msb_cpt_cluster_%d'%cluster for cluster in range(4)]].replace(0, np.nan).nunique(axis=1)
    # unique_CPT_pourcentage = {'%d'%i:int(count) for i, count in (df['unique_msb_cpt_count'].value_counts()/len(df)*100).items()}
    # print('unique_msb_cpt_pourcentage', unique_CPT_pourcentage)
    # config.update({'unique_msb_cpt_pourcentage': unique_CPT_pourcentage})

    save_config_file_copy(config)

    # plt.plot(df['unique_CPT_count'])
    # # plt.plot(pd.unique(df[['CPT_cluster_%d'%cluster for cluster in range(4)]]))
    # plt.grid()
    # plt.tight_layout()
    # plt.show()
    # return
    # df = correct_ADC_data_64ch(df, config)
    channels_to_study = board_config["injected_channel"][0]
    channels_to_study = [43]
    plt.show()

    if "small" in output_folder:
        ASIC_channel_selection = [33, 35, 41, 46, 28, 20, 25]  # inner 7 channels
        ASIC_channel_selection += [
            52,
            54,
            51,
            43,
            31,
            23,
            15,
            17,
            14,
            22,
            38,
            44,
        ]  # + ring channels around inner
        file_label = "inner_19_channels"
    else:
        file_label = "all_channels"
        ASIC_channel_selection = board_config["injected_channel"][0]

    energy_selection = (df[adc_col_list_selection] > 300).any(axis=1)
    plot_flood_map(df[energy_selection], config, ASIC_channel_selection, file_label)
    plot_tdc_histo(df, config, file_suffix)

    # plot_correlation_adc_vs_toa_photopeak_cluster(df, adc_col_list, config)

    # plot_map_of_each_frame(df, config, file_suffix)

    # plot_first_triggered_channel_count_map(df, config, file_suffix)

    # print(config['nb_trigger'])
    # print(len(config['enable_TL_ASIC_ch'][0]))

    # tdc_col_list = ['tdc_%s_ch%d'%(gain, channel) for channel in config['enable_TL_ASIC_ch'][0] for gain in ['low']]
    # print("rows with all ch tdc value null : ",(df[tdc_col_list]==0).all(axis=1).value_counts())
    # print("rows with at least 1 ch adc value above 350 : ", (df[adc_col_list]>350).any(axis=1).value_counts())
    # print("rows with at least 1 ch adc value above 200 : ", (df[adc_col_list]>200).any(axis=1).value_counts())

    # df = df[(df[adc_col_list]>350).any(axis=1)]

    # i_len = len(adc_col_list)
    # plt.subplots(i_len, i_len, figsize=(10, 8))
    # # for ci, col in enumerate(adc_col_list):
    # #     if col in df.columns:
    # #         plt.scatter(df.index, df[col], s = 2)
    # for i in range(i_len):
    #     for j in range(i_len):
    #         plt.subplot(i_len, i_len, i*i_len+j+1)
    #         plt.scatter(df[adc_col_list[i]], df[adc_col_list[j]], s = 2)
    #
    # plt.show()


def plot_spectrum_per_channel(df, config, file_suffix):

    board = config["board"][0]
    board_config = config["config_B%d" % board]


    for ci, channel in enumerate(board_config["really_injected_ASIC_channels"][0]):
        for gain in ["low", "high"]:
            label = file_suffix[6:]
            color = "darkturquoise"
            col_label = "adc_%s_ch%d_B%d" % (gain, channel, board)

            if col_label in df.columns:
                plt.figure(figsize=(9, 7))
                # plt.subplot(2, 1, ci+1)

                # all
                serie = df[col_label]
                if (serie.min() == serie.max()) or serie.isna().all():
                    print("Data %s seems wrong."%col_label)
                    print(serie)
                    continue
                step = 2**3
                bins = np.arange(serie.min(), serie.max() + step + 1, step)
                counts, bins = np.histogram(serie, bins=bins)
                plt.stairs(counts, bins, color=color, fill=True, label=label)

                plt.title(
                    "Energy spectrum for channel %d %s\n%s"
                    % (channel, gain, config["datapath_to_display"])
                )
                plt.xlabel("ADC [lsb]")
                plt.ylabel("Count")
                plt.grid()
                plt.xlim([-50, 1100])
                # plt.ylim([0, 130])
                plt.legend(prop={'size': 18})

                # plt.yscale("log")
                plt.tight_layout()
                plt.savefig(
                    config["output_folder"]
                    + "../"
                    + file_suffix
                    + "/channel/22Na_spectrum_ch%d_%s_%s.png" % (channel, gain, label)
                )
                # plt.show()
                plt.close()

            # for time_conversion_method in ['lsb_fromCAL', , 'DNL_TOA_fraction',
            #                                'DNL_TOA_calibrated_time']:

            # df = compute_ps_time_within_one_msb_cpt(df, config, channel, board, time_conversion_method='lsb_fromCAL_moving_avg')

            # col_label_low = "toa_ps_low_ch%d_B%d" % (channel, board)
            # col_label_high = "toa_ps_high_ch%d_B%d" % (channel, board)
            #
            # tot = df[col_label_high] - df[col_label_low]
            #
            # plt.figure(figsize=(10, 8))
            # # plt.scatter(serie, tot, marker='.')
            # plt.scatter(serie, df[col_label_low], marker='.')
            # # plt.yscale("log")
            # plt.tight_layout()
            # plt.show()
            # plt.close()
            #
            #
            # plt.figure(figsize=(10, 8))
            #
            # step = 20
            # bins = np.arange(tot.min(), tot.max() + step + 1, step)
            # counts, bins = np.histogram(tot, bins=bins)
            # plt.stairs(counts, bins, color=color, fill=True, label=label)
            #
            # # plt.title()
            # # plt.xlabel("ADC [lsb]")
            # # plt.ylabel("Count")
            # plt.grid()
            # # plt.xlim([-200, 1224])
            #
            # # plt.yscale("log")
            # plt.tight_layout()
            # plt.show()
            # plt.close()

    print("file:///"+(os.path.abspath(config["output_folder"]+ "../"+ file_suffix+ "/channel/")).replace('\\', '/'))

def plot_spectrum_per_channel_for_large_LYSO(df, config, file_suffix):

    photopeak_per_channel = (
        config["output_folder"] + "../" + file_suffix + "/photopeak_mean_per_channel.csv"
    )
    gain = 'high'
    board = config["board"][0]
    board_config = config["config_B%d" % board]
    if not os.path.exists(photopeak_per_channel):
        injected_adc_col = [
            "adc_%s_ch%d_B%d" % (gain, ch, board)
            for ch in board_config["really_injected_ASIC_channels"][0]
        ]
        res = {"channel": [], "photopeak_mean": []}  # , 'photopeak_std': []}

        # plt.subplots(2, 1, figsize=(10, 8))
        # for ci, channel in enumerate([43, 43]):
        for ci, channel in enumerate(board_config["really_injected_ASIC_channels"][0]):
            # for ci, channel in enumerate([8]):

            # if ci == 1:
            #     df = correct_ADC_data_64ch(df, config)
            #     label = 'corrected ADC value'
            #     color = 'darkturquoise'
            #     col_label = 'adc_%s_ch%d_corr' % ('low', channel)
            #
            # else:
            #     label = 'raw ADC value'
            #     color = 'darkblue'
            label = ""
            color = "darkturquoise"
            col_label = "adc_%s_ch%d_B%d" % (gain, channel, board)

            if col_label in df.columns:
                plt.figure(figsize=(10, 8))
                # plt.subplot(2, 1, ci+1)

                # all
                serie = df[col_label]
                step = 10
                bins = np.arange(serie.min(), serie.max() + step + 1, step)
                counts, bins = np.histogram(serie, bins=bins)
                plt.stairs(counts, bins, color=color, fill=True, label=label)

                res["channel"].append(channel)
                methodA = True
                if methodA:
                    serie = df.loc[
                        (df[col_label] == df[injected_adc_col].max(axis=1)), col_label
                    ]
                    # serie = df.loc[(df['photopeak_selection']) & (df[col_label]==df[injected_adc_col].max(axis=1)), col_label]
                    # serie = df.loc[(df['adc_sum_all_channels']>6000), col_label]
                    # serie = df.loc[df['photopeak_selection'], col_label]
                    # if (serie.max()-serie.min()) > 9:
                    # bins = np.arange(serie.min(), serie.max() + 1, 20)
                    # else:
                    # bins = 2
                    if len(serie) > 0:
                        bins = np.arange(serie.min(), serie.max() + 21, 20)
                        counts, bins = np.histogram(serie, bins=bins)
                        plt.stairs(counts, bins, color="darkblue", fill=True, label=label)
                        if len(counts) < 1:
                            pass
                        photopeak_index = np.argmax(counts)
                        photopeak = bins[photopeak_index]
                    else:
                        photopeak = 1
                else:
                    # serie = df.loc[(df[col_label] > 200) & (df[col_label] < (df[col_label].max()-50)), col_label]
                    if len(serie) < 100:
                        print(
                            "Not enough data for selection for channel %d : %d"
                            % (channel, len(serie))
                        )
                        res["photopeak_mean"].append(1)
                        # res['photopeak_std'].append(0)
                    else:
                        # bins = np.arange(serie.min(), serie.max() + 1, 60)
                        # counts, bins = np.histogram(serie, bins=bins)
                        # photopeak_index = np.argmax(counts)
                        photopeak_index = np.argmin(np.diff(counts[4:-2]))
                        photopeak = bins[4:-2][photopeak_index]

                plt.axvline(
                    photopeak,
                    color="blue",
                    linestyle="dashed",
                    label="\nmean photopeak = %d adc" % photopeak,
                )

                res["photopeak_mean"].append(photopeak)
                # if len(bins[photopeak_index:])<3:
                #     xmax = bins[-1]
                # else:
                #     xmax = bins[photopeak_index:][argrelmin(counts[photopeak_index:])[0][0]]
                # xmin = bins[:photopeak_index][argrelmin(counts[:photopeak_index])[0][-1]]
                #
                # try:
                #     p0 = [photopeak, (xmax - xmin) / 10, max(counts)]
                #     fitParam, cov = curve_fit(modelGauss, bins[photopeak_index - 5:photopeak_index + 5],
                #                               counts[photopeak_index - 5:photopeak_index + 5], p0=p0)
                #
                #     mu = fitParam[0]
                #     sigmaHisto = fitParam[1]
                #     ampHisto = fitParam[2]
                #     xmin = mu - 2 * sigmaHisto
                #     xmax = mu + 2 * sigmaHisto
                #     xfit = np.arange(xmin, xmax, (xmax - xmin) / 100)
                #     yfit = modelGauss(xfit, mu, sigmaHisto, ampHisto)
                #
                #     # resolution_FWHM2 = 2.35 * sigmaHisto * 1e3
                #     r1, r2, FWHM = half_max_x(xfit, yfit)
                #
                #     plt.plot(xfit, yfit, linestyle='-', color='red',
                #              label=r"$\Delta E/E$ " + '= %.0f %% FWHM' % (FWHM / mu * 100))
                # except:
                #     print("Error fit energy resolution")
                #     pass

                # max_adc = bins[80:][np.argmax(counts[80:])]
                # selection = (df[col_label] > (max_adc-20)) & (df[col_label] < (max_adc+20))
                # energy selection to compute calibration
                # serie = df.loc[df['photopeak_selection'], col_label]
                # serie = serie[serie > energy_cut]

                #
                #
                # bins = np.arange(serie.min(), serie.max() + 1, (serie.max()-serie.min())/300)
                # counts, bins = np.histogram(serie, bins=bins)
                #
                # if len(counts[bins[:-1] > 200])<2:
                #     res['photopeak_mean'].append(1)
                #     continue
                # channel_photopeak_mean = bins[:-1][bins[:-1] > 200][np.argmax(counts[bins[:-1] > 200])]
                # res['photopeak_mean'].append(channel_photopeak_mean)
                # # res['photopeak_std'].append(serie.std())
                #
                # plt.stairs(counts, bins, color='darkcyan', fill=True, label='photopeak selection from sum')

                plt.title(
                    "Energy spectrum for channel %d %s\n%s"
                    % (channel, gain, config["datapath_to_display"])
                )
                plt.xlabel("ADC [lsb]")
                plt.ylabel("Count")
                plt.grid()
                plt.xlim([-200, 1224])

                plt.yscale("log")
                # plt.axvline(pedestal_mean[ci], color='red', linestyle='dashed', label='pedestal mean')
                # plt.axvline(pedestal_mean[ci]+5*pedestal_std[ci], color='red', linestyle='-', label='pedestal mean + 5 sigma')
                plt.legend()
                plt.tight_layout()
                plt.savefig(
                    config["output_folder"]
                    + "../"
                    + file_suffix
                    + "/channel/22Na_spectrum_ch%d.png" % channel
                )
                plt.show()
                # if channel==43:
                #     plt.show()
                plt.close()

        photopeak_per_channel_df = pd.DataFrame(res)
        photopeak_per_channel_df.to_csv(photopeak_per_channel, index=False)

    else:
        photopeak_per_channel_df = pd.read_csv(photopeak_per_channel)

    photopeak_per_channel_df.loc[
        photopeak_per_channel_df["photopeak_mean"] < 100, "photopeak_mean"
    ] = photopeak_per_channel_df.loc[
        photopeak_per_channel_df["photopeak_mean"] >= 100, "photopeak_mean"
    ].mean()
    adc_col_list = [
        "adc_%s_ch%d_B%d" % (gain, channel, board)
        for channel in board_config["really_injected_ASIC_channels"][0]
        for gain in ["low"]
    ]
    df["adc_sum_corrected"] = (
        df[adc_col_list] / photopeak_per_channel_df["photopeak_mean"].values
    ).sum(axis=1)

    # 15 channels should collect charge maximum
    # subset = df.loc[df['adc_sum_corrected'] < 15, :]
    subset = df["adc_sum_corrected"]
    xmin, xmax, mu, sigmaHisto = plot_adc_sum(subset, file_suffix)
    plt.title(
        "Energy spectrum for 22Na summing all channels with channel gain correction \n%s"
        % config["datapath_to_display"]
    )
    plt.tight_layout()
    plt.savefig(
        config["output_folder"]
        + "../"
        + file_suffix
        + "/22Na_spectrum_sum_all_ch_gain_corrected.png"
    )

    plt.show()
    plt.close()


def plot_spectrum_sum_channels_gain_corrected_for_CeBr3(df, config, file_suffix):

    # Find photopeak for each channel
    photopeak_per_channel = (
        config["output_folder"] + "../" + file_suffix + "/photopeak_mean_per_channel.csv"
    )

    board = config["board"][0]
    board_config = config["config_B%d" % board]
    if not os.path.exists(photopeak_per_channel):
        res = {"channel": [], "photopeak_mean": []}

        for ci, channel in enumerate(board_config["injected_channel"][0]):
            label = ""
            color = "darkturquoise"
            col_label = "adc_%s_ch%d_B%d" % ("low", channel, board)

            if col_label in df.columns:
                plt.figure(figsize=(10, 8))

                # all
                serie = df[col_label]
                step = 5
                bins = np.arange(serie.min(), serie.max() + step + 1, step)
                counts, bins = np.histogram(serie, bins=bins)
                plt.stairs(counts, bins, color=color, fill=True, label=label)

                res["channel"].append(channel)

                if len(serie) > 0:
                    if len(counts) < 1:
                        pass
                    photopeak_index = np.argmax(counts)
                    photopeak = bins[photopeak_index]
                else:
                    print(
                        "Not enough data for selection for channel %d : %d"
                        % (channel, len(serie))
                    )
                    photopeak = 1

                plt.axvline(
                    photopeak,
                    color="blue",
                    linestyle="dashed",
                    label="\nmean photopeak = %d adc" % photopeak,
                )
                res["photopeak_mean"].append(photopeak)

                plt.title(
                    "Energy spectrum for channel %d\n%s"
                    % (channel, config["datapath_to_display"])
                )
                plt.xlabel("ADC [lsb]")
                plt.ylabel("Count")
                plt.grid()
                plt.xlim([-200, 1100])
                plt.yscale("log")
                plt.legend()
                plt.tight_layout()
                plt.savefig(
                    config["output_folder"]
                    + "../"
                    + file_suffix
                    + "/channel/22Na_spectrum_ch%d.png" % channel
                )
                # plt.show()
                plt.close()

        photopeak_per_channel_df = pd.DataFrame(res)
        photopeak_per_channel_df.to_csv(photopeak_per_channel, index=False)

    else:
        photopeak_per_channel_df = pd.read_csv(photopeak_per_channel)

    # Plot energy sum
    adc_col_list = [
        "adc_%s_ch%d_B%d" % (gain, channel, board)
        for channel in board_config["really_injected_ASIC_channels"][0]
        for gain in ["low"]
    ]
    scale = photopeak_per_channel_df["photopeak_mean"].mean() / len(adc_col_list)
    df["adc_sum_corrected"] = (
        df[adc_col_list] / photopeak_per_channel_df["photopeak_mean"].values
    ).sum(axis=1) * scale

    subset = df["adc_sum_corrected"]
    xmin, xmax, mu, sigmaHisto = plot_adc_sum(subset, file_suffix, offset=0)
    plt.title(
        "Energy spectrum for 22Na summing all channels with channel gain correction \n%s"
        % config["datapath_to_display"]
    )
    plt.tight_layout()
    plt.savefig(
        config["output_folder"]
        + "../"
        + file_suffix
        + "/22Na_spectrum_sum_all_ch_gain_corrected.png"
    )
    plt.yscale("log")
    # plt.show()
    plt.close()


def compare():

    thres_scan_df_filename = (
        "../output/Damavan/threshold_scan/75/raw/B2_calib_TL_staircase.csv"
    )
    df = pd.read_csv(thres_scan_df_filename)
    # plt.plot(df.channel, df.expected_aligned_pedestal)
    plt.plot(df.channel, df.calib_DAC_local)

    thres_scan_df_filename = (
        "../output/Damavan/threshold_scan/76/raw/B2_calib_TL_staircase.csv"
    )
    df = pd.read_csv(thres_scan_df_filename)
    # plt.plot(df.channel, df.expected_aligned_pedestal)
    plt.plot(df.channel, df.calib_DAC_local)

    plt.grid()
    plt.legend()

    plt.tight_layout()
    # plt.savefig(folder + 'ch%d.png' % channel)
    plt.show()


def plot_map_of_mean_frame(df, config):
    board = config["board"][0]
    board_config = config["config_B%d" % board]
    ASIC_channels_injected = board_config["really_injected_ASIC_channels"][0]
    missing_SiPM_channels = list(set(board_config["injected_channel_SiPM"][0]) ^ set(range(1, 62)))
    missing_ASIC_channels_values = [0] * len(missing_SiPM_channels)

    # adc_col_list_low = ["adc_%s_ch%d_B%d" % ("low", channel, board) for channel in ASIC_channels_injected]
    # selection = (df[adc_col_list_low] > 200).any(axis=1)
    # tdc_good_col_list_low = ["tdc_good_%s_ch%d_B%d" % ("low", channel, board) for channel in ASIC_channels_injected]
    # selection = df[tdc_good_col_list_low].any(axis=1)

    selection = (df["adc_sum_all_channels"] > 290) & (df["adc_sum_all_channels"] < 310)
    # inside photopeak according to sum all channels
    print(selection.value_counts())

    # mean_frame = df.mean(axis=0)
    mean_frame = df[selection].mean(axis=0)
    col_of_interest = 'adc'
    plt.subplots(1, 2, figsize=(16, 9))
    for gi, gain in enumerate(['low', 'high']):
        plt.subplot(1, 2, gi+1)
        im = plot_hex_sipm_from_frame(mean_frame, col_of_interest, board, gain, board_config)
        plt.colorbar(im, label="Energy - pedestal [adc]", location="bottom", shrink=0.6)

    plt.show()


def open_raw_file_at_frame_index(frame):
    index = frame['original_index']+1
    time = hex(frame['CPT']>>14)
    cpt_14b = hex((frame['CPT']&0b11_1111_1111_1111))


def plot_map_of_each_frame(df, config, file_suffix, threshold_dict):
    # plot SiPM map frame-by-frame
    mpl.rcParams["savefig.directory"] = (
        config["save_folder"] + "../" + file_suffix + "/frame/"
    )
    mpl.rcParams["savefig.format"] = "png"

    board = config["board"][0]
    board_config = config["config_B%d" % board]

    ASIC_channels_injected = board_config["really_injected_ASIC_channels"][0]

    # ASIC_channels_injected += get_ASIC_ch(missing_SiPM_channels, 'Hamamatsu_S13361_6597')

    adc_col_list_low = [
        "adc_%s_ch%d_B%d" % ("low", channel, board) for channel in ASIC_channels_injected
    ]

    # energy_selection = (df[adc_col_list_low] > 600).any(axis=1)

    # inside photopeak according to sum all channels
    energy_selection = df["photopeak_selection_high"] #& (df[tdc_good_col].sum(axis=1)>30)
    print(energy_selection.value_counts())
    df = df[energy_selection]

    tdc_good_col = [col for col in df.columns if ('tdc_good' in col)]
    df['tdc_good_count'] = df[tdc_good_col].sum(axis=1)
    df.sort_values('tdc_good_count', ascending=False, inplace=True)

    # df.sort_values('adc_low_ch31_B4', ascending=False, inplace=True)

    pass
    # it happens that col are in the SiPM ranking order, ready to plot !
    # df1 = df.loc[energy_selection, time_col_list]
    # df1 = df1.rename(columns={col:get_SiPM_ch(int(col[13:]), 'Hamamatsu_S13361_6597') for col in df1.columns})
    # df1 = df1.rename(columns={col:get_SiPM_ch(int(col[7+len(time_measure):]), 'Hamamatsu_S13361_6597') for col in df1.columns})


    for i, frame in df.iterrows():  # .loc[energy_selection, :]
        plt.subplots(2, 3, figsize=(16, 9))

        for gi,gain in enumerate(['high', 'low']):
            plt.subplot(2, 3, 1+3*gi)

            threshold = threshold_dict[gain]
            im = plot_hex_sipm_from_frame(frame, 'adc', board, gain, board_config, threshold = threshold, plot_center_mass=True)
            plt.colorbar(im, label=f"Energy - pedestal [adc] {gain} gain (cut<{threshold:.0f} adc)", location="bottom", shrink=0.6)
            im.set_clim(0, 1023)

            plt.subplot(2, 3, 2+3*gi)
            im = plot_hex_sipm_from_frame(frame, 'toa', board, gain, board_config)
            plt.colorbar(im, label=f"TOA [lsb] {gain} gain", location="bottom", shrink=0.6)

            plt.subplot(2, 3, 3+3*gi)
            im = plot_hex_sipm_from_frame(frame, 'tdc_good', board, gain, board_config)
            plt.colorbar(im, label=f"LSB [ps] {gain} gain", location="bottom", shrink=0.6)


        # val = frame[toa_col_list_low].where(
        #     frame[tdc_has_triggered_col_list_low].values, 0.0
        # )
        # # val -= val[val!=0].min()
        # val = val.to_list()
        # # frame[toa_ns_col_list] = frame[toa_ns_col_list].where(frame[toa_ns_col_list].isna().values==False, 0.0)
        # im = plot_hex_sipm(
        #     val + missing_ASIC_channels_values, "TOA low"
        # )  # for frame %d'%i)


        # # val = (frame[lsb_fromCAL_col_list_low].where(frame[tdc_has_triggered_col_list_low].values, 0.0)*1e3).to_list()
        # val = (frame[lsb_fromCAL_col_list_low] * 1e3).to_list()
        #
        # im = plot_hex_sipm(
        #     val + missing_ASIC_channels_values,
        #     "LSB from calibration low",
        #     hidden_value=0,
        #     label_format="%.1f",
        # )



        # val = np.array(
        #     [
        #         frame["CPT_cluster_%d" % (channel // 16)]
        #         for channel in ASIC_channels_injected
        #     ]
        # )
        # # Works because ASIC_channels_injected is ranked by SiPM channel order
        # val -= val.min()
        # val = val.tolist() + missing_ASIC_channels_values
        # labels = np.array(
        #     [
        #         val[channel] if channel % 16 == 3 else 0
        #         for channel in ASIC_channels_injected
        #     ]
        # )
        # im = plot_hex_sipm(
        #     val, "CPT diff between clusters", labels=labels, label_format="%d"
        # )  # .2E
        # cb = plt.colorbar(im, label="[400 ns]", location="bottom", shrink=0.6)

        # plt.subplot(2, 3, 5)
        # val = frame[overflown_TOA_col_list_low].to_list()
        # im = plot_hex_sipm(val + missing_ASIC_channels_values, "overflown_TOA_low")
        #
        # cb = plt.colorbar(im, label="[1]", location="bottom", shrink=0.6)
        #
        # plt.subplot(2, 3, 6)
        # val = (
        #     frame[cpt_col_list_low]
        #     .where(frame[tdc_has_triggered_col_list_low].values, 0.0)
        #     .to_list()
        # )
        # im = plot_hex_sipm(val + missing_ASIC_channels_values, "cpt low")
        # cb = plt.colorbar(im, label="cpt [25 ns]", location="bottom", shrink=0.6)

        plt.suptitle(
            "Frame %d - %s\n%s"
            % (i, file_suffix, config["save_folder"] + "../" + file_suffix + "/")
        )
        plt.tight_layout()
        frame_index = frame['original_index'] + 1
        plt.savefig(config["output_folder"]+ "../"+ file_suffix+ "/frame/frame_%d.png"%frame_index, dpi=120)
        plt.show()
        # plt.close()


def plot_first_triggered_channel_count_map(df, config, file_suffix):

    tdc_col = ["tdc_low_ch%d" % ch for ch in range(64)]

    hit_count_df = pd.DataFrame(
        {
            "hit_count": (df[tdc_col] != 0).sum(axis=0),
            "ASIC_channel": range(64),
            "cluster": np.array(range(64)) // 16,
            "SiPM_channel": get_SiPM_ch(list(range(64)), config["SiPM_model"]),
            "row": list(
                map(lambda x: x[:1], get_SiPM_ch(list(range(64)), config["SiPM_model"]))
            ),
            "column": list(
                map(lambda x: x[1:], get_SiPM_ch(list(range(64)), config["SiPM_model"]))
            ),
        }
    )

    first_event_count_map = pd.pivot(
        hit_count_df, values="hit_count", index="row", columns="column"
    )
    SiPM_channel_map = pd.pivot(
        hit_count_df, values="SiPM_channel", index="row", columns="column"
    )
    ASIC_channel_map = pd.pivot(
        hit_count_df, values="ASIC_channel", index="row", columns="column"
    )

    plot_cluster = False
    if plot_cluster:
        cluster_map = pd.pivot(
            first_event_count_map, values="cluster", index="row", columns="column"
        )
        first_event_count_map = cluster_map

    vmax = first_event_count_map.values.max()
    vmin = 0
    fig, ax = plt.subplots(1, 1, figsize=(10, 7))
    im = ax.imshow(
        first_event_count_map.values,
        origin="upper",
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
    )
    ax.set_xticks(
        range(len(np.int32(first_event_count_map.columns))),
        np.int32(first_event_count_map.columns),
    )
    ax.set_yticks(range(len(first_event_count_map.index)), first_event_count_map.index)
    # ax.tick_params(axis='both', which='major', labelsize=8)
    ax.set_xlabel("column")
    ax.set_ylabel("row")
    ax.set_aspect("equal")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=20)

    for (j, i), label in np.ndenumerate(SiPM_channel_map):
        red, green, blue, l = im.cmap(im.norm(im.get_array()[j, i]))  # background_colors
        luminance = (
            red * 0.2126 + green * 0.7152 + blue * 0.0722
        )  # human sightseeing color weight
        font_color = "white" if luminance < 140 / 255 else "black"  # maximise contrast

        plt.text(i, j, label, color=font_color, ha="center", va="top")
        plt.text(
            i,
            j,
            ASIC_channel_map.iloc[j, i],
            color=font_color,
            ha="center",
            va="bottom",
        )
        plt.axhline(i + 0.5, color="white", linewidth="1")
        plt.axvline(j + 0.5, color="white", linewidth="1")

    plt.title("Hit count map")
    plt.tight_layout()
    plt.savefig(
        config["save_folder"] + "../" + file_suffix + "/hit_count_map.png", dpi=120
    )
    # plt.show()
    plt.close()

    toa_col = ["toa_ns_low_ch%d" % ch for ch in range(64)]
    energy_cut_adc_sum = 1000
    selection = df["adc_sum"] < energy_cut_adc_sum
    selection = [True] * len(df["adc_sum"])
    # print(df.loc[selection, toa_col].eq(df.loc[selection, toa_col][df[selection] != 0].min(axis=1), axis=0).sum(axis=0)) # should be one per row !

    first_event_count_df = pd.DataFrame(
        {
            "first_event_count": df.loc[selection, toa_col]
            .eq(df.loc[selection, toa_col][df[selection] != 0].min(axis=1), axis=0)
            .sum(axis=0),
            "ASIC_channel": range(64),
            "cluster": np.array(range(64)) // 16,
            "SiPM_channel": get_SiPM_ch(list(range(64)), config["SiPM_model"]),
            "row": list(
                map(lambda x: x[:1], get_SiPM_ch(list(range(64)), config["SiPM_model"]))
            ),
            "column": list(
                map(lambda x: x[1:], get_SiPM_ch(list(range(64)), config["SiPM_model"]))
            ),
        }
    )

    first_event_count_map = pd.pivot(
        first_event_count_df, values="first_event_count", index="row", columns="column"
    )
    SiPM_channel_map = pd.pivot(
        first_event_count_df, values="SiPM_channel", index="row", columns="column"
    )
    ASIC_channel_map = pd.pivot(
        first_event_count_df, values="ASIC_channel", index="row", columns="column"
    )

    plot_cluster = False
    if plot_cluster:
        cluster_map = pd.pivot(
            first_event_count_df, values="cluster", index="row", columns="column"
        )
        first_event_count_map = cluster_map

    vmax = first_event_count_map.values.max()
    vmin = 0
    fig, ax = plt.subplots(1, 1, figsize=(10, 7))
    im = ax.imshow(
        first_event_count_map.values,
        origin="upper",
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
    )
    ax.set_xticks(
        range(len(np.int32(first_event_count_map.columns))),
        np.int32(first_event_count_map.columns),
    )
    ax.set_yticks(range(len(first_event_count_map.index)), first_event_count_map.index)
    # ax.tick_params(axis='both', which='major', labelsize=8)
    ax.set_xlabel("column")
    ax.set_ylabel("row")
    ax.set_aspect("equal")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=20)

    for (j, i), label in np.ndenumerate(SiPM_channel_map):
        red, green, blue, l = im.cmap(im.norm(im.get_array()[j, i]))  # background_colors
        luminance = (
            red * 0.2126 + green * 0.7152 + blue * 0.0722
        )  # human sightseeing color weight
        font_color = "white" if luminance < 140 / 255 else "black"  # maximise contrast

        plt.text(i, j, label, color=font_color, ha="center", va="top")
        plt.text(
            i,
            j,
            ASIC_channel_map.iloc[j, i],
            color=font_color,
            ha="center",
            va="bottom",
        )
        plt.axhline(i + 0.5, color="white", linewidth="1")
        plt.axvline(j + 0.5, color="white", linewidth="1")

    plt.title(
        "Counting the number of time a channel is first triggered among 64\nfor energy_cut_adc_sum < %d "
        % energy_cut_adc_sum
    )
    plt.tight_layout()
    plt.savefig(
        config["save_folder"]
        + "../"
        + file_suffix
        + "/first_triggered_channel_count_map.png",
        dpi=120,
    )
    plt.close()
    # plt.show()


def plot_spectrum_sum_channels(df, config, file_suffix):
    # ASIC_channel_selection = [33, 35, 41, 46, 28, 20, 25]  # inner 7 channels
    # ASIC_channel_selection += [52, 54, 51, 43, 31, 23, 15, 17, 14, 22, 38, 44]  # + ring channels around inner
    # channel_selection_suffix_list = ['inner_19_channels', 'all_channels']
    # ASIC_channel_selection_list = [ASIC_channel_selection, config['enable_TL_ASIC_ch'][0]]

    board = config["board"][0]
    board_config = config["config_B%d" % board]
    channel_selection_suffix_list = ["all_channels"]
    ASIC_channel_selection_list = [board_config["really_injected_ASIC_channels"][0]]
    # ASIC_channel_selection_list = [[43]]

    threshold_dict={}
    for gain in ['low', 'high']:
        for channel_selection_suffix, channel_selection in zip(
            channel_selection_suffix_list, ASIC_channel_selection_list
        ):
            adc_col_list_selection = ["adc_%s_ch%d_B%d" % (gain, channel, board) for channel in channel_selection]
            scale = 1 / len(adc_col_list_selection)
            sum = df[adc_col_list_selection].sum(axis=1) * scale
            df["adc_sum_" + gain + '_' + channel_selection_suffix] = sum

            xmin, xmax, mu, sigmaHisto = plot_adc_sum(sum, file_suffix, config)
            threshold_dict[gain] = 1.5*mu
            # df['photopeak_selection'] = df['adc_sum_' + channel_selection_suffix].ge(df['adc_sum_' + channel_selection_suffix].quantile(0.9))
            # xmin = mu-10
            # xmax = mu+10
            df["photopeak_selection_"+gain] = (sum > xmin) & (sum < xmax)
            plt.title(
                "Energy spectrum summing %s %s\n%s"
                % (gain, channel_selection_suffix, config["datapath_to_display"])
            )
            plt.tight_layout()
            plt.savefig(
                config["output_folder"]
                + "../"
                + file_suffix
                + "/22Na_spectrum_sum_"+gain+'_'
                + channel_selection_suffix
                + ".png"
            )
            plt.yscale("log")
            # plt.show()
            plt.close()

    return df, threshold_dict


def find_next_folder_index(folder, prev_folder_index):
    dir_list = list(next(os.walk(folder))[1])
    dir_list.sort()
    this_dir_index = prev_folder_index
    if prev_folder_index == -1:
        return int(dir_list[0])
    if not dir_list:
        return prev_folder_index
    else:
        for i, dir in enumerate(dir_list):
            if int(dir) == prev_folder_index:
                try:
                    this_dir_index = int(dir_list[i + 1])
                except IndexError:
                    pass
                break
    return this_dir_index


def analyse_step(root_folder, pedestal_mean, df_scan, folder_step):
    config = yaml.safe_load(open(folder_step + "config.yaml", "r"))
    step_HV = config["config_B2"]["target_hv"]

    # read measured HV, in case not available, use target HV
    step_HV_before = config["config_B2"].get("measured_HV_before", step_HV)
    step_HV_after = config["config_B2"].get("measured_HV_after", step_HV)
    step_HV_measured = 0.5 * (step_HV_before + step_HV_after)

    step_I_before = config["config_B2"].get("measured_I_before", 0)
    step_I_after = config["config_B2"].get("measured_I_after", 0)
    step_I_measured = 0.5 * (step_I_before + step_I_after)

    config["datapath_to_display"] = folder_step[len(root_folder) :]
    config["output_folder"] = folder_step
    config["config_B2"]["really_injected_ASIC_channels"] = config["config_B2"][
        "injected_channel"
    ][0]
    config["config_B2"]["not_injected_ASIC_channels"] = []

    file_suffix_list = glob.glob(folder_step + "B*_22Na*.csv")
    file_suffix_list = [
        "_" + os.path.basename(file).split(".")[0].split("_")[-1]
        for file in file_suffix_list
    ]
    file_suffix_list = np.unique(file_suffix_list)

    # file_suffix_list = ['_22Na_HV_57.0_palgGain_9_tauLG_2_patgain_32']
    # file_suffix_list = ['_22Na_HV_57.0_palgGain_9_tauLG_2_patgain_20']
    # file_suffix_list = file_suffix_list[8:]

    for file_suffix in file_suffix_list:
        print("Analysing :", file_suffix)
        analyse_data_with_source(
            root_folder, folder_step, file_suffix, pedestal_mean, config
        )

    df2_filepath = (
        os.path.dirname(folder_step)
        + "/../"
        + file_suffix
        + "/"
        + "2"
        + file_suffix
        + ".feather"
    )

    df_step = pd.read_feather(df2_filepath)
    if df_scan.empty:
        for i in df_step.columns:
            if "adc" in i:
                df_scan[i + "_mean"] = []
                df_scan[i + "_std"] = []
        df_scan["HV"] = []
        df_scan["HV_measured"] = []
        df_scan["I_measured"] = []

    step_data = {}
    step_data["HV"] = step_HV
    step_data["HV_measured"] = step_HV_measured
    step_data["I_measured"] = step_I_measured

    for colname in df_step.columns:
        if "adc" not in colname:
            continue
        step_data[colname + "_mean"] = df_step[colname].mean()
        step_data[colname + "_std"] = df_step[colname].std()

    temp = pd.DataFrame(step_data, index=[0])

    df_scan = pd.concat([df_scan, temp], ignore_index=True)

    return df_scan


def analyse_dark_HV_scan(root_folder, search_folder):
    pedestal_mean, pedestal_std, config = analyse_pedestal(root_folder, search_folder)

    i_prev = -1

    df_scan = pd.DataFrame()

    while True:
        i_step = find_next_folder_index(search_folder, i_prev)
        if i_step == i_prev:
            break
        folder_step = search_folder + f"{i_step}/raw/"

        df_scan = analyse_step(root_folder, pedestal_mean, df_scan, folder_step)

        i_prev = i_step

    df_scan.to_csv(search_folder + "dark_HV_scan.csv", index=False)

def var_v_function(x, sigma_0, alpha, beta, gamma, Vbd):
    Vov = x - Vbd
    sigma_out = sigma_0*sigma_0 + beta * (Vov*Vov * (1-np.exp(-Vov / alpha))) / \
                (1 - gamma * Vov * (1 - np.exp(-Vov / alpha)))**3
    return np.where(Vov >= 0, sigma_out, 0)


def get_Vbd_channel(search_folder, chan, hv, adc):

    fig, ax = plt.subplots()
    ax.plot(hv, adc, 'o')
    ax.set_xlabel('HV [V]')
    ax.set_ylabel('ADC [lsb]')

    ax.grid()
    ax.set_xlim([hv.min(), hv.max()])
    ax.set_ylim([0, 1.5])
    # plt.show()
    plt.savefig(search_folder + f"/../Vbd_channels/Vbd_scan_{chan}.png")

    return -1

def extract_Vbd_channel(search_folder):
    table_filepath = search_folder + "dark_HV_scan.csv"
    df = pd.read_csv(table_filepath)
    df_vbd = pd.DataFrame()
    df_vbd['channel'] = []
    df_vbd['Vbd'] = []

    if not os.path.exists(search_folder + "../Vbd_channels/"):
        os.mkdir(search_folder + "../Vbd_channels/")

    fig, ax = plt.subplots(8, 8, figsize=(20, 20))
    fig_2, ax_2 = plt.subplots(8, 8, figsize=(20, 20))
    for i_chan in range(64):
        x = df["HV_measured"].to_numpy()
        y = df[f'adc_low_ch{i_chan}_B2_std'].to_numpy()
        chan_data = {
            "channel": i_chan,
            # "Vbd": get_Vbd_channel(search_folder, i_chan, x, y)
            "Vbd": -1
        }
        df_vbd = pd.concat([df_vbd, pd.DataFrame(chan_data, index=[0])], ignore_index=True)
        x_idx = i_chan // 8
        y_idx = i_chan % 8
        ax[x_idx, y_idx].plot(x, y*y, 'o')
        ax[x_idx, y_idx].set_title(f'Ch {i_chan}')
        ax[x_idx, y_idx].grid()
        ax[x_idx, y_idx].set_xlim([x.min(), x.max()])
        # ax[x_idx, y_idx].set_ylim([0, 4])

        # ax_2[x_idx, y_idx].plot(x, 2* np.gradient(y) / y, 'o')
        ax_2[x_idx, y_idx].plot(x, np.gradient(np.log(y**2), x), 'o')
        ax_2[x_idx, y_idx].set_title(f'Ch {i_chan}')
        ax_2[x_idx, y_idx].grid()
        ax_2[x_idx, y_idx].set_xlim([x.min(), x.max()])
        # ax_2[x_idx, y_idx].set_ylim([-1, 1])


    fig.tight_layout()
    fig.savefig(search_folder + f"/../Vbd_channels/Vbd_scan_all.png")

    fig_2.tight_layout()
    fig_2.savefig(search_folder + f"/../Vbd_channels/Vbd_scan_all_deriv.png")


    return df_vbd



if __name__ == "__main__":
    # root_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw_seva/output/"
    # root_folder = "/home/vsevolod/Work/Temporoc/temporoc_sw/output/"
    # root_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    # root_folder = "//192.168.2.230/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    # folder = root_folder + "Hamamatsu/Na22_spectra/full_segmented_alu_coated_LYSO/"
    # root_folder = "//PCWEEROC22/temporoc/temporoc_sw/output/"

    # search_folder = root_folder + "Broadcom/Na22_spectra/CeBr3_quartz_encapsulated/"
    # search_folder = root_folder + "Hamamatsu_S13361_6597/Na22_spectra/full_monolithic_uncoated_LYSO/"
    # i = find_latest_folder_index(search_folder)


    # plot_staircase("../output/Damavan/threshold_scan/2/raw/")
    # plot_Sipm_gain_vs_channel("../output/Damavan/threshold_scan/2/raw/")
    # plot_22Na_spectrum("//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/Damavan/22Na_spectra/63/raw/")
    # compare()

    # for i in [123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138]:
    # for i in [ 133, 134, 135, 136, 137, 138]: #132,
    # for i in [140]:



    # analyse_dark_HV_scan(root_folder, search_folder+f"{i}/raw/")
    # extract_Vbd_channel(search_folder+f"{i}/raw/")

    # plot_22Na_spectrum(root_folder, search_folder+"%d/raw/"%i)

    # plot_22Na_spectrum(root_folder + "Hamamatsu/Na22_spectra/3x3x5_LYSO/38_B1_filtering_TQ_baseline/raw/")
    # plot_hex_sipm_cluster_map()

    root_folder = "../output/"
    # search_folder = root_folder + "Broadcom_S4N44P164M/Na22_spectra/LYSO_array_2mm_pitch/25/raw/" # Shared by Sydney
    # search_folder = root_folder + "/Hamamatsu_single/Na22_spectra/LYSO_3x3x10/62/raw/"
    # shutil.copyfile(root_folder + '/Hamamatsu_single/Na22_spectra/LYSO_3x3x10/37/raw/B6_master_cluster_0_pedestal.csv', search_folder+'B6_master_cluster_0_pedestal.csv')

    search_folder = root_folder + "/Hamamatsu_S13361_6597/Na22_spectra/LYSO_monolithic_hexa/6/raw/"


    for cluster in range(4):
        file_to_copy = root_folder + '/Hamamatsu_S13361_6597/Na22_spectra/LYSO_monolithic_hexa/2/raw/B4_master_cluster_%d_pedestal.csv'%cluster
        if os.path.exists(file_to_copy):
            shutil.copyfile(file_to_copy, search_folder+'B4_master_cluster_%d_pedestal.csv'%cluster)

    plot_22Na_spectrum(root_folder, search_folder)