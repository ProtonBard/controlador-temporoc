import csv
import os, re, glob, pandas as pd, numpy as np, yaml, time, itertools
from datetime import datetime

from alive_progress import alive_bar
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from src.CONSTANTS import CONSTANTS
from src.utils import save_config_file_copy, save_post_analysis_config_file, plot_data_quality
from statistics import multimode, mode


def analyse_init_internal_tdc(search_folder, file_suffix=''):
    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("(?<=/)[0-9]+", folder)
    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        exit(0)

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)
    outfile.close()

    distant_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    if distant_folder in search_folder:
        config['save_folder'] = distant_folder + config['save_folder']

    output_folder = folder + '/../' + file_suffix + '/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    config['output_folder'] = output_folder
    config['save_folder'] = search_folder

    stats_filepath = output_folder + "stats"+file_suffix+".csv"
    df0_filepath = output_folder + '0' + file_suffix + '.feather'
    df1_filepath = output_folder + '1'+file_suffix+'.feather'

    # Step 0 : assemble all files
    if os.path.exists(stats_filepath) & os.path.exists(df0_filepath) & ~os.path.exists(df1_filepath):
        print("Reading existing dataframe 0")
        stats = pd.read_csv(stats_filepath)
        df = pd.read_feather(df0_filepath)

    else:
        print("Will merge clusters for each delay based on CPT={time;msb_cpt}")
        # MERGE cluster files for each delay
        df = pd.DataFrame()
        stats_dict = {'raw_event_count': [],
                      'exploitable_event_count': [],
                      'file': [],
                      'cluster': [],
                      'delay': [],
                      'injected_channels': [],
                      'status_32_count': []}

        for delay in config['delay']:
            board = config['board'][0]
            files = [search_folder + "/B%d_cluster_%d_delay_%d.csv" % (board, cluster, delay) for cluster in
                                 config['power_cluster'][0]]

            df_tmp0 = pd.DataFrame()
            for fi, file in enumerate(files):

                df_tmp = build_dataframe_from_file(file)
                df_tmp = decode_CPT_data(df_tmp)
                RO_code = config['board_B%d'%board]['readout_mode_code']
                df_tmp = remove_status_erroneous_frames(len(df), df_tmp, stats_dict, fi, 'CPT', RO_code, verbose=False)

                cluster = re.findall("(?<=cluster_)[0-9]+", file)
                cluster = int(cluster[0]) if cluster else 0

                injected_channel_list = np.array(config['enable_TL_ASIC_ch'])
                cluster_list = injected_channel_list // 16
                injected_channel_list_within_current_cluster = injected_channel_list[np.where(cluster_list == cluster)]

                stats_dict['exploitable_event_count'].append(len(df_tmp))
                stats_dict['file'].append(os.path.basename(file))
                stats_dict['cluster'].append(cluster)
                stats_dict['delay'].append(delay)
                stats_dict['injected_channels'].append(injected_channel_list_within_current_cluster)

                df_tmp = rename_channels_to_64base(df_tmp, cluster)

                df_tmp.drop(['time', 'msb_cpt', 'trigger_low', 'trigger_high', 'status', 'mode'], axis=1, inplace=True)

                if fi == 0:
                    df_tmp0 = df_tmp
                else:
                    df_tmp0 = df_tmp0.merge(df_tmp, on='CPT', how='inner', validate='one_to_one')

            df_tmp0['delay'] = delay

            # CONCAT delay
            df = pd.concat([df, df_tmp0])

        df.to_feather(df0_filepath)
        stats = pd.DataFrame(stats_dict)
        stats.to_csv(stats_filepath, index=False)

        dict_keys_with_status = [k for k, v in stats_dict.items() if 'status_' in k]
        for dict_key_with_status in dict_keys_with_status:
            status = int(re.findall("(?<=status_)[0-9]+", dict_key_with_status)[0])
            print("%d (%d %%) events removed because of STATUS %d error" % (stats[dict_key_with_status].sum(), stats[dict_key_with_status].sum() / stats['raw_event_count'].sum() * 100, status))

        additional_keys = []
        if 'duplicated_time_count' in stats_dict.keys():
            print("%d (%d %%) events removed because of duplicated_time error" % (stats['duplicated_time_count'].sum(), stats['duplicated_time_count'].sum() / stats['raw_event_count'].sum() * 100))
            additional_keys.append('duplicated_time_count')

        if 'duplicated_time_count' in stats_dict.keys():
            print("%d (%d %%) events removed because of duplicated {time;msb_cpt} error" % (stats['duplicated_CPT_count'].sum(),
                                                                                  stats['duplicated_CPT_count'].sum() /
                                                                                  stats['raw_event_count'].sum() * 100))
            additional_keys.append('duplicated_time_count')

        status_columns = [col for col in stats.columns if 'status' in col]
        category_names_stats = ['exploitable_event'] + status_columns + additional_keys
        columns = ['exploitable_event_count'] + status_columns + additional_keys
        df_mean = pd.pivot_table(stats, values=columns, index='readout_mode', aggfunc='sum', sort=False)
        results = df_mean.T.to_dict('list')

        plot_data_quality(category_names_stats, results, 'data_quality', output_folder)

    # Step 1 : decode data + add absolute time
    if os.path.exists(df1_filepath):
        print("Reading existing dataframe 1")
        df = pd.read_feather(df1_filepath)
    else:
        df = decode_TDC_data(df, config)
        df = correct_TDC_data_64ch(df, config, other_cols_to_drop=[])

        # df = drop_adc_columns(df)
        # df = correct_ADC_data_64ch(df, config)

        save_config_file_copy(config)

        df.to_feather(df1_filepath)

    return df, output_folder, config, folder_index_str



def is_data_mergeable(config, file_suffix=''):

    mergeable = True
    for bi, board in enumerate(config['board']):
        files = glob.glob(config['save_folder'] + '/B%d_'%board + '*' + file_suffix + '.csv')
        df_board = pd.DataFrame()

        for fi, file in enumerate(files):  # go through clusters
            converters = {"time": lambda x: int(x, 16), "msb_cpt": lambda x: int(x, 16)}
            df_tmp = pd.read_csv(file, names=CONSTANTS.COLNAMES106, header=None, converters=converters)
            df_tmp['CPT'] = np.left_shift(df_tmp.time, 14) + df_tmp.msb_cpt
            df_tmp.drop(labels=list(set(df_tmp.columns)^{'CPT'}), axis="columns", inplace=True)

            if fi == 0:
                df_board = df_tmp
            else:
                df_board = df_board.merge(df_tmp, on='CPT', how='inner') #, validate='one_to_one')

        mergeable &= (len(df_board)>0)

    return mergeable

def read_config(root_folder, search_folder, config =None, file_suffix='', board_list=None):

    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("(?<=/)[0-9]+", folder)  # (?=_*/raw)
    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        exit(0)
        # return

    if not config:
        config_file = folder + "/config_post_analysis.yaml"
        if not os.path.exists(config_file):
            config_file = folder + "/config.yaml"
        with open(config_file, 'r') as outfile:
            config = yaml.safe_load(outfile)
        outfile.close()

    if board_list == None:
        board_list = config['board']

    # config['save_folder'] = root_folder + config['save_folder']
    config['root_folder'] = root_folder
    config['datapath_to_display'] = search_folder[len(root_folder):]

    # distant folder
    # if (':/' in root_folder) | ('//' in root_folder):
    #     config['save_folder'] = root_folder + config['save_folder']

    if len(board_list) > 1:
        board_list = [str(board) for board in np.sort(board_list)]
        all_boards_label = 'B' + "-".join(board_list)
        output_folder = folder + '/../' + all_boards_label + '/' + file_suffix + '/'
    else:
        output_folder = folder + '/../B%d/' % board_list[0] + file_suffix + '/'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    config['output_folder'] = output_folder

    return config

