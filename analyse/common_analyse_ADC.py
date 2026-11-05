import os, re, yaml, glob

import pandas as pd
from alive_progress import alive_bar

from analyse.common_data_decoding import *


def analyse_init_internal_adc(search_folder):
    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("(?<=raw/)[0-9]+", folder)

    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        exit(0)

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    files = glob.glob(search_folder + '/*.csv')

    board = config['board'][0]
    df_filename = '%s_B%d' % (folder_index_str, board)
    # df_filename = os.path.basename(files[0])
    # df_filename = df_filename.split("__")[0]  # no mention of cluster or delay

    output_folder = folder + '/../../' + folder_index_str + '/energy_spectrum/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    save_filepath = output_folder + df_filename
    df0_filepath = save_filepath + "_0.feather"
    df1_filepath = save_filepath + "_1.feather"
    stats_filepath = save_filepath + "_stats.csv"

    # Step 0 : assemble all files
    if os.path.exists(stats_filepath):
        stats = pd.read_csv(stats_filepath)
        if os.path.exists(df0_filepath):
            df = pd.read_feather(df0_filepath)
        else:
            print("Missing dataframe.")
            exit(0)

        stats['not_received_frames'] = stats.asked_event_count - stats.raw_event_count
        status_columns = [col for col in stats.columns if 'status' in col]
        category_names_stats = ['exploitable_event'] + status_columns + ['all_tdc_null_count', 'frames not received']
        columns = ['exploitable_event_count'] + status_columns + ['all_tdc_null_count', 'not_received_frames']
        # df_mean = pd.pivot_table(stats, values=columns, index='readout_mode', aggfunc='sum', sort=False)
        # results = df_mean.T.to_dict('list')

        # plot_data_quality(category_names_stats, results, 'data_quality', output_folder)

    else:
        df = pd.DataFrame()

        stats_dict = {'raw_event_count': [],
                      'asked_event_count': [],
                      'readout_mode': [],
                      'exploitable_event_count': [],
                      'file': [],
                      'cluster': []}


        print("Combining all results...")
        with alive_bar(len(files), force_tty=True) as bar:  # your expected total
            for fi, file in enumerate(files):
                if 'i2c_df' in file:
                    continue
                df_tmp = build_dataframe_from_file(file)

                df_tmp = remove_status_erroneous_frames(len(df), df_tmp, stats_dict, fi, meas='adc')

                stats_dict['asked_event_count'].append(0) #config['total_nb_events_expected'][0])
                stats_dict['exploitable_event_count'].append(len(df_tmp))
                stats_dict['file'].append(os.path.basename(file))
                stats_dict['readout_mode'].append(config['readout_mode'][0])

                cluster = re.findall("(?<=cluster_)[0-9]+", file)
                cluster = int(cluster[0]) if cluster else 0
                stats_dict['cluster'].append(cluster)
                df_tmp['cluster'] = cluster

                df = pd.concat([df_tmp, df])

                bar()

        df.to_feather(df0_filepath)
        stats = pd.DataFrame(stats_dict)
        stats.to_csv(stats_filepath, index=False)

    # # Step 1 : decode data + add absolute time
    # if os.path.exists(df1_filepath):
    #     df = pd.read_feather(df1_filepath)
    # else:
    #     # df = drop_tdc_columns(df)
    #     df = decode_TDC_data(df)
    #     df = correct_TDC_data(df, config)
    #     df.to_feather(df1_filepath)

    return df, output_folder, save_filepath, config, folder_index_str, board, files


