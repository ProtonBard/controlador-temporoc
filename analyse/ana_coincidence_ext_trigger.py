from statistics import median

import matplotlib.pyplot as plt
import numpy as np

from analyse.ana_internal_TDC import analyse_code_density_internal_tdc
from analyse.common_analysis import generate_report
from analyse.common_analysis_TDC import *
from analyse.common_data_decoding import *
matplotlib.use('Qt5Agg')

font = {'size': 10}
matplotlib.rc('font', **font)

def analyse_coincidence_ext_trigger(root_folder, search_folder):

    config = read_config(root_folder, search_folder)
    df = analyse_init(search_folder, config)

    if len(df) == 0:
        print("No data")
        exit(0)

    df2_filepath = config['output_folder'] + "2.feather"
    CTR_filepath = config['output_folder'] + 'CTR.csv'

    # Step 2 : compute time difference between coincident channels
    if os.path.exists(df2_filepath):
        df = pd.read_feather(df2_filepath)
    else:

        if os.path.exists(CTR_filepath):
            print("Skipping CTR analysis: result csv file already there !")
            return
        else:
            print("CTR analysis...")


        # plot_lsb_vs_time_for_all_ch(df, config, plot=True)

        # WITH ONLY LSB COUNTER

        # In between boards
        # boardA = config['board'][0]
        # boardB = config['board'][1]
        # for channelA in config['config_B%d' % boardA]['enable_TL_ASIC_ch'][0]:
        #     for channelB in config['config_B%d' % boardB]['enable_TL_ASIC_ch'][0]:
        #
        #         ch_suffixA = '_%s_ch%d_B%d' % (gain, channelA, boardA)
        #         ch_suffixB = '_%s_ch%d_B%d' % (gain, channelB, boardB)
        #         non_null_selection = (df['tdc_data_valid' + ch_suffixA] != 0) & (
        #                     df['tdc_data_valid' + ch_suffixB] != 0)
        #
        #         plt.figure()
        #         plt.title('LSB CPT diff ')
        #         plt.annotate("B%d\nCh %d\n%s" % (boardA, channelA, gain), xy=(0.4, 0.65), xycoords='axes fraction')
        #         plt.annotate("B%d\n   %d\n%s" % (boardB, channelB, gain), xy=(0.65, 0.65), xycoords='axes fraction',
        #                      horizontalalignment='right')
        #
        #         step = 1
        #         dt = df.loc[non_null_selection, 'cpt' + ch_suffixA] - df.loc[non_null_selection, 'cpt' + ch_suffixB]
        #         bins = np.arange(dt.min(), dt.max() + 1, step)  # lsb
        #         counts, bins = np.histogram(dt, bins=bins)
        #         # plt.stairs(counts, bins, fill=True, label='dt' + ch_suffixA + ch_suffixB)
        #         plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True)
        #         plt.grid()
        #         plt.xlabel('dt' + ch_suffixA + ch_suffixB)
        #         plt.yscale('log')
        #         plt.tight_layout()
        #         plt.savefig(output_folder + "lsb_cpt_CTR" + ch_suffixA + ch_suffixB + '.png')
        #         plt.show()
        #         plt.close()

        # for board in config['board']:
        #     if len(config['config_B%d' % board]['enable_TL_ASIC_ch'][0]) > 1:
        #
        #         channelA = config['config_B%d' % board]['enable_TL_ASIC_ch'][0][0]
        #         channelB = config['config_B%d' % board]['enable_TL_ASIC_ch'][0][1]
        #
        #         ch_suffixA = '_%s_ch%d_B%d' % (gain, channelA, board)
        #         ch_suffixB = '_%s_ch%d_B%d' % (gain, channelB, board)
        #
        #         non_null_selection = (df['tdc_data_valid' + ch_suffixA] != 0) & (
        #                 df['tdc_data_valid' + ch_suffixB] != 0)
        #
        #         plt.figure()
        #         # step = 1
        #         dt = (df.loc[non_null_selection, 'cpt' + ch_suffixA] - df.loc[non_null_selection, 'cpt' + ch_suffixB])
        #         print(ch_suffixA+ch_suffixB)
        #         print(dt.value_counts())
        #
        #         # plt.scatter(df.loc[non_null_selection & (dt != 0), 'cpt' + ch_suffixA], df.loc[non_null_selection & (dt != 0), 'cpt' + ch_suffixB], s=2)
        #         # plt.scatter(dt.index, dt.values, s=2)
        #         # plt.plot((df['CPT']+df['cpt' + ch_suffixA])*12.5, df['cpt' + ch_suffixA], marker='.')
        #         plt.plot(((df['CPT']+df['cpt' + ch_suffixA])*12.5).diff(), marker='.')
        #         plt.grid()
        #         plt.xlabel(ch_suffixA)
        #         plt.ylabel(ch_suffixB)
        #
        #         # plt.title('LSB CPT diff ')
        #         # plt.annotate("B%d\nCh %d\n%s" % (board, channelA, gain), xy=(0.4, 0.65), xycoords='axes fraction')
        #         # plt.annotate("B%d\n   %d\n%s" % (board, channelB, gain), xy=(0.65, 0.65), xycoords='axes fraction',
        #         #              horizontalalignment='right')
        #
        #         # bins = np.arange(dt.min(), dt.max() + 1, step)  # lsb
        #         # counts, bins = np.histogram(dt, bins=bins)
        #         # plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True)
        #         # plt.grid()
        #         # plt.xlabel('dt' + ch_suffixA + ch_suffixB)
        #         # plt.yscale('log')
        #         # plt.tight_layout()
        #         # plt.savefig(output_folder + "lsb_cpt_CTR" + ch_suffixA + ch_suffixB + '.png')
        #
        #         plt.show()
        #         plt.close()

        # WITH TDC
        res = {'boardA':[], 'channelA':[], 'gainA':[], 'boardB':[], 'channelB':[], 'gainB':[],
               'time_conversion_method':[], 'CTR_FWHM_ps_std':[], 'CTR_FWHM_ps_Gaussian':[]}

        gain = 'low'

        for time_conversion_method in ['DNL_TOA_calibrated_time']: #['lsb_fromCAL_moving_avg']: #['lsb_fromCAL']: #'DNL_TOA_fraction']:   # , 'lsb_fromCAL_moving_avg','DNL_TOA_fraction'
            # 'DNL_TOA_calibrated_time'
            # df = compute_ps_time_within_one_msb_cpt_for_all_channels(df, config, time_conversion_method=time_conversion_method)


            # In between boards
            boardA = config['board'][0]
            boardB = config['board'][1]
            channelA_list = config['config_B%d'%boardA]['enable_TL_ASIC_ch'][0]
            channelB_list = config['config_B%d'%boardB]['enable_TL_ASIC_ch'][0]
            for channelA, channelB in zip(channelA_list, channelB_list):
            # for channelA, channelB in zip([6], [6]):
            # for channelA, channelB in zip([12], [12]):

                    ch_gain_suffixA = '_%s_ch%d_B%d' % (gain, channelA, boardA)
                    ch_gain_suffixB = '_%s_ch%d_B%d' % (gain, channelB, boardB)
                    df = compute_ps_time_within_one_msb_cpt(df, config, channelA, gain, boardA, time_conversion_method)
                    df = compute_ps_time_within_one_msb_cpt(df, config, channelB, gain, boardB, time_conversion_method)

                    df['dt'+ch_gain_suffixA+ch_gain_suffixB] = df['toa_ps' + ch_gain_suffixA] - df['toa_ps' + ch_gain_suffixB]
                    CTR_FWHM_ps_std, CTR_FWHM_ps_Gaussian = plot_CTR(df, config, channelA, boardA,
                                                                     channelB, boardB, time_conversion_method,
                                                                     gainA=gain, gainB=gain)

                    res['boardA'].append(boardA)
                    res['channelA'].append(channelA)
                    res['gainA'].append(gain)
                    res['boardB'].append(boardB)
                    res['channelB'].append(channelB)
                    res['gainB'].append(gain)
                    res['time_conversion_method'].append(time_conversion_method)
                    res['CTR_FWHM_ps_std'].append(CTR_FWHM_ps_std)
                    res['CTR_FWHM_ps_Gaussian'].append(CTR_FWHM_ps_Gaussian)


            # Within the same board
            if len(config['config_B%d'%boardA]['enable_TL_ASIC_ch'][0]) > 1:
                for board in config['board']:
                    channelA = config['config_B%d'%boardA]['enable_TL_ASIC_ch'][0][0]
                    channelB = config['config_B%d'%boardB]['enable_TL_ASIC_ch'][0][1]

                    ch_gain_suffixA = '_%s_ch%d_B%d' % (gain, channelA, board)
                    ch_gain_suffixB = '_%s_ch%d_B%d' % (gain, channelB, board)
                    df['dt'+ch_gain_suffixA+ch_gain_suffixB] = df['toa_ns' + ch_gain_suffixA] - df['toa_ns' + ch_gain_suffixB]
                    CTR_FWHM_ps_std, CTR_FWHM_ps_Gaussian = plot_CTR(df, config, channelA, board,  channelB, board, time_conversion_method)

                    res['boardA'].append(board)
                    res['channelA'].append(channelA)
                    res['gainA'].append(gain)
                    res['boardB'].append(board)
                    res['channelB'].append(channelB)
                    res['gainB'].append(gain)
                    res['time_conversion_method'].append(time_conversion_method)
                    res['CTR_FWHM_ps_std'].append(CTR_FWHM_ps_std)
                    res['CTR_FWHM_ps_Gaussian'].append(CTR_FWHM_ps_Gaussian)

        CTR_df = pd.DataFrame(res)
        print(CTR_df[['boardA', 'channelA', 'boardB', 'channelB','CTR_FWHM_ps_Gaussian']])
        if os.path.exists(CTR_filepath):
            CTR_df = pd.read_csv(CTR_filepath).merge(CTR_df, how='outer', on=['boardA', 'channelA', 'gainA', 'boardB', 'channelB', 'gainB', 'time_conversion_method'])
        CTR_df.to_csv(CTR_filepath, index=False)
        pass

        generate_report(config)