def analyse_init(search_folder, config,
                 file_suffix='', board_list=None,
                 merge_clusters_based_on = 'CPT', #'CPT>>2',
                 skip_adc_correction=True):

    if board_list == None:
        board_list = config['board']
    config['merge_based_on'] = merge_clusters_based_on

    # save_filepath = output_folder # + '%s_' % (folder_index_str)
    df0_filepath = config['output_folder'] + '0'+file_suffix+'.feather'
    df1_filepath = config['output_folder'] + '1'+file_suffix+'.feather'
    stats_filepath = config['output_folder'] + "stats"+file_suffix+".csv"
    config['stats_filepath'] = stats_filepath

    # Step 0 : assemble all files
    if os.path.exists(stats_filepath) & os.path.exists(df0_filepath):

        if os.path.exists(df1_filepath):
            pass
        else:
            print("Reading existing dataframe 0 ", end='')
            df = pd.read_feather(df0_filepath)
            print("(%d frames)"%len(df))
    else:
        df = pd.DataFrame()
        cluster_stats_dict = {'raw_event_count': [],
                      'exploitable_event_count': [],
                      'file': [],
                      'cluster': [],
                      'injected_channels': [],
                      'len_after_merging':[]}

        if merge_clusters_based_on:
            print("\nWill merge clusters based on " + merge_clusters_based_on)
            if merge_clusters_based_on=='CPT':
                print("CPT = concatenation of {fpga counting temporoc's counter overflow (32b) ; temporoc counter (14b)}")


        board_length_list = []

        for bi, board in enumerate(board_list):
            files = glob.glob(search_folder + '/B%d'%board+'*' + file_suffix + '.csv')

            df_board = pd.DataFrame()
            # df_MSB_CPT_stats = pd.DataFrame()
            df_not_merged_CPT = pd.DataFrame()

            # with alive_bar(len(files), force_tty=True) as bar:  # your expected total
            # cluster_length_list = []
            cluster_for_this_board = []

            # combine clusters
            for fi, file in enumerate(files): # go through clusters
                print("For %s:"%os.path.basename(file))

                cluster = re.findall("(?<=cluster_)[0-9]+", file)
                cluster = int(cluster[0]) if cluster else 0
                cluster_for_this_board.append(cluster)

                df_tmp = build_dataframe_from_file(file, config)
                init_len = len(df_tmp)
                df_tmp['index_cluster_%d_B%d' % (cluster, board)] = df_tmp.index
                df_tmp, new_cluster_stats_dict = remove_status_erroneous_frames(init_len, df_tmp, cluster_stats_dict)
                cluster_stats_dict = append_cluster_stats_dict(new_cluster_stats_dict, cluster_stats_dict)
                if len(df_tmp)>0:

                    df_tmp = decode_CPT_data(df_tmp, config, cluster, file_suffix, use_mimic_offset_table=True)

                    # df_tmp['CPT>>2'] = np.right_shift(df_tmp['CPT'], 2)

                    df_tmp = remove_duplicated_merge_key_row(init_len, df_tmp, cluster_stats_dict, fi, merge_clusters_based_on)

                    conv_syst = 'pedestal' in file_suffix
                    if conv_syst:
                        # should delete all columns related to tdc, trigger, lsb_cpt because wrong when conv_sys
                        pass
                    else:
                        df_tmp = correct_lsb_cpt_data_from_expected_overflow(df_tmp, config, init_len)

                    df_tmp = rename_channels_to_64base(df_tmp, cluster, board)

                # df_MSB_CPT_stats['CPT_cluster_%d' % cluster] = df_tmp['CPT'].reset_index(drop=True)

                # df_tmp = correct_overflow_counter_in_CPT_data(df_tmp)
                # df_tmp = remove_retriggering_frames(init_len, df_tmp, cluster_stats_dict, fi, RO_code)

                injected_channel_list = np.array(config['config_B%d'%board]['enable_TL_ASIC_ch'][0])
                cluster_list = injected_channel_list // 16
                injected_channel_list_within_current_cluster = injected_channel_list[np.where(cluster_list == cluster)]

                cluster_stats_dict['raw_event_count'].append(init_len)
                cluster_stats_dict['exploitable_event_count'].append(len(df_tmp))
                cluster_stats_dict['file'].append(os.path.basename(file))
                cluster_stats_dict['cluster'].append(cluster)
                cluster_stats_dict['injected_channels'].append(injected_channel_list_within_current_cluster)

                # print(df_tmp.CPT.diff().value_counts() / len(df_tmp) * 100)
                # print(config['nb_trigger'])
                # print(len(config['enable_TL_ASIC_ch'][0]))


                if merge_clusters_based_on=='CPT':
                    df_tmp.drop(['status', 'mode', 'msb_cpt', 'frames_found', 'bytes_dropped'], axis=1, inplace=True)
                    # df_tmp.rename(columns={'trigger_%s'%gain:'trigger_%s_cluster%d'%(gain, cluster) for gain in ['low', 'high']}, inplace=True)
                    # df_tmp.columns = df_tmp.columns.map(lambda x: str(x) + '_B%d'%board if x not in [merge_clusters_based_on]  else str(x))


                    if fi == 0:
                        df_board = df_tmp
                        cluster_stats_dict['len_after_merging'].append(len(df_tmp))
                    else:
                        merge_result = df_board.merge(df_tmp, on='CPT', how='inner', validate='one_to_one')
                        cluster_stats_dict['len_after_merging'].append(len(df_board))

                        new_df_not_merged_CPT = df_tmp.loc[~df_tmp['CPT'].isin(merge_result['CPT']), ['CPT', 'index_cluster_%d_B%d'%(cluster, board)]]
                        if df_not_merged_CPT.empty:
                            df_not_merged_CPT = new_df_not_merged_CPT
                        else:
                            df_not_merged_CPT = df_not_merged_CPT.merge(new_df_not_merged_CPT, on='CPT', how='outer')
                        df_board = merge_result

                if merge_clusters_based_on=='CPT>>2':
                    df_tmp['index_cluster_%d_B%d'%(cluster, board)] = df_tmp.index
                    df_tmp.drop(['status', 'mode', 'msb_cpt'], axis=1, inplace=True)

                    df_tmp.rename(columns={'CPT':'CPT_cluster%d_B%d'%(cluster, board)}, inplace=True)

                    if fi == 0:

                        df_board = df_tmp
                        cluster_stats_dict['len_after_merging'].append(len(df_tmp))
                    else:
                        merge_result = df_board.merge(df_tmp, on=merge_clusters_based_on, how='inner', validate='one_to_one')
                        cluster_stats_dict['len_after_merging'].append(len(df_board))

                        new_df_not_merged_CPT = df_tmp.loc[~df_tmp[merge_clusters_based_on].isin(merge_result[merge_clusters_based_on]), [merge_clusters_based_on, 'index_cluster_%d_B%d'%(cluster, board)]]
                        if df_not_merged_CPT.empty:
                            df_not_merged_CPT = new_df_not_merged_CPT
                        else:
                            df_not_merged_CPT = df_not_merged_CPT.merge(new_df_not_merged_CPT, on=merge_clusters_based_on, how='outer')
                        df_board = merge_result

                if merge_clusters_based_on == 'raw_file_index':
                    # 'time',
                    df_tmp.drop(['msb_cpt', 'status', 'mode'], axis=1, inplace=True) # 'trigger_low', 'trigger_high',
                    # cluster_length_list.append(len(df_tmp))
                    # df_tmp.columns = df_tmp.columns.map(lambda x: str(x) + '_B%d' % board
                    #     if x != 'CPT' else str(x))
                    df_tmp['raw_file_index'] = df_tmp.index
                    if fi == 0:
                        df_board = df_tmp
                        cluster_stats_dict['len_after_merging'].append(len(df_tmp))
                    else:
                        # df_tmp.drop(['CPT_B%d'%board], axis=1, inplace=True)
                        # if 'CPT_B%d'%board in df_board.columns:
                        #     df_board.drop(['CPT_B%d'%board], axis=1, inplace=True)

                        df_tmp.drop(['CPT'], axis=1, inplace=True)
                        df_board = df_board.merge(df_tmp, on='raw_file_index', how='inner', validate='one_to_one')
                        cluster_stats_dict['len_after_merging'].append(len(df_board))


                print('-> %d merged events' % len(df_board))

            length_after_merging = len(df_board)
            if length_after_merging==0:
                print("Dataset is empty after merging clusters !")
            board_length_list.append(length_after_merging)

            pass

            # #### post-analysis CPT ###
            # # For matching CPT rows, count number of overflows
            # correctable_overflow_error_in_matching_CPT = (df_board['CPT'].diff(-1)>0).value_counts()[(df_board['CPT'].diff(-1)>0).value_counts().index == True].values
            # correctable_overflow_error_in_matching_CPT = int(correctable_overflow_error_in_matching_CPT[0] if correctable_overflow_error_in_matching_CPT.size>0 else 0)
            #
            # # For non-matching CPT row, extract them, quantify errors types
            # df_MSB_CPT_stats = df_MSB_CPT_stats[~df_MSB_CPT_stats.eq(df_MSB_CPT_stats.iloc[:, 0], axis=0).all(1)]
            # true_CPT = df_MSB_CPT_stats.apply(mode, axis=1)
            # # true_CPT = df_MSB_CPT_stats.apply(multimode, axis=1)  # takes into account when no majority exists 2 vs 2
            # error_types = df_MSB_CPT_stats.sub(true_CPT, axis=0).apply(lambda x: set(abs(x)) ^ {0}, axis=1)
            # msb_cpt_error_by_one = int((error_types == {16}).sum())
            # overflow_error_in_non_matching_CPT = int((error_types == {2 ** 14}).sum())
            # unexplained_error = len(df_MSB_CPT_stats) - msb_cpt_error_by_one - overflow_error_in_non_matching_CPT
            #
            # min_init_len = min(cluster_stats_dict['raw_event_count'])
            # cpt_error_str = ('%d (%.2f %%) unexplained_error_in_non_matching_CPT  '%(unexplained_error, unexplained_error/min_init_len*100)
            # + '\n%d (%.2f %%) msb_cpt_error_by_one_in_non_matching_CPT  '% (msb_cpt_error_by_one, msb_cpt_error_by_one/min_init_len*100)
            # + '\n%d (%.2f %%) overflow_error_in_non_matching_CPT  '%(overflow_error_in_non_matching_CPT, overflow_error_in_non_matching_CPT/min_init_len*100)
            # + '\n%d (%.2f %%) correctable_overflow_error_in_matching_CPT '%(correctable_overflow_error_in_matching_CPT, correctable_overflow_error_in_matching_CPT/length_after_merging*100))
            #
            # print("MSB CPT ERRORS:\n"+cpt_error_str)
            # df_MSB_CPT_stats.to_csv(config['output_folder']+"/df_MSB_CPT_stats.csv")

            cluster_column = list(set(df_not_merged_CPT.columns) ^ {merge_clusters_based_on})
            CPT_matching_error_count = len(df_not_merged_CPT)
            CPT_found_in_3clusters_out_of_4_count = 0
            if CPT_matching_error_count>0:
                a = df_not_merged_CPT[cluster_column].nunique(axis=1)
                print("%d CPT errors:"%CPT_matching_error_count)

                if len(a)>0:
                    CPT_found_in_3clusters_out_of_4_count = int((a==1).value_counts()[True])
                    print('CPT_found_in_3clusters_out_of_4_count: %d '%CPT_found_in_3clusters_out_of_4_count)
                    b = a.value_counts()
                    if 1 not in b.index:
                        print(b)

                    df_not_merged_CPT.to_csv(config['output_folder']+"/df_not_merged_CPT_B%d.csv"%board, index=False)


            if len(files) > 1:
                config['CPT_matching_error_count_B%d' % board] = CPT_matching_error_count
                config['CPT_found_in_3clusters_out_of_4_count_B%d' % board] = CPT_found_in_3clusters_out_of_4_count

                config['merge_success_count_B%d'%board] = length_after_merging
                config['merge_success_%%_B%d'%board] = round(length_after_merging / min(cluster_stats_dict['raw_event_count']) * 100)
                print('Between clusters of B%d: %d %% successfully merged events (%d)' % (board,
                config['merge_success_%%_B%d'%board], config['merge_success_count_B%d' % board]))


            if bi == 0:
                df = df_board
            else:
                # CPT_offset_between_board = df['CPT'].iloc[0]-df_board['CPT'].iloc[0]
                # CPT_offset_between_board = 1
                # df_board['CPT'] += CPT_offset_between_board
                df = pd.merge(df, df_board, on=merge_clusters_based_on, how='inner', validate='one_to_one')

                config['merge_success_count'] = len(df)
                config['merge_success_%%'] = round(
                    len(df)/ min(board_length_list) * 100)
                print('Between boards : %d %% successfully merged events (%d)' % (config['merge_success_%%'], config['merge_success_count']))


        save_post_analysis_config_file(config)
        # if (merge_clusters_based_on == 'CPT') | (merge_clusters_based_on == 'CPT>>2'):
        #     original_index_col = [col for col in df.columns if 'index_cluster_' in col]
        #     df['original_index'] = df[original_index_col[0]]
        #     df.drop(columns=original_index_col, axis=1, inplace=True)

        df.to_feather(df0_filepath)
        stats = pd.DataFrame(cluster_stats_dict)
        stats.to_csv(stats_filepath, index=False)

        stats['not_received_frames'] = 0  # stats.asked_event_count - stats.raw_event_count
        status_columns = [col for col in stats.columns if 'status' in col]
        category_names_stats = ['exploitable_event'] + status_columns + ['frames not received'] # 'all_tdc_null_count'
        columns = ['exploitable_event_count'] + status_columns + ['not_received_frames'] # 'all_tdc_null_count'
        df_mean = pd.pivot_table(stats, values=columns, index='file', aggfunc='sum', sort=False)
        results = df_mean.T.to_dict('list')


        plot_data_quality(category_names_stats, results, 'data_quality'+file_suffix, config['output_folder'])


    # Step 1 : decode data + add absolute time
    if os.path.exists(df1_filepath):
        print("Reading existing dataframe 1 ", end='')
        df = pd.read_feather(df1_filepath)
        print("(%d frames)" % len(df))
    else:

        if len(df)>0:
            df = remove_lsb_cpt_erroneous_frames(df, file_suffix)

            df = decode_TDC_data(df, config, file_suffix)

            # df = drop_adc_columns(df)

            if not skip_adc_correction:
                df = correct_ADC_data_64ch(df, config)

            # save_config_file_copy(config)

            # check_no_retriggering(df, config)
            # analyse_CPT_rate(df, config)
        else:
            print("No data at stage 1")

        df.to_feather(df1_filepath)

        # generate_report(config)


    return df