def analyse_pedestal_core(df0, search_folder, config):

    # last_foldername = os.path.basename(os.path.normpath(search_folder + "../../"))

    if not os.path.exists(config['output_folder'] + "adc/channel_pedestal/"):
        os.makedirs(config['output_folder'] + "adc/channel_pedestal/")

    pedestal_dict = {"board": [], "gain": [], "channel": [], "pedestal_mean": [], "pedestal_std": []}

    # plt.figure(0, figsize=(12, 8))
    # plt.figure(1, figsize=(12, 8))

    for board in config['board']:
        channel_list = config['config_B%d' % board]['enable_TL_ASIC_ch'][0]

        for gain in ['low', 'high']:
            adc_col_list = ['adc_%s_ch%d_B%d' % (gain, channel, board) for channel in channel_list]
            # adc_col_list = [col for col in df0.columns if ('adc_%s'%gain in col) & ('B%d'%board in col)]
            # if len(adc_col_list) == 0:
            #     print("Empty dataset!")
            #     pass
            #     exit(0)
            channel_list = [int(re.findall("(?<=_ch)[0-9]+", col)[0]) for col in adc_col_list]
            pedestal_mean = df0[adc_col_list].mean(axis=0).values
            pedestal_std = df0[adc_col_list].std(axis=0).values

            pedestal_dict['board'] += [board]*len(pedestal_mean)
            pedestal_dict['gain'] += [gain]*len(pedestal_mean)
            pedestal_dict['channel'] += channel_list
            pedestal_dict['pedestal_mean'] += pedestal_mean.tolist()
            pedestal_dict['pedestal_std'] += pedestal_std.tolist()

            plt.figure(0)
            plt.errorbar(channel_list, pedestal_mean, yerr=pedestal_std, fmt="o", ls="none", label='B%d_%s' % (board, gain))

            plt.figure(1)
            plt.plot(channel_list, pedestal_std, marker='o', label='B%d_%s' % (board, gain))

            plt.figure(2)
            bins = np.arange(pedestal_mean.min(), pedestal_mean.max() + 1, 5)
            counts, bins = np.histogram(pedestal_mean, bins=bins)
            plt.stairs(counts, bins, fill=True, label='B%d_%s' % (board, gain))

            # PLOT WEIRD CHANNELS
            #     for ci, channel in enumerate(config["injected_channel"][0]):
            problematic_channels = [channel for channel, pedestal in zip(channel_list, pedestal_mean) if (pedestal > 100) | (pedestal < 20)]
            for ci,channel in enumerate(problematic_channels):

                col_label = "adc_%s_ch%d_B%d" % (gain, channel, board)
                if col_label not in df0.columns:
                    return
                plt.figure(figsize=(10, 8))
                bins = np.arange(df0[col_label].min(), df0[col_label].max() + 1, 1)
                counts, bins = np.histogram(df0[col_label], bins=bins)
                plt.stairs(counts, bins, color="darkcyan", fill=True)
                plt.title("Channel %d "%channel)
                plt.xlabel("ADC [lsb]")
                plt.ylabel("Count")
                plt.grid()

                plt.axvline(
                    pedestal_mean[ci],
                    color="red",
                    linestyle="dashed",
                    label="pedestal mean",
                )
                plt.legend()
                plt.tight_layout()
                plt.savefig(config['output_folder'] + "adc/channel_pedestal/%s.png" % col_label)
                plt.close()

    pedestal_df = pd.DataFrame(pedestal_dict)
    pedestal_df.to_csv(config['output_folder'] + "adc/pedestal_stats.csv", index=False)

    plt.figure(0)
    plt.grid()
    plt.xlabel("Channels")
    plt.title("Pedestal dispersion versus channel")
    plt.ylabel("Mean pedestal [adc]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "adc/pedestal_mean_vs_channel")
    plt.close()

    plt.figure(1)
    plt.grid()
    plt.xlabel("Channels")
    plt.title("Pedestal dispersion versus channel")
    plt.ylabel("Std pedestal [adc]")
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "adc/pedestal_std_vs_channel")
    plt.close()

    plt.figure(2)
    plt.title("Histogram mean pedestal versus channel (binning = 5 [adc]) ")
    plt.ylabel("Count")
    plt.xlabel("Mean pedestal [adc]")
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "adc/pedestals_histo")
    plt.close()
    # plt.show()

    # plt.figure(3)
    # todo
    # Comparison with shaper analogprobe DC levels for weird channels

    return pedestal_df