def compute_DNL_for_each_board(root_folder, search_folder):

    config_file = os.path.dirname(search_folder) + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)
    outfile.close()

    board_list = config['board']
    for board in board_list:
        print("\nB%d in "%board+search_folder)
        config = read_config(root_folder, search_folder)
        df = analyse_init(search_folder, config, board_list=[board])

        config['output_folder'] += '/code_density_tdc/'
        analyse_code_density_internal_tdc(df, config)


if __name__ == '__main__':
    # root_folder = "//PCWEEROC22/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    # root_folder = "//192.168.2.230/Users/Weeroc_User/temporoc/temporoc_sw/output/"
    root_folder = "../output/"
    search_folder = root_folder + "coincidence/ext_trigger_digital/B6-4/8/raw/"
    search_folder = root_folder + "dual_asic/1CTR_low_trig_ext_async/raw/"
    # search_folder = root_folder + "dual_asic/2data_cluster_ext_trigger_all_sync_use_indelay/raw/"
    # search_folder = root_folder + "dual_asic/3data_cluster_ext_trigger_all_async_use_indelay/raw/"
    search_folder = root_folder + "dual_asic/4CTR_DVDD1.37_dis_edge/raw/"

    compute_DNL_for_each_board(root_folder, search_folder)
    analyse_coincidence_ext_trigger(root_folder, search_folder)