def analyse_CPT_rate(df, config):

    if 'original_index' not in df.columns:
        return

    board = config['board'][0]
    ck_freq_MHz = config['config_B%d' % board]['tempo_dig_ck']
    x = df.loc[df.original_index < 4000].original_index
    x_valid = df.loc[df.index < 4000].index
    y_ms = df.loc[df.original_index < 4000, 'CPT'] * 1e-3 / ck_freq_MHz  # ms
    y_ms_valid = df.loc[df.index < 4000, 'CPT'] * 1e-3 / ck_freq_MHz  # ms

    data = y_ms.diff()[1:] # / 1e3
    # bins = np.linspace(data.values.min(), data.values.max(), 200)
    data = data[data>0] # negative values probably because events still in the fifo from previous acquisition ?
    logbins = np.logspace(np.log10(data.values.min()), np.log10(data.values.max()), 201)
    mean_time_between_2_fifo_read_ms = np.nanmedian(data[data > 0.01]) * 1e3
    plt.axvline(0.01, color='red', linestyle='--', label='Rate dominated by FIFO (left) & USB (right)')
    plt.axvline(mean_time_between_2_fifo_read_ms, color='green', linestyle='--',
                label='Mean time to drain FIFO via USB = %d ms' % mean_time_between_2_fifo_read_ms)
    plt.hist(data, bins=logbins)
    # plt.hist(data, bins=bins, label='mean_time_between_2_fifo_read = %d ms' % mean_time_between_2_fifo_read_ms)
    plt.yscale("log")
    plt.xscale("log")
    plt.xlabel('Delta time between 2 consecutive valid events [ms]')
    plt.ylabel('Count')
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['output_folder'] + "histo_dt_between_2_consecutives_valid_events.png")
    # plt.show()
    plt.close()

    fig, ax = plt.subplots(figsize=[9, 6])
    index_high = np.argmax(data)  # capture 1st jump due to fifo filling
    xlimit_high = x.iloc[index_high]
    selection = (x <= xlimit_high)
    par = np.polyfit(x[selection], y_ms[selection], 1).tolist()
    frame_bit_count = CONSTANTS.FRAME_LENGTH_RO_MODE_STR[config['config_B%d' % board]['readout_mode']][0]
    max_serialisation_rate_kHz = config['config_B%d' % board]['tempo_dig_ck'] *1e3 / frame_bit_count
    yfit0 = x[selection] * par[0] + par[1]
    if 'hit_freq' in config['config_B%d' % board].keys():
        hit_rate = config['config_B%d' % board]['hit_freq']/1e3
        extra_label = "Hit rate %.2f kHz" % hit_rate
    elif 'rate_Hz' in config.keys():
        hit_rate = config['rate_Hz']/1e3
        extra_label = "Hit rate %.2f kHz" % hit_rate
    else:
        extra_label = "" # todo
    label = "FIFO rate (raw events) = %.2f kHZ (%s  Expected max %d kHz)" % (1 / par[0], extra_label, max_serialisation_rate_kHz)

    ax.plot(x[selection], yfit0, color='orange', ls='dashed', label=label)

    axin = ax.inset_axes((0.63, 0.05, 0.35, 0.4))
    axin.set_xlim(-10, xlimit_high*1.1)
    axin.set_ylim(y_ms[0], y_ms.iloc[index_high]*1.1)
    axin.scatter(x, y_ms, marker='.', s=1)
    axin.set_title("First FIFO filling")
    # axin.plot(x[selection], yfit0, color='orange', linestyle='--')
    # ax.indicate_inset_zoom(axin)

    par0 = np.polyfit(x, y_ms, 1).tolist()
    yfit = x * par0[0] + par0[1]
    ax.scatter(x, y_ms, marker='.', s=1, label="FIFO draining = %d ms (mean)" % mean_time_between_2_fifo_read_ms)
    ax.plot(x, yfit, color='red', linestyle='--', label='System rate (raw events) = %.2f kHz' % (1 / par0[0]))

    par0 = np.polyfit(x_valid, y_ms_valid, 1).tolist()
    yfit = x_valid * par0[0] + par0[1]
    ax.scatter(x_valid, y_ms_valid, marker='.', s=1, color='green')
    ax.plot(x_valid, yfit, color='tab:olive', linestyle='--',
            label='System rate (valid events) = %.2f kHz' % (1 / par0[0]))

    plt.grid()
    plt.xlabel("Frame index")
    plt.ylabel("Event CPT [ms]")
    plt.title("Frame acquisition rate")
    plt.legend(loc='upper left')

    plt.tight_layout()
    plt.savefig(config['output_folder'] + "Frame_acquisition_rate.png")
    # plt.show()
    plt.close()

    # plt.figure()
    # plt.axhline(mean_time_between_2_fifo_read_ms / 1e3, color='red', linestyle='--')
    # # plt.scatter(range(len(data)), data, marker='.', s=1)
    # plt.plot(range(len(data)), data, marker='.')
    # plt.xlabel("Frame index")
    # plt.yscale('log')
    # plt.ylabel('Delta time between 2 consecutive events [s]')
    # plt.grid()
    # plt.tight_layout()
    # plt.savefig(config['output_folder'] + "dt_between_consecutives_valid_events.png")
    # plt.close()

    # plt.show()

def check_no_retriggering(df, config):
    for board in config['board']:
        if 'CPT' in df.columns:
            col_name = 'CPT'
        else:
            col_name = 'CPT_B%d'%board

        if col_name in df.columns:
            CPT_gap_between_2_consecutive_events = df[col_name].diff().value_counts() / len(df) * 100
            if CPT_gap_between_2_consecutive_events.max() > 0.05:
                print("Retriggering WARNING for B%d"%board)
                print(CPT_gap_between_2_consecutive_events)
        else:
            print('skip retriggering check')


def rename_channels_to_64base(df, cluster, board):
    colnames = ['cpt', 'tdc', 'adc', 'tdc_data_valid']  # 'CPT',
    mapper = {colname + "_%s_ch%d" % (gain, ch): colname + "_%s_ch%d_B%d" % (gain, 16*cluster+ch, board) for ch in range(16) for gain in ['low', 'high'] for colname in colnames}
    mapper.update({'trigger_%s' % gain: 'trigger_%s_cluster%d_B%d' % (gain, cluster, board) for gain in ['low', 'high']})
    # new_df = pd.concat([new_df, df[df.cluster == cluster].rename(columns=mapper).drop(['cluster', 'index'], axis=1)], axis=1)
    return df.rename(columns=mapper)

def find_ASIC_data_colnames(filepath):
    # determine if asic data format from DLL
    d = ','
    f = open(filepath, 'r')

    reader = csv.reader(f, delimiter=d)
    ncol = len(next(reader))
    if ncol == 104:
        return CONSTANTS.COLNAMES104
    elif ncol == 106:
        return CONSTANTS.COLNAMES106
    else:
        print("Unknown csv data file format")
        exit(0)

def build_dataframe_from_file(filepath, config):
    # Decoding unchanged with Temporoc3 compared to Temporoc2
    # But field size changed :
    # - msc_cpt: 3 to 4 hexadigits
    # - cpt_low/_high: 1 to 2 hexadigits

    if not os.path.exists(filepath):
        print("File does not exists")
        exit(0)

    # DLL_decodeLib_date = datetime.strptime(config['DLL_decodeLib'][7:], '%Y_%m_%d_%H_%M')
    # date_DLL_in_use = datetime.strptime("2025_02_07_16_00", '%Y_%m_%d_%H_%M')
    #
    # if DLL_decodeLib_date >= date_DLL_in_use:
    #     extra_cols =  []
    # else:
    #     extra_cols = []

    converters = {"time": lambda x: int(x, 16),
                  "msb_cpt": lambda x: int(x, 16),
                  "trigger_low": lambda x: int(x, 16),
                  "trigger_high": lambda x: int(x, 16),
                  'mimic_time': lambda x: int(x, 16),
                  'mimic_time_right_shift_14': lambda x: int(x, 16)}

    converters.update({"cpt_low_ch%d" % i: lambda x: int(x, 16) for i in range(16)})
    converters.update({"tdc_low_ch%d" % i: lambda x: int(x, 16) for i in range(16)})
    converters.update({"adc_low_ch%d" % i: lambda x: int(x, 16) for i in range(16)})
    converters.update({"cpt_high_ch%d" % i: lambda x: int(x, 16) for i in range(16)})
    converters.update({"tdc_high_ch%d" % i: lambda x: int(x, 16) for i in range(16)})
    converters.update({"adc_high_ch%d" % i: lambda x: int(x, 16) for i in range(16)})

    df = pd.read_csv(filepath, names=find_ASIC_data_colnames(filepath), header=None, converters=converters)

    # df.drop(columns=['frames_found', 'bytes_dropped'], axis=1, inplace=True) # ignoring these DLL infos for now

    return df


def remove_lsb_cpt_erroneous_frames(df, file_suffix): # stats_dict, config, init_len):
    init_len = len(df)

    gain_selected_to_trigger_digital = 'low'
    enabled_lsb_cpt_col = [col for col in df.columns if (('cpt_' + gain_selected_to_trigger_digital) in col)]
    # frame_error_list = []

    # events_supposed_simultaneous = 'ext_trigger' in config['test']
    # # Reject frames based on lsb cpt corruption, works only if all channels are triggered externally
    # if events_supposed_simultaneous:
    #     # All lsb should have the same value with external trigger
    #     lsb_cpt_error = df[enabled_lsb_cpt_col].nunique(axis=1) > 2
    #     df = df[~lsb_cpt_error]
    #     lsb_cpt_error_count = sum(lsb_cpt_error)
    #
    #     if lsb_cpt_error_count>0:
    #         print("\t%d (%d %%) more than 2 channels with distinct lsb cpt while triggered simultaneously" % (
    #         lsb_cpt_error_count, lsb_cpt_error_count / init_len * 100))
    #
    #     error_label = 'more_than_2_distinct_lsb_cpt_while_triggered_simultaneously'
    #     if error_label not in stats_dict:
    #         stats_dict['frame_error_' + error_label] = [0] * len(stats_dict['raw_event_count'])
    #     stats_dict['frame_error_' + error_label].append(lsb_cpt_error_count)
    #     frame_error_list.append('frame_error_' + error_label)

    tdc_data_valid_col = [col for col in df.columns if (('tdc_data_valid_' + gain_selected_to_trigger_digital) in col)]

    conv_syst = 'pedestal' in file_suffix
    if not conv_syst:

        # Reject frame based on lsb cpt not matching 6b lsb of CPT
        CPT_6b = np.bitwise_and(df.CPT, 0b111111)
        triggered_channels_of_one_cluster = df[tdc_data_valid_col].values
        lsb_cpt_across_triggered_channels_of_one_cluster = df[enabled_lsb_cpt_col].values
        # np.nan is a float, need to convert int array into float array first
        lsb_cpt_across_triggered_channels_of_one_cluster = np.array(lsb_cpt_across_triggered_channels_of_one_cluster, dtype=float)
        lsb_cpt_across_triggered_channels_of_one_cluster[~triggered_channels_of_one_cluster] = np.nan  # absurd value much higher than lsb_cpt max (2**6-1)
        at_least_one_channel_have_triggered = triggered_channels_of_one_cluster.sum(axis=1) > 0
        # alternative would have been np.array().ravel() to flatten the array if not dealing with it as 2D

        if any(triggered_channels_of_one_cluster.any(axis=1)):
            # at least one lsb_cpt value per frame/row/cluster of 16 ch
            min_lsb_cpt_across_triggered_channels_of_one_cluster = np.nanmin(lsb_cpt_across_triggered_channels_of_one_cluster, axis=1)


            # df['CPT_14b'] = np.bitwise_and(df.CPT, 0b11_1111_1111_1111)
            # df['CPT_6b'].apply(lambda row: hex(row + (1 << 6)))
            # df['CPT_14b'].apply(lambda row: hex(row))
            # df.loc[row_requiring_correctionB == 0, ['min_cpt', 'CPT_6b', 'CPT_14b']]
            delta_lsb_CPT = (CPT_6b - min_lsb_cpt_across_triggered_channels_of_one_cluster)
            # delta_lsb_CPT[~at_least_one_channel_have_triggered] = 0
            # error can be determined only if at least one channel has triggered per cluster

            rows_to_delete = (delta_lsb_CPT < -1) | (delta_lsb_CPT > 0)
            # metastability commands to tolerate shift by 1 or 0
            # metastability due to resync of global cluster event between 6 or 7 clock cycles
            # while lsb_cpt is sampled when tdc data valid rises 7 clocks cycles after async event
            # thus, difference of 0 or 1
            # maybe diff of 2 tolerable

            lsb_cpt_error2_count = sum(rows_to_delete)

            # if verbose:
            #     print("CPT_6b - min(lsb cpt) across channel check data quality transmission")
            #     print(delta_lsb_CPT.value_counts())

            if lsb_cpt_error2_count:
                observed_delay_list = delta_lsb_CPT.value_counts().keys().tolist()
                for expected_value in [0,-1]:
                    if expected_value in observed_delay_list:
                        observed_delay_list.remove(expected_value)
                print("\t%d (%d %%) min lsb cpt too late wrt CPT_6b by (positive values) " % (lsb_cpt_error2_count, lsb_cpt_error2_count / init_len * 100)
                    +str(observed_delay_list))

            df = df[~rows_to_delete]

            # error_label = 'lsb_cpt_too_late_wrt_CPT'
            # if error_label not in stats_dict:
            #     stats_dict['frame_error_' + error_label] = [0] * len(stats_dict['raw_event_count'])
            # stats_dict['frame_error_' + error_label].append(lsb_cpt_error2_count)
            # frame_error_list.append('frame_error_' + error_label)

        # dict_keys_with_error = [k for k, v in stats_dict.items() if 'frame_error_' in k]
        # for dict_key_with_error in dict_keys_with_error:
        #     if dict_key_with_error not in frame_error_list:
        #         stats_dict[dict_key_with_error].append(0)

    return df


# def get_delta_lsb_cpt(df):
#     enabled_lsb_cpt_col = [col for col in df.columns if (('cpt_' + gain_selected_to_trigger_digital) in col)]
#
#     CPT_6b = np.bitwise_and(df.msb_cpt, 0b111111)
#     triggered_channels_of_one_cluster = bool(np.right_shift(df[enabled_lsb_cpt_col], 6))
#     lsb_cpt_across_triggered_channels_of_one_cluster = np.bitwise_and(df[enabled_lsb_cpt_col], 0b111111)
#     lsb_cpt_across_triggered_channels_of_one_cluster[~triggered_channels_of_one_cluster] = 1818 # absurd value
#     at_least_one_channel_have_triggered = triggered_channels_of_one_cluster.sum(axis=1)>0
#
#     min_lsb_cpt_across_triggered_channels_of_one_cluster = lsb_cpt_across_triggered_channels_of_one_cluster.min(
#         axis=1)  # skipna=True by default
#
#     # df['CPT_14b'] = np.bitwise_and(df.CPT, 0b11_1111_1111_1111)
#     # df['CPT_6b'].apply(lambda row: hex(row + (1 << 6)))
#     # df['CPT_14b'].apply(lambda row: hex(row))
#     # df.loc[row_requiring_correctionB == 0, ['min_cpt', 'CPT_6b', 'CPT_14b']]
#     delta_lsb_CPT = (CPT_6b - min_lsb_cpt_across_triggered_channels_of_one_cluster)
#
#     rows_to_delete = ((delta_lsb_CPT > 0) | (delta_lsb_CPT < -2)) & at_least_one_channel_have_triggered
#     # error can be determined only if at least one channel has triggered per cluster
#
#     return delta_lsb_CPT, rows_to_delete

def remove_duplicated_merge_key_row(init_len, df, stats_dict, fi, merge_clusters_based_on):
    # merge_key = 'CPT>>2'
    merge_key = 'CPT'

    if merge_clusters_based_on == merge_key:
        duplicated_CPT_frames = df[merge_key].duplicated(keep=False) # to have all events including duplicated
        duplicated_CPT_count = duplicated_CPT_frames.value_counts()[duplicated_CPT_frames.value_counts().index == True].values
        duplicated_CPT_count = duplicated_CPT_count[0] if duplicated_CPT_count.size>0 else 0

        # df['row_to_remove'] |= duplicated_CPT_frames
        df = df[~duplicated_CPT_frames]
        if 'duplicated_'+merge_key+'_count' not in stats_dict:
            stats_dict['duplicated_'+merge_key+'_count'] = [0] * fi #(len(stats_dict['raw_event_count'])-1)
        stats_dict['duplicated_'+merge_key+'_count'].append(duplicated_CPT_count)

        if duplicated_CPT_count>0:
            print("\t%d (%d %%) events removed because of duplicated CPT>>2 error" % (duplicated_CPT_count, duplicated_CPT_count/init_len*100))

    return df

def remove_status_erroneous_frames(init_len, df, stats_dict, events_supposed_simultaneous=True, verbose=True):
    print("Removed frames because")
    new_stats_dict = {}

    # STATUS error as decoded by the DLL
    status_list = list(np.unique(df.status))
    for status in status_list:
        if status == 0:
            continue
        mask_status = df.status == status
        if status==99:
            status_count = sum(mask_status & (df.bytes_dropped !=0))
            extra=' with non null bytes dropped count during DLL data decoding'
            if status_count>0:
                print("\t%d (%d %%) STATUS %d error"%(status_count, status_count/init_len*100, status)+extra)

        else:
            status_count = sum(mask_status)
            print("\t%d (%d %%) STATUS %d error"%(status_count, status_count/init_len*100, status))

        new_key = 'status_%d_count' % status
        if new_key not in new_stats_dict:
            new_stats_dict[new_key] = []
        new_stats_dict[new_key].append(status_count)

        # df['row_to_remove'] = mask_status
        # df = df[~mask_status].reset_index(drop=True)
        df = df[~mask_status]




    # if merge_clusters_based_on == 'time':
    #     duplicated_time_frames = df.time.duplicated(keep=False) # to have all events including duplicated
    #     duplicated_time_count = duplicated_time_frames.value_counts()[duplicated_time_frames.value_counts().index == True].values
    #     duplicated_time_count = duplicated_time_count[0] if duplicated_time_count else 0
    #
    #     df = df[~duplicated_time_frames]
    #     # df['row_to_remove'] |= duplicated_time_frames
    #
    #     if 'duplicated_time_count' not in stats_dict:
    #         stats_dict['duplicated_time_count'] = [0] * fi #(len(stats_dict['raw_event_count'])-1)
    #     stats_dict['duplicated_time_count'].append(duplicated_time_count)
    #
    #     if verbose:
    #         print("\t%d (%d %%) events removed because of duplicated_time error"%(duplicated_time_count, duplicated_time_count/init_len*100))
    #


    # REMOVING NULL TDC FRAMES
    # # columns_to_apply = [field+'_%s_ch%d' % (gain, channel) for gain in ['low', 'high'] for channel in range(16)]





    # fine_cpt_col = [col for col in df.columns if ('cpt' in col) & ('low' in col)]
    # df['lsb_cpt_all_null'] = (df[fine_cpt_col] == 0).all(axis=1)
    # df['msb_cpt_null'] = df['msb_cpt'] == 0
    # print(df.groupby(['msb_cpt_null', 'lsb_cpt_all_null'],as_index=False).size().apply(lambda x: round(x*100/len(df), 0) if isinstance(x, int) else x))
    # a = df[~df.msb_cpt_null & df.lsb_cpt_all_null]
    # df.drop(['msb_cpt_null', 'lsb_cpt_all_null'], inplace=True, axis=1)

    # REMOVING NULL 10b coarse counter FRAMES
    # if merge_clusters_based_on != 'raw_file_index':
    #     field = 'msb_cpt'
    #
    #     # print('#msb_cpt null ', (df.loc[:, 'msb_cpt'] == 0).value_counts())
    #     tdc_col = [col for col in df.columns if 'tdc' in col]
    #
    #     # at_least_one_tdc_triggered = ~(df.loc[:, tdc_col] == 0).all(axis=1)
    #     # print("at_least_one_tdc_triggered ", at_least_one_tdc_triggered.value_counts())
    #     # print('#msb_cpt null whereas at_least_one_tdc_triggered',
    #     #       (df.loc[at_least_one_tdc_triggered, 'msb_cpt'] == 0).value_counts())
    #
    #     # columns_to_apply = [field+'_%s_ch%d' % (gain, channel) for gain in ['low', 'high'] for channel in range(16)]
    #     columns_to_apply = [col for col in df.columns if field in col]
    #
    #     null_selection = (df.loc[:, columns_to_apply] == 0).all(axis=1) & ((df.loc[:, tdc_col] == 0).all(axis=1))
    #     null_count_array = null_selection.value_counts()[null_selection.value_counts().index == True].values
    #     null_count = null_count_array[0] if null_count_array else 0
    #
    #     if 'all_' + field + '_null_count' not in stats_dict:
    #         stats_dict['all_' + field + '_null_count'] = [0] * fi  # (len(stats_dict['raw_event_count']) - 1)
    #     stats_dict['all_' + field + '_null_count'].append(null_count)
    #     df = df[~null_selection].reset_index(drop=True)
    #
    #     print("%d (%d %%) events removed because all %s is null" % (
    #     null_count, null_count / init_len * 100, field))






    # for field in fields:
    #     if 'all_'+field+'_null_count' not in stats_dict.keys():
    #         stats_dict['all_'+field+'_null_count'].append(0)

    # number_frame_per_injection = round(len(df)/ expected_frame_count)
    # if number_frame_per_injection > 1:
    #     df = df.iloc[0::number_frame_per_injection, :].reset_index(drop=True)

    return df, new_stats_dict


def append_cluster_stats_dict(cluster_stats_dict, stats_dict):

    added_length = 0
    new_erroneous_keys = [k for k, v in cluster_stats_dict.items() if 'status_' in k]
    for new_erroneous_key in new_erroneous_keys:
        if new_erroneous_key not in stats_dict:
            stats_dict[new_erroneous_key] = [0] * len(stats_dict['raw_event_count'])
        a = cluster_stats_dict[new_erroneous_key]
        stats_dict[new_erroneous_key] += a
        added_length = len(a)

    # FILL 0 for none problematic cluster files
    erroneous_keys = [k for k, v in stats_dict.items() if 'status_' in k]
    for erroneous_key in erroneous_keys:
        if erroneous_key not in new_erroneous_keys:
            stats_dict[erroneous_key] += [0]*added_length
    return stats_dict

def remove_retriggering_frames(init_len, df, stats_dict, fi, RO_code, verbose=True):
    
    # Remove retriggering frames
    # assuming that if modeRO contains TDC data and no TDC at all triggered in the received data, then it's a retriggering frame
    if (RO_code & 0b00011) != 0: # TDC data inside
        if (RO_code & 0b00011) == 0b11:
            gain_list = ['low', 'high']
        if (RO_code & 0b00011) == 0b01:
            gain_list = ['low']
        if (RO_code & 0b00011) == 0b10:
            gain_list = ['high']
        tdc_field = ['tdc_%s_ch%d' % (gain, ch) for ch in range(16) for gain in gain_list]
        retriggering_frames = (df[tdc_field]==0).all(axis=1)
        retriggering_frames_count = retriggering_frames.value_counts()[
            retriggering_frames.value_counts().index == True].values
        retriggering_frames_count = retriggering_frames_count[0] if retriggering_frames_count.size>0 else 0

        df = df[~retriggering_frames]
        if 'retriggering_frames' not in stats_dict:
            stats_dict['retriggering_frames'] = [0] * fi
        stats_dict['retriggering_frames'].append(retriggering_frames_count)

        retriggering_error_str = "\t%d (%d %%) events removed because identified as retriggering because all TDC empty" % (
            retriggering_frames_count, retriggering_frames_count / init_len * 100)
        if verbose:
            print(retriggering_error_str)


    # Remove retriggering frames (old)
    # diff = df.CPT.diff()
    # # rows_to_drop = (diff == 1040) | (diff == 1056) | (diff == 2096)
    # rows_to_drop = (diff == 3136) | (diff == 3152) | (diff == 2272) | (diff == 2288) | (diff == 2096) | (diff == 3120) | (diff == 2432)
    # digital_retriggering_array = rows_to_drop.value_counts()[rows_to_drop.value_counts().index == True].values
    # digital_retriggering_count = digital_retriggering_array[0] if digital_retriggering_array else 0
    #
    # if 'digital_retriggering_count' not in stats_dict:
    #     stats_dict['digital_retriggering_count'] = [0] * fi  # (len(stats_dict['raw_event_count']) - 1)
    # stats_dict['digital_retriggering_count'].append(digital_retriggering_count)
    # df = df[~rows_to_drop].reset_index(drop=True)
    #
    # print("%d (%d %%) events removed because retriggering frames" % (
    #     digital_retriggering_count, digital_retriggering_count / init_len * 100))
    
    return df

def adjoin_real_time(df, config):

    if 'delaybox_step' in config['test']:
        methodA = False
        if methodA:
            df['real_time_ns'] = df.delay * 0.01  # ns
        else:
            df_correction = pd.read_csv("../output/tdc_scan/delaybox_step_oscillo_delay/ref_B%d.csv" % config['board'][0])
            df = df.merge(df_correction, on='delay', how='inner')
            df['real_time_ns'] = df.oscilloDelay_mean / 1e3

    elif "Custom step" in config['test']:

        for board in config['board']:
            new_series_set = {}

            # A) Do not take into account missing hit and wrong status
            # df['real_time_ns_A'] = df.index * config['current_step'] * 1e9

            # B) Suffer from the msb_cpt metastability making the count not exactly a multiple of ck_cycles_in_between_2_hits
            # df['real_time_ns_B'] = df['CPT_B%d'%board] / config['ck_cycles_in_between_2_hits'] * config['current_step'] * 1e9

            # C) FINE !
            df['real_time_ns'] = round(df['CPT'] / config['ck_cycles_in_between_2_hits']) * config['current_step'][0] * 1e9
            # df['real_time_ns'] = round(df['CPT_B%d'%board] / config['ck_cycles_in_between_2_hits']) * config['current_step'][0] * 1e9

            # D & E) # Extra step needed BUT they do not work better than C)
            # for channel in config['config_B%d'%board]['enable_TL_ASIC_ch'][0]:
            #     for gain in config['config_B%d'%board]['tdc_injected'][0]:
            #         suffix = '_%s_ch%d_B%d' % (gain, channel, board)
            #
            #         new_series_set['full_cpt'+suffix] = df['CPT_B%d' % board]+df['cpt'+suffix]
            #
            #         new_series_set['real_time_ns'+suffix] = (round(new_series_set['full_cpt'+suffix] / config['ck_cycles_in_between_2_hits'])
            #                                                  * config['current_step'] * 1e9)
            #         # Based on real time
            #         # new_series_set['real_time_ns_2'+suffix] = (round(df['toa_ns'+suffix] / config['ck_cycles_in_between_2_hits'] / (1e3/tempo_dig_ck))
            #         #                                          * config['current_step'] * 1e9)
            # df = pd.concat([df, pd.DataFrame(new_series_set)], axis=1)

            # Plot to check behaviour

            # plt.figure()
            # ch = 43
            # gain = 'low'
            # board = 1
            # channel_suffix = '_%s_ch%d_B%d' % (gain, ch, board)
            # selection = df['tdc_data_valid' + channel_suffix]
            # plt.scatter(df.loc[selection, 'real_time_ns'], df.loc[selection, 'toa' + channel_suffix], label="C")
            # # plt.scatter(df.loc[selection, 'real_time_ns' + channel_suffix], df.loc[selection, 'toa' + channel_suffix], label="D")
            # # plt.scatter(df.loc[selection, 'real_time_ns_2'+channel_suffix], df.loc[selection, 'toa' + channel_suffix], label="E")
            # plt.grid()
            # plt.legend()
            # plt.tight_layout()
            # plt.show()

    return df

def drop_time_columns(df):
    columns_to_drop = (['cpt_low_ch%d'%ch for ch in range(16)] +
                       ['cpt_high_ch%d'%ch for ch in range(16)] +
                       ['tdc_low_ch%d' % ch for ch in range(16)] +
                       ['tdc_high_ch%d' % ch for ch in range(16)])
    df.drop(columns=columns_to_drop, inplace=True)

def drop_adc_columns(df):
    channel_present_in_data_low = {int(col[10:]) for col in df.columns if 'adc_low' in col}
    channel_present_in_data_high = {int(col[11:]) for col in df.columns if 'adc_high' in col}

    columns_to_drop = (['adc_low_ch%d' % ch for ch in channel_present_in_data_low] +
                       ['adc_high_ch%d' % ch for ch in channel_present_in_data_high])

    df.drop(columns=columns_to_drop, inplace=True)

def drop_not_injected_channels_within_cluster(df, config, cluster):
    # apply only on cluster like df
    injected_channel_list = np.array(config['enable_TL_ASIC_ch'])
    cluster_list = injected_channel_list//16
    injected_channel_list_within_current_cluster = injected_channel_list[np.where(cluster_list==cluster)]
    not_injected_channel_list_within_current_cluster = set(injected_channel_list_within_current_cluster%16) ^ set(range(16))

    colnames = ['cpt', 'tdc', 'adc']
    columns_to_drop = [colname+'_'+gain+'_ch%d'%ch for ch in not_injected_channel_list_within_current_cluster
                       for gain in ['low', 'high'] for colname in colnames]
    return injected_channel_list_within_current_cluster, df.drop(columns=columns_to_drop)

def drop_not_injected_channels(df, config):
    # apply only on a df with 64 channels columns

    for board in config['board']:
        board_config = config['config_B%d' % board]
        injected_channel_list = board_config['enable_TL_ASIC_ch'][0]
        # not_injected_channel_list = set(injected_channel_list) ^ set(range(64))
        for meas in ['cpt', 'adc']:
            channel_present_in_data = {int(col[10:]) for col in df.columns if col.startswith(meas+'_low')}
            not_injected_channel_list = set(injected_channel_list) ^ channel_present_in_data
            columns_to_drop = ['%s_%s_ch%d_B%d' % (meas, gain, ch, board) for ch in not_injected_channel_list for gain in ['low', 'high']]
            df.drop(columns=columns_to_drop, inplace=True)



def drop_not_injected_gain(df, config):
    # apply only on a df with 64 channels columns
    columns_to_drop = []
    for board in config['board']:
        board_config = config['config_B%d' % board]
        injected_channel_list = board_config['enable_TL_ASIC_ch'][0]
        not_injected_gain_list = set(board_config['tdc_injected'][0]) ^ {'low', 'high'}

        columns_to_drop += ['%s_%s_ch%d' % (meas, gain, ch) for ch in injected_channel_list for gain in not_injected_gain_list for meas in ['cpt', 'adc']]

    df.drop(columns=columns_to_drop, inplace=True)


def drop_null_TOAc_CALc_frames(df):
    print("Deleting null TOAc CALc data for all channels of a cluster : ")
    init_len = len(df)
    nb_cluster_channels = 16
    channel_gain_list = ['low', 'high']
    # with alive_bar(4*nb_cluster_channels * len(channel_gain_list), force_tty=True) as bar:
    for cluster in range(4):
        cluster_selection = df.cluster == cluster
        selection_to_keep_cluster_wise = np.array([True]*len(df[cluster_selection]))

        for cluster_channel in range(nb_cluster_channels):
            for channel_gain in channel_gain_list:
                cluster_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)
                # bar()
                selection_to_keep_cluster_wise |= ((df.loc[cluster_selection, 'TOAcoarse'+cluster_suffix] != 0) & (df.loc[cluster_selection, 'CALcoarse'+cluster_suffix] != 0))
                # print(selection_to_keep_cluster_wise.value_counts())
        df.loc[cluster_selection, 'selection_to_keep']=selection_to_keep_cluster_wise

    df = df.loc[df.selection_to_keep, :].reset_index()
    final_len = len(df)
    print((init_len-final_len)/init_len*100, "% deleted frames ")
    return df

def decode_TDC_data_cluster_like(df):

    for cluster in range(4):
        cluster_selection = df.cluster==cluster
        for cluster_channel in range(16):
            for channel_gain in ['low', 'high']:
                cluster_suffix = '_%s_ch%d' % (channel_gain, cluster_channel)
                matrix_suffix = '_%s_ch%d' % (channel_gain, cluster*16+cluster_channel)

                # df['bin'] = tdc_value.apply(lambda x: bin(x)[2:].zfill(18))
                tdc_value = df.loc[cluster_selection, 'tdc' + cluster_suffix]
                # method 3
                # df['CALcoarse'] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 14)  # 4 bits
                # df['CALfine'] = tdc_value.apply(lambda x: (x &        0b11_1110_0000_0000) >> 9)  # 5 bits
                # df['TOAcoarse'] = tdc_value.apply(lambda x: (x &            0b1_1110_0000) >> 5)  # 4 bits
                # df['TOAfine'] = tdc_value.apply(lambda x: x &                    0b1_1111)  # 5 bits

                # # method 2
                df.loc[cluster_selection, 'TOAcoarse'+matrix_suffix] = tdc_value.apply(lambda x: (x & 0b11_1100_0000_0000_0000) >> 14)  # 4 bits
                df.loc[cluster_selection, 'TOAfine'+matrix_suffix] = tdc_value.apply(lambda x: (x &        0b11_1110_0000_0000) >> 9)  # 5 bits
                df.loc[cluster_selection, 'CALcoarse'+matrix_suffix] = tdc_value.apply(lambda x: (x &            0b1_1110_0000) >> 5)  # 4 bits
                df.loc[cluster_selection, 'CALfine'+matrix_suffix] = tdc_value.apply(lambda x: x &                    0b1_1111)  # 5 bits

                # FPGA counter driven by temporoc coarse counter overflow : 51.2 µs period = 2**14*3.125 ns
                #   ovf reset counter is reset when reset fifo
                # + digital cluster-wise MSB counter: 10 bits at 20 MHz (2**4*3.125ns period)
                # + digital channel-wise LSB counter: 4 bits at 320 MHz
                df.loc[cluster_selection, 'CPT'+matrix_suffix] = df.time.apply(lambda x: x << 14) + df.msb_cpt.apply(lambda x: x << 4) + df['cpt_%s_ch%d' % (channel_gain, cluster_channel)]
                # df['CPT'] = df.msb_cpt.apply(lambda x: x << 4) + df['cpt_%s_ch%d' % (channel_gain, channel)]
                # df['CPT'] -= df.CPT.min()


    return df


def trigger_table_in_data(config, board):
    ROmode_str = config['config_B%d'%board]['readout_mode']
    ROmode_code = CONSTANTS.FRAME_LENGTH_RO_MODE_STR[ROmode_str][1]
    return np.bool_((ROmode_code & 0b10000)>>4)

def find_offset_based_on():
    pass


def find_ROmode(df, config):
    if len(np.unique(df['mode'])) == 1:
        ROmode = np.unique(df['mode'])[0]
    else:
        print("Can not proceed with offset identification with several ROmode in dataset. "
              "Truncate the data to a single readout mode")
        board = config['board'][0]
        ROmode = config['config_B%d'%board]['readout_mode_code']
    return ROmode

def remove_blank_datavalid_frames(df, ROmode, res):
    # dataset needs to be cleaned from retriggering blank frames

    fraction_blank_frames = 0
    cpt_list = []
    cpt_high_list = ['cpt_high_ch%d' % ch for ch in range(16)]
    cpt_low_list = ['cpt_low_ch%d' % ch for ch in range(16)]

    if (ROmode != 0) & (ROmode != 0b10000):
        if (ROmode & 0b0001) | ((ROmode & 0b0100) >> 2):  # low gain cpt
            cpt_list += cpt_low_list
        elif ((ROmode & 0b0010) >> 1) | ((ROmode & 0b1000) >> 3):  # high gain cpt
            cpt_list += cpt_high_list

        if ROmode == 18:
            cpt_list = cpt_low_list  # error in DLL

        # Truncate frame where tdc have actually converted a trigger and produced a datavalid (bit 6 of lsb cpt)
        mask = (df[cpt_list] == 0).all(axis=1)
        fraction_blank_frames = np.sum(mask / len(df))
        df2 = df[~mask]

        # Could also identify wrong frames with mismatch between trigger table (on level) and tdc data valid (on edge)
        # but works only for modes with trigger table included in the frame
    else:
        df2 = df.copy()
        # No need to identify retriggering frames for these readout mode !

    res.update({'fraction_blank_frames': ["{:06.0f}".format(fraction_blank_frames)]})

    return df2, fraction_blank_frames

def find_most_likely_offset(df2, res):
    offsets = ((df2['mimic_time'] - df2['msb_cpt']) % 2 ** 14).value_counts() / len(df2)
    # print(a)
    if len(offsets) > 0:
        offset = offsets.index[0] - 1
        # -1 so c does not contain values = 2**14 = 16384
    else:
        print("No offset could be found")
        pass
        exit()
    res.update({'offset_proba%d' % i: ["{:06f}".format(offsets.iloc[i])] for i in range(len(offsets))})
    res.update({'offset%d' % i: ["{:06d}".format(offsets.index[i])] for i in range(len(offsets))})

    return offsets, offset

def predict_CPT(df, offset, ROmode):

    # Use offset to predict time (ovf counter), thus CPT
    c = np.bitwise_and(df['mimic_time'] - offset - df['msb_cpt'], 0x3fff)
    # print(c.value_counts())
    offset_corrected = offset + (c <= CONSTANTS.FRAME_LENGTH_RO_MODE_INT[ROmode]) * c

    predicted_time_left_shift_14 = np.bitwise_and(df['mimic_time'] - offset_corrected, 0xffff_c000)
    # df['offset_corrected'] = offset_corrected
    # df['c']=c
    # df['predicted_time'] = np.right_shift(predicted_time_left_shift_14, 14)
    # df['col'] = df['mimic_time'] - (np.left_shift(df['time'],14)+df['msb_cpt'])
    # d = df.loc[
    #     df['predicted_time'] != df['time'], ['predicted_time', 'mimic_time', 'mimic_time_right_shift_14', 'time', 'msb_cpt',
    #                                          'offset_corrected', 'c', 'col']]
    # df.loc[df['predicted_time'] != df['time'], ['predicted_time', 'time']]
    predicted_CPT = predicted_time_left_shift_14 + df.msb_cpt

    return predicted_CPT

def check_CPT_prediction(true_CPT, predicted_CPT, file_suffix, res):
    fraction_events_corrected = "{:06f}".format(0)
    because_of_time_late = 0

    b = (true_CPT - predicted_CPT).value_counts() / len(predicted_CPT)
    extra_label = ''
    if 0 in b.index:
        fraction_events_corrected = "{:06f}".format(b[0])
        if b[0] != 1:  # partially corrected
            mimic_counter_failed = np.sum((true_CPT - predicted_CPT) != 0)
            because_of_time_late = np.sum((true_CPT - predicted_CPT) == 2 ** 14)
            # reference is wrong
            extra_label = (" mimic worked for %.2f %% events. %d failed %d because of time late"
                           % (b[0] * 100, mimic_counter_failed, because_of_time_late))
        else:
            extra_label = ' perfect'
    else:
        print(file_suffix + ' not corrected at all')
        print(b)

    res.update({'delta_proba%d' % i: ["{:06f}".format(b.iloc[i])] for i in range(len(b))})
    res.update({'delta%d' % i: ["{:06d}".format(b.index[i])] for i in range(len(b))})
    res.update({'fraction_events_corrected': [fraction_events_corrected],
                'fraction_fpga_time_late_can_not_be_trusted': ["{:06f}".format(because_of_time_late / len(predicted_CPT))]})

    return extra_label


def compute_mimic_offset(config, file_suffix, ROmode_from_data, res):

    # FIND SC parameters for formula
    if 'conf' in file_suffix:
        conf = int(re.findall("(?<=conf)[0-9]+", file_suffix)[0])
        res.update({'conf': [conf]})
        # use conf table
        df_conf = pd.read_csv(config['save_folder'] + 'conf.csv')
        ROmode = df_conf.loc[df_conf['conf']==conf, 'ROmode'].iloc[0]
        event_window_length = df_conf.loc[df_conf['conf']==conf, 'event_window_length'].iloc[0]
        adc_mux = df_conf.loc[df_conf['conf']==conf, 'adc_mux'].iloc[0]
        shaper_delay_length = df_conf.loc[df_conf['conf']==conf, 'shaper_delay_length'].iloc[0]
    else:
        # use config.yaml table
        ROmode = config['config_B%d'%(config['board'][0])]['readout_mode_code']

        SC_df = pd.read_csv(config['save_folder'] + 'i2c_df.csv')
        event_window_length = (SC_df.loc[(SC_df['add']==65)&(SC_df['subadd']==10), 'data'] & 0b111111)
        adc_mux = (SC_df.loc[(SC_df['add']==66)&(SC_df['subadd']==5), 'data'] >> 7)
        adc_mux = 'slow' if adc_mux == 1 else 'fast'
        shaper_delay_length = (SC_df.loc[(SC_df['add']==65)&(SC_df['subadd']==9), 'data'] & 0b11111)

    assert ROmode==ROmode_from_data, 'Readout mode in conf table different than in dataframes'

    # All offset delay in 320 MHz clock period unit
    extra_delay = 29
    adc_fast_conversion_time = 621
    extra_adc_conversion_time = 309

    adc_field = (ROmode&0b01100 != 0)
    slow_adc = (adc_mux == 'slow')
    offset = (adc_fast_conversion_time + extra_adc_conversion_time*slow_adc + shaper_delay_length*4)*adc_field
    offset += event_window_length + CONSTANTS.FRAME_LENGTH_RO_MODE_INT[ROmode] + extra_delay

    return offset


def decode_CPT_data(df, config, cluster, file_suffix, use_mimic_offset_table=False):
    new_series_set = {}

    ROmode = find_ROmode(df, config)
    time_stamp_found = False
    cols_to_drop = []

    if 'time' in df.columns:
        cols_to_drop += ['time']

        if (df['time']!=0).any():
            print("\tWill use overflow counter incremented by ASIC")

            # Will compute CPT from time
            true_CPT = np.left_shift(df['time'], 14) + df.msb_cpt
            time_stamp_found = True

            # USE true FPGA counter of TEMPOROC clusters coarse counter overflows
            # BEST options but costs 2 extra wires from ASIC to FPGA per cluster (4x2 per ASIC)
            # Not completely immune to errors but < 0.3 %
            new_series_set['CPT'] = true_CPT

    if 'mimic_time' in df.columns:

        cols_to_drop += ['mimic_time', 'mimic_time_right_shift_14']
        if (df['mimic_time']!=0).all():
            print("\tWill use mimic overflow counter inside FPGA")
            # Will compute CPT from MIMIC time
            # compute counter overflows using cluster coarse counter copy within FPGA
            res = {'cluster':[cluster], '#events':[len(df)]}
            time_stamp_found = True


            # FIND OFFSET within the data assuming no hit saturation
            df2, fraction_blank_frames = remove_blank_datavalid_frames(df, ROmode, res)
            if use_mimic_offset_table:
                print("used tabulated offset")
                offset = compute_mimic_offset(config, file_suffix, ROmode, res)
            else:
                offsets, offset = find_most_likely_offset(df2, res)

            predicted_CPT = predict_CPT(df, offset, ROmode)
            new_series_set['CPT'] = predicted_CPT

            # CHECK CPT predicted with true CPT (if exists)
            extra_label = ''
            if 'time' in df.columns:
                if (df['time'] != 0).all():
                    extra_label = check_CPT_prediction(true_CPT, predicted_CPT, file_suffix, res)

            # SAVE
            offset_stat_file = config['save_folder'] + '../offset_stats.csv'
            if os.path.exists(offset_stat_file):
                offset_df = pd.read_csv(offset_stat_file)
                offset_df = pd.concat([offset_df, pd.DataFrame(res)])
            else:
                offset_df = pd.DataFrame(res)
            offset_df.to_csv(offset_stat_file, index=False)

            # PRINT
            print("Blank frames = %d %%      offset = %d %s"%(fraction_blank_frames*100, offset, extra_label))
            pass


    if not time_stamp_found:
        print("No overflow counter in dataset, "
              "can not compute an absolute time (after rstb release) longer than ASIC coarse counter range on 14 bits at 320 MHz = 51 µs")
        exit()

    df.drop(labels=cols_to_drop, axis="columns", inplace=True)
    df = pd.concat([df, pd.DataFrame(new_series_set)], axis=1)

    return df

def correct_overflow_counter_in_CPT_data(df):
    # correct overflow CPT

    df.loc[df['CPT'].diff(-1)>0, 'CPT'] -= 2**14

    # df['time'] = np.right_shift(df['CPT'], 14).apply(lambda row: hex(row))
    # df['msb'] = np.right_shift(np.bitwise_and(df['CPT'], 0b11_1111_1111_0000), 4).apply(lambda row: hex(row))
    # df[['CPT', 'time', 'msb', 'CPT_diff']].iloc[:10]
    return df

def correct_lsb_cpt_data_from_expected_overflow(df, config, init_len):
    replaced_series_set = {}
    new_series_set = {}

    for board in config['board']:
        # channel_list = config['config_B%d'%board]['enable_TL_ASIC_ch'][0]
        gain_list = config['config_B%d'%board]['tdc_injected'][0]
        for gain in gain_list:
            row_requiring_correction_count_per_ch = []

            for channel in range(16):
                cluster_suffix = '_%s_ch%d' % (gain, channel)

                tdc_data_valid = np.bool_(np.right_shift(np.bitwise_and(df['cpt' + cluster_suffix], 0b1_000_000), 6))
                new_series_set['tdc_data_valid' + cluster_suffix] = tdc_data_valid

                # Correction to compensate lsb_cpt 6b overflows based on CPT counter where all 14b are saved for the first event occuring
                lsb_cpt = np.bitwise_and(df['cpt' + cluster_suffix], 0b0_111_111) #+ row_requiring_correctionB
                cluster_CPT_6b = np.bitwise_and(df['CPT'], 0b111111)
                row_requiring_correctionA = (lsb_cpt < cluster_CPT_6b) * tdc_data_valid
                replaced_series_set['cpt' + cluster_suffix] = lsb_cpt + (row_requiring_correctionA * 64)
                # replaced_series_set['cpt' + cluster_suffix] = lsb_cpt
                # replaced_series_set['cpt' + cluster_suffix] = lsb_cpt
                # new_series_set['cpt_corrected' + cluster_suffix] = row_requiring_correctionA
                row_requiring_correction_count = row_requiring_correctionA.value_counts()[row_requiring_correctionA.value_counts().index == True].values
                row_requiring_correction_count_per_ch.append((row_requiring_correction_count[0] if row_requiring_correction_count.size > 0 else 0) / init_len * 100)


    df.drop(labels=list(replaced_series_set.keys()), axis="columns", inplace=True)
    df = pd.concat([df.reset_index(drop=True),
                    pd.DataFrame(new_series_set),
                    pd.DataFrame(replaced_series_set).reset_index(drop=True)], axis=1)


    # gain_selected_to_trigger_digital='low'
    # enabled_lsb_cpt_col = [col for col in df.columns if (('cpt_' + gain_selected_to_trigger_digital) in col)]
    # crpt = [col for col in df.columns if (('crpt_' + gain_selected_to_trigger_digital) in col)]
    # tdc_data_valid_col = [col for col in df.columns if (('tdc_data_valid_' + gain_selected_to_trigger_digital) in col)]
    #
    # CPT_6b = np.bitwise_and(df.msb_cpt, 0b111111)
    # triggered_channels_of_one_cluster = df[tdc_data_valid_col].values
    # lsb_cpt_across_triggered_channels_of_one_cluster = df[enabled_lsb_cpt_col].values
    # # np.nan is a float, need to convert int array into float array first
    # lsb_cpt_across_triggered_channels_of_one_cluster = np.array(
    #     lsb_cpt_across_triggered_channels_of_one_cluster, dtype=float)
    # lsb_cpt_across_triggered_channels_of_one_cluster[~triggered_channels_of_one_cluster] = np.nan  # absurd value much higher than lsb_cpt max (2**6-1)
    # at_least_one_channel_have_triggered = triggered_channels_of_one_cluster.sum(axis=1) > 0
    # # alternative would have been np.array().ravel() to flatten the array if not dealing with it as 2D
    #
    # try:
    #     min_lsb_cpt_across_triggered_channels_of_one_cluster = np.nanmin(
    #         lsb_cpt_across_triggered_channels_of_one_cluster, axis=1)  # skipna=True by default
    # except RuntimeWarning:
    #     pass
    #
    # delta_lsb_CPT = (CPT_6b - min_lsb_cpt_across_triggered_channels_of_one_cluster)
    # # delta_lsb_CPT[~at_least_one_channel_have_triggered] = 0
    # # error can be determined only if at least one channel has triggered per cluster
    #
    # # rows_to_delete = ((delta_lsb_CPT > 0) | (delta_lsb_CPT < -2))
    # rows_to_delete = (delta_lsb_CPT < -1) | (delta_lsb_CPT > 0)
    # # metastability commands to tolerate shift by 1 or 0
    # # metastability due to resync of global cluster event between 6 or 7 clock cycles
    # # while lsb_cpt is sampled when tdc data valid rises 7 clocks cycles after async event
    # # thus, difference of 0 or 1
    #
    # lsb_cpt_error2_count = sum(rows_to_delete)
    # pass

    return df

def get_toa_cal_from_tdc(tdc_value):
    toa_fine = np.right_shift(np.bitwise_and(tdc_value, 0b11_1110_0000_0000_0000), 13)  # 5 bits
    toa_coarse = np.right_shift(np.bitwise_and(tdc_value, 0b1_1110_0000_0000), 9)  # 5 bits4
    cal_fine = np.right_shift(np.bitwise_and(tdc_value, 0b1_1111_0000), 4)  # 5 bits
    cal_coarse = np.bitwise_and(tdc_value, 0b1111)  # 4 bits
    toa = toa_fine + 31 * toa_coarse
    cal = cal_fine + 31 * cal_coarse  # new_series_set['cal' + cluster_suffix]
    return toa_fine, toa_coarse, cal_fine, cal_coarse, toa, cal

def decode_TDC_data(df, config, file_suffix, tolerated_delta_error = 0.1):

    if 'pedestal' in file_suffix:
        print('Ignoring trigger and time related data when using conv_syst ')
        return df
    

    df2_file = config['output_folder']+"01.feather"
    if os.path.exists(df2_file):
        df = pd.read_feather(df2_file)
    else:
        start = time.perf_counter()
        new_series_set = {}
        to_destroy_series_set = {}
        expected_delta = 140

        for board in config['board']:

            # channel_list = config['config_B%d'%board]['enable_TL_ASIC_ch'][0]
            # gain_list = config['config_B%d'%board]['tdc_injected'][0]
            # for gain in gain_list:
            #     for channel in channel_list:
            # cluster_suffix = '_%s_ch%d_B%d' % (gain, channel, board)

            # cluster_suffix = ['_%s_ch%d_B%d' % (gain, ch, board) for ch in range(64) for gain in ['low', 'high']]
            cluster_suffix_list = [col[3:] for col in df.columns if 'cpt' in col]
            for cluster_suffix in cluster_suffix_list:
                    gain = 'low' if 'low' in cluster_suffix else 'high'
                    channel = int(re.findall("(?<=_ch)[0-9]+", cluster_suffix)[0])

                    # Decode TDC fields
                    tdc_value = df.loc[:, 'tdc' + cluster_suffix]
                    toa_fine, toa_coarse, cal_fine, cal_coarse, toa, cal = get_toa_cal_from_tdc(tdc_value)
                    new_series_set['toa' + cluster_suffix] = toa

                    delta = cal - new_series_set['toa' + cluster_suffix]
                    new_series_set['delta' + cluster_suffix] = delta

                    if trigger_table_in_data(config, board):
                        cluster = channel//16
                        no_trigger = ~np.bool_(np.right_shift(np.bitwise_and(df['trigger_%s_cluster%d_B%d'%(gain, cluster, board)].astype(np.uint64), np.uint64(1<<channel)), channel))
                    else:
                        # can not compare tdc data valid with trigger table (because not serialiased)
                        no_trigger = np.array([False]*len(df))

                    # Error checks for temporoc3
                    delta_out_of_range = ((delta<((1-tolerated_delta_error)*expected_delta)) | (delta>((1+tolerated_delta_error)*expected_delta))).values
                    tdc_data_not_valid = ~df['tdc_data_valid' + cluster_suffix].values
                    tdc_data_null = (df['tdc' + cluster_suffix] == 0).values

                    time_error_code = (no_trigger<<3) + (delta_out_of_range<<2) + (tdc_data_null<<1) + tdc_data_not_valid
                    new_series_set['time_error' + cluster_suffix] = time_error_code

                    # suspected_error = delta_out_of_range | tdc_data_not_valid | tdc_data_null | no_trigger
                    # new_series_set['tdc_good' + cluster_suffix] = ~suspected_error

        # df.drop(labels=list(replaced_series_set.keys()), axis="columns", inplace=True)
        df = pd.concat([df, pd.DataFrame(new_series_set)], axis=1) # pd.DataFrame(replaced_series_set)

        tdc_raw_col = [col for col in df.columns if ('tdc' in col) & ('tdc_data_valid' not in col) & ('tdc_good' not in col)]
        df.drop(labels=tdc_raw_col, axis="columns", inplace=True)

        # rows_to_destroy = pd.DataFrame(to_destroy_series_set).any(axis=1)
        # df = df.loc[~rows_to_destroy,:]

        stop = time.perf_counter()
        print("Time elapsed %d s"%(stop-start))


    if False:
        for board in config['board']:
            for i in range(len(df)//50):
                plt.figure(figsize=(10, 10))
                ax = plt.subplot(1, 1, 1)
                # time_error_col = [col for col in df.columns if ('time_error' in col)]
                time_error_col = ['time_error_%s_ch%d_B%d'%(gain, ch, board) for ch in range(64) for gain in ['low', 'high']]
                time_error_col_label = [str(ch) if gain=='L' else '' for ch in range(64) for gain in ['L', 'H']]
                # print(time_error_col)
                map = df[time_error_col].iloc[i*50:(i+1)*50]
                im = plt.imshow(map.values, origin='lower', vmin=0, vmax=15, aspect='auto')
                # plt.title(metric + ' time difference')
                xrange = range(len(map.columns))
                yrange = range(len(map.index))
                # plt.xticks(xrange, map.columns)
                plt.xticks(xrange, time_error_col_label)

                plt.yticks(yrange, map.index + 1)  # comparison channels
                # plt.xlabel("Delay [ns]")
                # plt.ylabel("Comparison channel")
                cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

                # cbar.ax.get_yaxis().set_ticks([])
                # time_error_label_list = []
                # for error in range(15,-1,-1):
                #     time_error_label = ''
                #     if error & 0b1000:
                #         time_error_label += 'no trigger'
                #     if error & 0b0100:
                #         time_error_label += '+ delta out of range'
                #     if error & 0b0010:
                #         time_error_label += '+ tdc data null'
                #     if error & 0b0001:
                #         time_error_label += '+ no TDC data valid'
                #     # time_error_label+='$'
                #     time_error_label_list.append(time_error_label)
                # print(time_error_label_list)
                # for j, lab in enumerate(time_error_label):
                #     cbar.ax.text(.5, (2 * j + 1) / 8.0, lab, ha='center', va='center')
                # cbar.ax.get_yaxis().labelpad = 15
                # cbar.ax.set_ylabel('# of contacts', rotation=270)

                # # write number
                # for y in range(15):
                #     for x in xrange:
                #         ax.text(x, y, map_channels_vs_delay.loc[y, x], ha="center", va="top", color="w", fontsize=8)

                # plt.tight_layout()
                figManager = plt.get_current_fig_manager()
                figManager.window.showMaximized()
                plt.savefig(config['output_folder'] + "/heatmap_time_error.png")
                plt.show()




    return df


def decode_TDC_data0(df, config, file_suffix, tolerated_delta_error=0.1):
    # nb_cluster_channels = 16
    # channel_gain_list = ['low', 'high']

    if 'pedestal' in file_suffix:
        print('Ignoring trigger and time related data when using conv_syst ')
        return df

    start = time.perf_counter()

    # cluster_suffix_list = np.unique([col[3:] for col in df.columns if ('_low_' in col) or ('_high_' in col)])
    # cluster_suffix_list = []
    # for element in itertools.product(config['enable_TL_ASIC_ch'][0], repeat=len(config['tdc_injected'][0])):
    #     cluster_suffix_list += ['_%s_ch%d'%(gain, channel) for gain, channel in zip(config['tdc_injected'][0], element)]
    # cluster_suffix_list = ['_%s_ch%d'%(gain, channel) for channel in range(64) for gain in ['low', 'high']]

    new_series_set = {}
    to_destroy_series_set = {}
    replaced_series_set = {}
    # with alive_bar(len(cluster_suffix_list), force_tty=True) as bar:
    expected_delta = 140

    for board in config['board']:

        channel_list = config['config_B%d' % board]['enable_TL_ASIC_ch'][0]
        gain_list = config['config_B%d' % board]['tdc_injected'][0]
        # gain_list = ['low', 'high']
        init_len = len(df)

        for gain in gain_list:

            missing_channels = []
            data_valid_high_but_no_tdc_data_count_per_ch = []  # per channel
            data_valid_low_but_tdc_data_count_per_ch = []
            # row_requiring_correction_count_per_ch = []
            tdc_has_NOT_triggered_count_per_ch = []
            data_valid_high_but_no_trigger_in_table_count_per_ch = []
            no_data_valid_but_trigger_in_table_count_per_ch = []

            for channel in channel_list:

                cluster_suffix = '_%s_ch%d_B%d' % (gain, channel, board)
                error_msg = ""
                lsb_cpt_error = False

                if ('tdc' + cluster_suffix) not in df.columns:
                    missing_channels.append(channel)

                    data_valid_high_but_no_tdc_data_count_per_ch.append(np.nan)
                    data_valid_low_but_tdc_data_count_per_ch.append(np.nan)
                    # row_requiring_correction_count_per_ch.append(np.nan)
                    tdc_has_NOT_triggered_count_per_ch.append(np.nan)
                    data_valid_high_but_no_trigger_in_table_count_per_ch.append(np.nan)
                    no_data_valid_but_trigger_in_table_count_per_ch.append(np.nan)

                    continue
                tdc_value = df.loc[:, 'tdc' + cluster_suffix]

                # Decode TDC fields
                toa_fine, toa_coarse, cal_fine, cal_coarse, toa, cal = get_toa_cal_from_tdc(tdc_value)
                new_series_set['toa' + cluster_suffix] = toa

                tdc_data_valid = df['tdc_data_valid' + cluster_suffix]
                tdc_has_triggered_count = sum(tdc_data_valid)

                delta = cal - new_series_set['toa' + cluster_suffix]
                new_series_set['delta' + cluster_suffix] = delta
                error_e = ((delta < ((1 - tolerated_delta_error) * expected_delta)) | (
                            delta > ((1 + tolerated_delta_error) * expected_delta))) & tdc_data_valid
                error_e_count = np.sum(error_e)

                # new_series_set['delta' + cluster_suffix] =
                # new_series_set['lsb_fromCAL' + cluster_suffix] = np.abs(2 * 3.125 / new_series_set['delta' + cluster_suffix])

                # new_series_set['toa_with_1b_cpt' + cluster_suffix] = np.bitwise_and(df['cpt'+cluster_suffix], 1) + new_series_set['toa' + cluster_suffix]
                # new_series_set['toa_ns' + cluster_suffix] = new_series_set['CPT' + cluster_suffix] + new_series_set['toa' + cluster_suffix]

                # print(new_series_set[['status', 'TOAcoarse', 'CALcoarse', 'TOAfine', 'CALfine', 'msb_cpt_modulo_hit_period']].drop_duplicates())

                tdc_has_NOT_triggered_count = (init_len - tdc_has_triggered_count)
                tdc_has_NOT_triggered_count_per_ch.append(tdc_has_NOT_triggered_count / init_len * 100)

                if (tdc_has_triggered_count > 0) & (tdc_has_triggered_count != init_len) & (
                        'pedestal' not in file_suffix):
                    # conv_syst should not generate lsb_cpt_error (as with pedestal)
                    lsb_cpt_error = True
                    # error_msg+= " %d (%.2f %%) tdc has missing data valid " % (tdc_has_NOT_triggered_count, tdc_has_NOT_triggered_count / init_len * 100)

                # checks for temporoc3
                # brand_new_series_set['tdc_data_valid' + cluster_suffix] = df['tdc' + cluster_suffix] != 0  # at least TDC triggered
                error_a = ~tdc_data_valid & (df['tdc' + cluster_suffix] != 0)
                error_a_count = error_a.value_counts()[error_a.value_counts().index == True].values
                error_a_count = error_a_count[0] if error_a_count.size > 0 else 0

                error_b = tdc_data_valid & (df['tdc' + cluster_suffix] == 0)
                error_b_count = error_b.value_counts()[error_b.value_counts().index == True].values
                error_b_count = error_b_count[0] if error_b_count.size > 0 else 0

                if trigger_table_in_data(config, board):
                    cluster = channel // 16
                    ch_has_triggered = np.bool_(np.right_shift(
                        np.bitwise_and(df['trigger_%s_cluster%d_B%d' % (gain, cluster, board)].astype(np.uint64),
                                       np.uint64(1 << channel)), channel))
                    error_c = tdc_data_valid & ~ch_has_triggered
                    error_c_count = np.sum(error_c)

                    error_d = ~tdc_data_valid & ch_has_triggered
                    error_d_count = np.sum(error_d)
                else:
                    # can not compare tdc data valid with trigger table (because not serialiased)
                    error_c = np.array([False] * len(df))
                    error_d = np.array([False] * len(df))
                    error_c_count = error_d_count = 0

                data_valid_low_but_tdc_data_count_per_ch.append(error_a_count / init_len * 100)
                data_valid_high_but_no_tdc_data_count_per_ch.append(error_b_count / init_len * 100)
                data_valid_high_but_no_trigger_in_table_count_per_ch.append(error_c_count / init_len * 100)
                no_data_valid_but_trigger_in_table_count_per_ch.append(error_d_count / init_len * 100)

                if error_e_count > 0:
                    error_msg += " %d (%d %%) delta is off by %d %% from expected (%d) " % (error_e_count,
                                                                                            error_e_count / init_len * 100,
                                                                                            tolerated_delta_error * 100,
                                                                                            expected_delta)
                    lsb_cpt_error = True

                if error_a_count > 0:
                    error_msg += " %d (%d %%) tdc data but no data valid " % (error_a_count,
                                                                              error_a_count / init_len * 100)
                    lsb_cpt_error = True

                if error_b_count > 0:
                    error_msg += " %d (%d %%) no tdc data but tdc data valid " % (error_b_count,
                                                                                  error_b_count / init_len * 100)
                    lsb_cpt_error = True

                if error_c_count > 0:
                    error_msg += " %5d (%d %%) tdc data valid but no trigger in table " % (error_c_count,
                                                                                           error_c_count / init_len * 100)
                    lsb_cpt_error = True

                if error_d_count > 0:
                    error_msg += " %d (%d %%) no tdc data valid but trigger in table " % (error_d_count,
                                                                                          error_d_count / init_len * 100)
                    lsb_cpt_error = True

                if lsb_cpt_error:
                    print("\t" + cluster_suffix[1:] + error_msg)

                suspected_error = error_a | error_b | error_c | error_d | error_e
                # to_destroy_series_set['row_to_drop' + cluster_suffix] = suspected_error
                new_series_set['tdc_good' + cluster_suffix] = (~suspected_error) & tdc_data_valid

            if len(missing_channels) > 0:
                print(f"Missing {gain} tdc data for channels " + str(missing_channels))

            plt.figure(figsize=(10, 7))
            plt.title("TDC decoding errors for %s gain" % gain)
            plt.plot(channel_list, data_valid_high_but_no_tdc_data_count_per_ch,
                     label='TDC data valid high but no data')
            plt.plot(channel_list, data_valid_low_but_tdc_data_count_per_ch, label='TDC data valid low but data')
            # plt.plot(channel_list, row_requiring_correction_count_per_ch, label='lsb cpt overflow')
            # plt.plot(channel_list, tdc_has_NOT_triggered_count_per_ch, label='No TDC data valid')
            plt.xlabel('Channel')
            plt.ylabel('Error/total events readout [%]')
            plt.grid()
            plt.legend()
            plt.tight_layout()
            plt.savefig(config['output_folder'] + '/TDC_decoding_errors.png')
            # plt.show()
            plt.close()

    df.drop(labels=list(replaced_series_set.keys()), axis="columns", inplace=True)
    df = pd.concat([df, pd.DataFrame(new_series_set), pd.DataFrame(replaced_series_set)], axis=1)

    tdc_raw_col = [col for col in df.columns if
                   ('tdc' in col) & ('tdc_data_valid' not in col) & ('tdc_good' not in col)]
    df.drop(labels=tdc_raw_col, axis="columns", inplace=True)

    # rows_to_destroy = pd.DataFrame(to_destroy_series_set).any(axis=1)
    # df = df.loc[~rows_to_destroy,:]

    stop = time.perf_counter()
    print("Time elapsed %d s" % (stop - start))

    return df

def correct_ADC_data_64ch(df, config):
    print("Correcting ADC data...", end='\t')
    replacing_series_set = {}

    # from simulation schematic level
    tau_rise = 16.37e-9 / np.log(9) # 1st order time constant = rising time 10-90% / ln(9)
    tau_fall = 18.71e-9 / np.log(9)


    for board in config['board']:

        tempo_dig_ck_freq = config['config_B%d' % board]['tempo_dig_ck'] * 1e6
        K_rise = 1 - np.exp(-1 / (tau_rise * tempo_dig_ck_freq))
        K_fall = 1 - np.exp(-1 / (tau_fall * tempo_dig_ck_freq))

        # if len(config['board']) == 1:
        #     board_suffix = ''
        #     channel_list = config['enable_TL_ASIC_ch'][0]
        #     gain_list = config['tdc_injected'][0]
        # else:
        board_suffix = '_B%d' % board
        channel_list = config['config_B%d' % board]['enable_TL_ASIC_ch'][0]
        gain_list = config['config_B%d' % board]['tdc_injected'][0]

        for gain in gain_list:
            for channel in set(channel_list) : # order matters !
                current_ch_gain = '_%s_ch%d' % (gain, channel) + board_suffix

                if channel%16==0: # ^ {0, 16, 32, 48}no need to correct ch0 of each cluster
                    replacing_series_set['adc' + current_ch_gain] = df['adc'+current_ch_gain]
                else:
                    previous_ch_gain = '_%s_ch%d' % (gain, channel - 1) + board_suffix
                    adc_increased_wrt_previous_ch = (df['adc'+current_ch_gain] > df['adc'+previous_ch_gain])
                    K = adc_increased_wrt_previous_ch * K_rise + (~adc_increased_wrt_previous_ch)*K_fall
                    replacing_series_set['adc' + current_ch_gain] = df['adc'+current_ch_gain]/K + replacing_series_set['adc' + previous_ch_gain] * (1-1/K)

    df.drop(labels=list(replacing_series_set.keys()), axis="columns", inplace=True)
    df = pd.concat([df, pd.DataFrame(replacing_series_set)], axis=1)

    print('Done')
    return df





def debug_unmatched_CPT():
    root_folder = "../output/"
    search_folder = root_folder + "/Hamamatsu_S13361_6597/Na22_spectra/LYSO_monolithic_hexa/6/raw/"
    file_suffix = ''

    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("(?<=/)[0-9]+", folder) # (?=_*/raw)
    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        exit(0)
        # return

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)
    outfile.close()


    board_list = config['board']

    # config['save_folder'] = root_folder + config['save_folder']
    config['root_folder'] = root_folder
    config['datapath_to_display'] = search_folder[len(root_folder):]

    # distant folder
    # if (':/' in root_folder) | ('//' in root_folder):
    #     config['save_folder'] = root_folder + config['save_folder']

    if len(board_list)>1:
        board_list = [str(board) for board in np.sort(board_list)]
        all_boards_label = 'B'+"-".join(board_list)
        output_folder = folder + '/../'+all_boards_label+'/'+ file_suffix + '/'
    else:
        output_folder = folder + '/../B%d/'%board_list[0]+ file_suffix + '/'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    config['output_folder'] = output_folder
    # config['save_folder'] = search_folder

    # save_filepath = output_folder # + '%s_' % (folder_index_str)
    df0_filepath = output_folder + '0'+file_suffix+'.feather'
    df1_filepath = output_folder + '1'+file_suffix+'.feather'
    stats_filepath = output_folder + "stats"+file_suffix+".csv"
    config['stats_filepath'] = stats_filepath


    # Step 0 : assemble all files
    if os.path.exists(stats_filepath) & os.path.exists(df0_filepath):

        if os.path.exists(df1_filepath):
            pass
        else:
            print("Reading existing dataframe 0 ", end='')
            df = pd.read_feather(df0_filepath)
            print("(%d frames)"%len(df))
    else:
        df = pd.DataFrame()
        cluster_stats_dict = {'raw_event_count': [],
                      'exploitable_event_count': [],
                      'file': [],
                      'cluster': [],
                      'injected_channels': [],
                      'len_after_merging':[]}


        board_length_list = []

        for bi, board in enumerate(board_list):
            files = glob.glob(search_folder + '/B%d'%board+'*' + file_suffix + '.csv')

            df_board = pd.DataFrame()
            # df_MSB_CPT_stats = pd.DataFrame()
            df_not_merged_CPT = pd.DataFrame()

            # with alive_bar(len(files), force_tty=True) as bar:  # your expected total
            # cluster_length_list = []
            cluster_for_this_board = []
            plt.figure(0)

            df = [pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()]

            # combine clusters
            for fi, file in enumerate(files): # go through clusters
                print("For %s:"%os.path.basename(file))

                cluster = re.findall("(?<=cluster_)[0-9]+", file)
                cluster = int(cluster[0]) if cluster else 0
                cluster_for_this_board.append(cluster)

                df_tmp = build_dataframe_from_file(file, config)
                init_len = len(df_tmp)
                df_tmp = remove_status_erroneous_frames(init_len, df_tmp, cluster_stats_dict, fi)
                # df_tmp=df_tmp[df_tmp.index!=12672]

                df_tmp = decode_CPT_data(df_tmp, config, cluster, file_suffix, use_mimic_offset_table=True)

                df[fi] = df_tmp
                # if cluster!=2:

            for fi in [0]:
                for index in df[fi].frames_found[df[fi].frames_found==0].index:
                    plt.axvline(index, ymin=0, ymax=1)

            for fi in range(1,4):
                y = (df[0].CPT - df[fi].CPT).values
                plt.scatter(range(len(y)), y, label="0-%d"%fi)
            # print((dfA.msb_cpt-dfB.msb_cpt).value_counts())

            plt.grid()
            plt.legend()
            plt.show()


if __name__=="__main__":
    debug_unmatched_CPT()
    pass


















