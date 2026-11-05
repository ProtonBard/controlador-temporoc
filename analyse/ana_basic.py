import re, os, glob

import yaml

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
from src.utils import modelFitLinear, asic_col


import scipy.optimize as opt

def conso_TDC_vs_channel(search_string):
    print(search_string)


    csv_files = glob.glob(search_string)

    board = int(re.findall("(?<=_B)[0-9]+", csv_files[0])[0])

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        selection = (df['conditions'] != 'channel_enabled_variation') & (df['conditions'] != 'one_by_one_channel')

        plt.figure(1, figsize=(10, 8))

        condition_selection = df['conditions'] == 'channel_enabled_variation'
        for cluster_RO_enabled in np.unique(df.loc[condition_selection, 'cluster_RO_enabled']):
            for freq in np.unique(df.loc[condition_selection, 'injection_freq']):
                selection = condition_selection & (df['injection_freq'] == freq) & (df.cluster_RO_enabled==cluster_RO_enabled)
                df.sort_values('channels_injected', inplace=True)

                ax_tmp = plt.plot(df.loc[selection, 'channels_injected'], df.loc[selection, 'digital_current'],
                                     linestyle=None, marker='o', label="DIGITAL - hit freq %d Hz - cluster_RO_enabled %d"%(freq, cluster_RO_enabled))

                plt.plot(df.loc[selection, 'channels_injected'], df.loc[selection, 'analog_current'],
                         linestyle='--', color=ax_tmp[0].get_color(), label="ANALOG - hit freq %d Hz - cluster_RO_enabled %d" % (freq, cluster_RO_enabled))


        plt.figure(2, figsize=(10, 8))
        condition_selection = df['conditions'] == 'one_by_one_channel'
        for cluster_RO_enabled in np.unique(df.loc[condition_selection, 'cluster_RO_enabled']):
            for freq in np.unique(df.loc[condition_selection, 'injection_freq']):
                selection = condition_selection & (df['injection_freq'] == freq) & (df.cluster_RO_enabled==cluster_RO_enabled)
                df.sort_values('channels_injected', inplace=True)

                ax_tmp = plt.plot(df.loc[selection, 'channels_injected'], df.loc[selection, 'digital_current'],
                                     linestyle=None, marker='o', label="DIGITAL - hit freq %d Hz - cluster_RO_enabled %d"%(freq, cluster_RO_enabled))
                plt.plot(df.loc[selection, 'channels_injected'], df.loc[selection, 'analog_current'],
                         linestyle='--', color=ax_tmp[0].get_color(), label="ANALOG - hit freq %d Hz - cluster_RO_enabled %d" % (freq, cluster_RO_enabled))



    plt.figure(1, figsize=(10, 8))
    plt.xlabel('Enabled & injected channel COUNT')
    plt.ylabel('Digital power consumption [mA]')
    plt.grid()
    plt.legend()
    plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
    plt.tight_layout()
    plt.savefig(folder + "conso_TDC_vs_channel_count.png")

    plt.figure(2, figsize=(10, 8))
    plt.xlabel('Enabled & injected channel NUMBER')
    plt.ylabel('Digital power consumption [mA]')
    plt.grid()
    plt.legend()
    plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
    plt.tight_layout()
    plt.savefig(folder + "conso_TDC_vs_channel_number.png")

    plt.show()
    pass

def plot_BG_range(search_string):

    search_string += 'BG_dac_range*.csv'
    print(search_string)

    csv_files = glob.glob(search_string)
    # csv_files = [search_string]

    folder = os.path.dirname(search_string) + '/../'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        plt.figure(0, figsize=(10, 8))
        df = df.sort_values(by=['BG_dac'])

        for bias_1V_dac in np.unique(df.bias_1V_dac):
            selection = (df.bias_1V_dac == bias_1V_dac) & (df['BG_mV']>-1e40)
            plt.plot(df.loc[selection, 'BG_dac'], df.loc[selection, 'BG_mV'], marker='+', label="bias_1V_dac %d"%bias_1V_dac)

        plt.xlabel('BG [dac]')
        plt.ylabel('Vbg [mV]')
        plt.grid()
        plt.title("BG_mV vs BG_dac vs bias_1V_dac")
        plt.legend()
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')
        plt.savefig(folder + "BG_sweep.png")

        plt.figure(1, figsize=(10, 8))
        df = df.sort_values(by=['bias_1V_dac'])
        for BG_dac in np.unique(df.BG_dac):
            selection = (df.BG_dac == BG_dac) & (df['bias_1V_mV']>-1e40)
            fitParam, cov = opt.curve_fit(modelFitLinear, df.loc[selection, 'bias_1V_dac'], df.loc[selection, 'bias_1V_mV'])
            voltage_offset = fitParam[1]
            voltage_per_dac = fitParam[0]
            plt.plot(df.loc[selection, 'bias_1V_dac'], df.loc[selection, 'bias_1V_mV'], marker='+', label="BG_dac %d : %.2f mV/dac  offset: %.2f mV"%(BG_dac, voltage_per_dac, voltage_offset))

        plt.xlabel('bias_1V [dac]')
        plt.ylabel('Vbias_1V [mV]')
        plt.title("bias_1V_mV vs bias_1V_dac vs BG_dac")
        plt.grid()
        plt.legend()
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')
        plt.tight_layout()
        plt.savefig(folder + "bias_1V_sweep.png")


        plt.figure(2, figsize=(10, 8))
        df['bias_1V_R1_ohm'] = 54e3
        for i in range(4):
            df['bias_1V_R1_ohm'] += np.right_shift(df['bias_1V_dac'] & (1 << i), i) * 2 ** i * 1e3
        R2 = 100e3
        df['bias_1V_expected_mV'] = (R2 + df['bias_1V_R1_ohm']) / R2 * df['BG_mV']
        df = df.sort_values(by=['bias_1V_expected_mV'])

        for BG_dac in np.unique(df.BG_dac):
            selection = (df.BG_dac == BG_dac) & (df['bias_1V_mV']>-1e40)
            plt.plot(df.loc[selection, 'bias_1V_expected_mV'], df.loc[selection, 'bias_1V_mV'], marker='+', label="BG_dac %d"%BG_dac)
        plt.ylabel('Vbias_1V measured [mV]')
        plt.xlabel('Vbias_1V expected [mV]')
        plt.title("Vbias 1V linearity")
        plt.grid()
        plt.legend()
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
        plt.tight_layout()
        plt.savefig(folder + "bias_1V_sweep_vs_expected.png")


        plt.figure(3, figsize=(10, 8))
        df = df.sort_values(by=['BG_dac'])
        for bias_1V_dac in np.unique(df.bias_1V_dac):
            selection = (df.bias_1V_dac == bias_1V_dac) & (df['BG_mV']>-1e40)
            plt.plot(df.loc[selection, 'BG_dac'], df.loc[selection, 'temp_mV'], marker='+', label="bias_1V_dac %d"%bias_1V_dac)

        plt.xlabel('bias_1V [dac]')
        plt.ylabel('temperature [mV]')
        plt.title("Temperature voltage vs BG_dac vs bias_1V_dac")

        plt.grid()
        plt.legend()
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')
        plt.tight_layout()
        plt.savefig(folder + "temp_sweep.png")

        plt.show()
        pass


def plot_Vth_range(search_string):

    search_string += '_vth_dac_range.csv'
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)


        plt.figure(0, figsize=(10, 8))
        df = df.sort_values(by=['dac'])

        for label in ['Vth1_mV', 'Vth2_mV', 'VthQ_mV']:
            fitParam, cov = opt.curve_fit(modelFitLinear, df.loc[:, 'dac'], df.loc[:, label])
            voltage_offset = fitParam[1]
            voltage_per_dac = fitParam[0]

            plt.plot(df.loc[:, 'dac'], df.loc[:, label], marker='+', label=label + " %.2f mV/dac  offset: %.2f mV"%(voltage_per_dac, voltage_offset))


        plt.xlabel('dac')
        plt.ylabel('label')
        plt.grid()
        plt.legend()
        plt.title("Vth DAC range sweep")
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')

        plt.savefig(folder + "Vth_sweep.png")
        plt.show()
        pass

def plot_input_dac_range(search_string):

    search_string += '_input_dac_range_per_channel.csv'
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)


        plt.figure(0, figsize=(10, 8))
        df = df.sort_values(by=['ch_input_dac'])
        for ch in np.unique(df.channel):
            selection = df.channel==ch
            plt.plot(df.loc[selection, 'ch_input_dac'], df.loc[selection, 'ch_input_mV'], marker='+', label='ch %d'%ch)

        plt.xlabel('ch_input_dac')
        plt.ylabel('ch_input_mV')
        plt.grid()
        plt.legend(ncols=4)
        plt.title("Input dac sweep")
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')
        plt.tight_layout()

        plt.savefig(folder + "input_dac_sweep.png")
        plt.close()

        plt.figure(1, figsize=(10, 8))
        selection = df.ch_input_dac == 128 # default HW value
        df = df.sort_values(by=['channel'])
        asic_col(df.loc[selection, 'ch_input_mV'])
        # asic_map(df.loc[selection, 'ch_input_mV'])
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(0.4, 0.01),
                    xycoords='axes fraction')
        plt.title("Input dac voltage pixel map [mV] for HW default input dac value (128)")
        plt.savefig(folder + "input_dac_channel_map_for_code_128.png")
        plt.show()
        pass

def plot_channel_dc_level(search_string):
    search_string += '_channel_DC_levels.csv'
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        plt.figure(0, figsize=(10, 8))
        df = df.sort_values(by=['channel'])
        linestyles = ['solid', 'dashed']
        for analog_probe in ['shH', 'shL', 'paLG', 'paHG']:

            for i, label in enumerate(['_mV_prior_PCB_buffer']): #['_mV', '_mV_prior_PCB_buffer']): #
                label = analog_probe + label
                selection = df[label]<1e40
                if i==0:
                    ax = plt.plot(df.loc[selection, 'channel'], df.loc[selection, label], marker='+', label=label,
                                  linestyle=linestyles[i])
                else:
                    plt.plot(df.loc[selection, 'channel'], df.loc[selection, label], marker='+', label=label, linestyle=linestyles[i], color = ax[0].get_color())

        plt.xlabel('channel')
        plt.ylabel('DC level [mV]')
        plt.grid()
        plt.legend()
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')
        plt.tight_layout()
        plt.savefig(folder + "channel_dc_level.png")
        plt.show()

        # plt.figure(1, figsize=(10, 8))
        # selection = df.ch_input_dac == 128 # default HW value
        # df = df.sort_values(by=['channel'])
        # asic_col(df.loc[selection, 'ch_input_mV'])
        # # asic_map(df.loc[selection, 'ch_input_mV'])
        # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(0.4, 0.01),
        #             xycoords='axes fraction')
        # plt.title("Input dac voltage pixel map [mV] for HW default input dac value (128)")
        # plt.savefig(folder + "input_dac_channel_map_for_code_128.png")
        # plt.show()
        # pass

def plot_oscillo_delaybox_step(search_string):
    csv_files = glob.glob(search_string)
    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)


    for csv_file in csv_files:
        print(search_string)
        df = pd.read_csv(csv_file)
        df['oscilloDelay_mean'] = df['oscilloDelay_mean'] - df.oscilloDelay_mean.min()

        try:
            fitParam, cov = opt.curve_fit(modelFitLinear, df.delay_code, df.oscilloDelay_mean)
        except:
            fitParam = [0, 0]
        slope = fitParam[0]
        # delayOffset = fitParam[1]
        lsb = slope

        plt.subplots(1, 3, figsize=(12, 8))

        plt.subplot(1, 3, 1)
        plt.scatter(df['delay'], df['oscilloDelay_mean']/1e3, label='LSB %.2f ps per delay code' %lsb)
        plt.xlabel('Delay code [lsb]')
        plt.ylabel('Delay [ns]')
        plt.title('Linearity')
        plt.legend()
        plt.grid()
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')


        plt.subplot(1, 3, 2)
        plt.scatter(df['delay'], df['oscilloDelay_sdev'], label='Average jitter %.2f ps'%df['oscilloDelay_sdev'].mean())
        plt.xlabel('Delay code [lsb]')
        plt.ylabel('Jitter [ps]')
        plt.grid()
        plt.legend()
        plt.title('Jitter')
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
                     xycoords='axes pixels')


        plt.subplot(1, 3, 3)
        yfit = modelFitLinear(df.delay_code, *fitParam)
        inl = (yfit - df.oscilloDelay_mean) / lsb
        plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')

        plt.plot(df.delay_code, inl, '--', linewidth=1, color='red', label='INL RMS={:.2f} lsb/{:.0f} ps \nMIN/MAX {:.2f}/{:.2f} lsb = {:.0f}/{:.0f} ps '
             .format(np.std(inl), np.std(inl) * lsb, np.nanmin(inl), np.nanmax(inl), np.nanmin(inl) * lsb,
                     np.nanmax(inl) * lsb))

        plt.grid()
        plt.legend()
        plt.title("INL")
        plt.ylabel("INL [lsb]")
        plt.suptitle("External delay box")
        mng = plt.get_current_fig_manager()
        mng.full_screen_toggle()
        plt.tight_layout()

        plt.savefig(folder + "/delaybox_linearity.png")
        plt.show()

def plot_scan_frame_count_versus_nb_trigger_vs_injected_channels(search_string):
    csv_files = glob.glob(search_string)
    folder_index_str = re.findall("(?<=raw/)[0-9]+", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/../../' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    config_file = os.path.dirname(csv_files[0]) + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    for csv_file in csv_files:
        print(search_string)
        df = pd.read_csv(csv_file)


        for ROmode in np.unique(df.readout_mode):


            nb_bits_per_frame = 1043  # full_adc_tdc
            df['frame_count'] = (df.ck_edge_count_mean / df.repeat / nb_bits_per_frame) #.astype(int)

            print(df.groupby(by="nb_trigger").frame_count.value_counts())

            # nb of distinct frame count per nb_trigger config if at least one channel injected
            print(df[df.nb_channels_enabled_injected > 0].groupby(by='nb_trigger').frame_count.nunique())

            # nb trigger setting producing at least 1 frame per injection no matter the number of channels injected within the cluster
            print(df[df.nb_channels_enabled_injected > 0].groupby(by='nb_trigger').filter(lambda x: (x.frame_count>0).all(axis=0)).nb_trigger)

            df[df.nb_channels_enabled_injected > 0].groupby(by='nb_trigger').filter(
                lambda x: (x.frame_count < 3).all(axis=0) & (x.frame_count.count() > 14)).nb_trigger.unique()
            # df.loc[df.nb_trigger == 28, :]
            print(df.loc[df.nb_trigger == 26, ['nb_channels_enabled_injected', 'frame_count']])


            # map
            plt.figure(0, figsize=(10, 6))
            ax = plt.gca()
            data = df['frame_count']
            # # Re-shaping of the array
            # m = np.array([data[i * nbOfLines:(i + 1) * nbOfLines] for i in range(0, nbOfLines)], dtype=float)
            # m = np.swapaxes(m, 0, 1)
            # m = m[::-1, ]
            m = pd.pivot(df, values='frame_count', index='nb_trigger', columns='nb_channels_enabled_injected').T

            # m[m==0]= np.nan

            vmin = 0 #data.min()
            vmax = 4 #data.max() to allow comparison

            # # discrete cmap
            # cmap = plt.get_cmap('Pastel1')
            # cmaplist = np.unique(m).tolist()
            # cmaplist = [cmap(i) for i in range(len(cmaplist)+1)]
            # cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
            #     'Custom cmap', cmaplist, len(cmaplist))

            # continuous cmap
            cmap = 'rainbow'
            cmap = 'viridis'

            # Plot
            im = plt.imshow(m, alpha=0.8, cmap=cmap)
            im.set_clim(vmin, vmax)

            # Color bar
            cbar = plt.colorbar(im)

            # if clabel:
            #     cbar.set_label(clabel)
            ax.set_aspect('auto')

            for (j, i), label in np.ndenumerate(m):
                r = 1
                if i==24: # nb_trigger
                    plt.text(i, j, str(round(label, r)), ha='center', va='center')

            plt.ylabel('nb_channels_enabled_injected')
            plt.xlabel('nb_trigger')
            plt.title(ROmode + ' - average number of frames per injection (force saturation above %.1f)'%vmax)
            # plt.legend()
            # plt.grid()
            # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
            #              xycoords='axes pixels')

            # mng = plt.get_current_fig_manager()
            # mng.full_screen_toggle()
            plt.suptitle(config['test'][0])
            plt.annotate(search_string, xy=(5, 7), xycoords='axes pixels')

            plt.tight_layout()

            plt.savefig(folder + "/frame_count_map.png")
            # plt.show()
            # plt.close()


            plt.figure(1, figsize=(8, 5))

            for nb_trigger in [1, 24, 31]: #[30, 31]:#np.unique(df.nb_trigger):#

                selection = (df.readout_mode == ROmode) & (df.nb_trigger == nb_trigger)
                # plt.errorbar(df.loc[selection, 'nb_channels_enabled_injected'], df.loc[selection, 'ck_edge_count_mean'],
                #              yerr= df.loc[selection, 'ck_edge_count_sdev'], label='nb_trigger %d'%nb_trigger)

                plt.plot(df.loc[selection, 'nb_channels_enabled_injected'], df.loc[selection, 'frame_count'],
                            label='nb_trigger %d'%nb_trigger)

            plt.xlabel('nb_channels_enabled_injected')
            plt.ylabel('average number of frames per injection')
            plt.title(ROmode + ' - average number of frames per injection - '+config['test'][0])
            plt.legend()
            plt.grid()
            plt.annotate(search_string, xy=(5, 7), xycoords='axes pixels')
            # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
            #              xycoords='axes pixels')



            # mng = plt.get_current_fig_manager()
            # mng.full_screen_toggle()
            plt.tight_layout()

            plt.savefig(folder + "/frame_count.png")
            plt.show()
            plt.close()

def plot_BG_vs_temp_vs_range(root_folder, folder_index_list):
    output_folder = root_folder+'0_synthesis/'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # df_all = pd.DataFrame()

    # add extra points
    df_all = pd.read_csv(output_folder+"manual_points.csv", delimiter=';')

    for folder_index in folder_index_list:
        search_string = root_folder+'/%d/raw/'%folder_index + 'BG_dac_range*.csv'

        csv_files = glob.glob(search_string)

        for csv_file in csv_files:
            print(csv_file)
            df = pd.read_csv(csv_file)
            temperature = re.findall("(?<=_T_)[-]?[0-9]+[.]?[0-9]+", csv_file)
            if len(temperature)>0:
                temperature = float(temperature[0])
            else:
                print("temperature not found in csv_file, assumed 0"+csv_file)
                temperature = 0
            df['temperature'] = temperature
            df['human_time'] = re.findall("(?<=range_)[0-9_]+(?=_)", csv_file)[0]
            df['time'] = os.path.getmtime(csv_file)

            df_all = pd.concat([df_all, df])

            # plt.figure(0, figsize=(10, 8))
            # df = df.sort_values(by=['BG_dac'])
            #
            # for bias_1V_dac in np.unique(df.bias_1V_dac):
            #     selection = (df.bias_1V_dac == bias_1V_dac) & (df['BG_mV']>-1e40)
            #     plt.plot(df.loc[selection, 'BG_dac'], df.loc[selection, 'BG_mV'], marker='+', label="bias_1V_dac %d"%bias_1V_dac)
            #
            #
            # # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
            # #              xycoords='axes pixels')
            #
            # plt.figure(1, figsize=(10, 8))
            # df = df.sort_values(by=['bias_1V_dac'])
            # for BG_dac in np.unique(df.BG_dac):
            #     selection = (df.BG_dac == BG_dac) & (df['bias_1V_mV']>-1e40)
            #     fitParam, cov = opt.curve_fit(modelFitLinear, df.loc[selection, 'bias_1V_dac'], df.loc[selection, 'bias_1V_mV'])
            #     voltage_offset = fitParam[1]
            #     voltage_per_dac = fitParam[0]
            #     plt.plot(df.loc[selection, 'bias_1V_dac'], df.loc[selection, 'bias_1V_mV'], marker='+', label="BG_dac %d : %.2f mV/dac  offset: %.2f mV"%(BG_dac, voltage_per_dac, voltage_offset))
            #
            #
            # plt.figure(2, figsize=(10, 8))
            # df['bias_1V_R1_ohm'] = 54e3
            # for i in range(4):
            #     df['bias_1V_R1_ohm'] += np.right_shift(df['bias_1V_dac'] & (1 << i), i) * 2 ** i * 1e3
            # R2 = 100e3
            # df['bias_1V_expected_mV'] = (R2 + df['bias_1V_R1_ohm']) / R2 * df['BG_mV']
            # df = df.sort_values(by=['bias_1V_expected_mV'])
            #
            # for BG_dac in np.unique(df.BG_dac):
            #     selection = (df.BG_dac == BG_dac) & (df['bias_1V_mV']>-1e40)
            #     plt.plot(df.loc[selection, 'bias_1V_expected_mV'], df.loc[selection, 'bias_1V_mV'], marker='+', label="BG_dac %d"%BG_dac)
            #
            # # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
            #
            #
            # plt.figure(3, figsize=(10, 8))
            # df = df.sort_values(by=['BG_dac'])
            # for bias_1V_dac in np.unique(df.bias_1V_dac):
            #     selection = (df.bias_1V_dac == bias_1V_dac) & (df['BG_mV']>-1e40)
            #     plt.plot(df.loc[selection, 'BG_dac'], df.loc[selection, 'temp_mV'], marker='+', label="bias_1V_dac %d"%bias_1V_dac)
            #
            # # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
            # #              xycoords='axes pixels')


    # plt.figure(0, figsize=(10, 8))
    # plt.xlabel('BG [dac]')
    # plt.ylabel('Vbg [mV]')
    # plt.grid()
    # plt.title("BG_mV vs BG_dac vs bias_1V_dac")
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig(output_folder + "BG_sweep.png")
    #
    # plt.figure(1, figsize=(10, 8))
    # plt.xlabel('bias_1V [dac]')
    # plt.ylabel('Vbias_1V [mV]')
    # plt.title("bias_1V_mV vs bias_1V_dac vs BG_dac")
    # plt.grid()
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig(output_folder + "bias_1V_sweep.png")
    #
    # plt.figure(2, figsize=(10, 8))
    # plt.ylabel('Vbias_1V measured [mV]')
    # plt.xlabel('Vbias_1V expected [mV]')
    # plt.title("Vbias 1V linearity")
    # plt.grid()
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig(output_folder + "bias_1V_sweep_vs_expected.png")
    #
    # plt.figure(3, figsize=(10, 8))
    # plt.xlabel('bias_1V [dac]')
    # plt.ylabel('temperature [mV]')
    # plt.title("Temperature voltage vs BG_dac vs bias_1V_dac")
    # plt.grid()
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig(output_folder + "temp_sweep.png")

    plt.figure(4, figsize=(10, 8))
    selection = (df_all.bias_1V_dac == 2) & (df_all.BG_dac == 0)
    plt.scatter(df_all.loc[selection, 'temperature'], df_all.loc[selection, 'BG_mV'],
                label='manual Vbias1V_dac %d'%2)
    selection = (df_all.bias_1V_dac == 0) & (df_all.BG_dac == 0)
    plt.scatter(df_all.loc[selection, 'temperature'], df_all.loc[selection, 'BG_mV'],
                label='auto sweep Vbias1V_dac %d'%0)
    plt.xlabel('Temperature [°C]')
    plt.ylabel('Vbg [mV]')
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "Vbg_vs_temp_for_dac0.png")

    plt.figure(5, figsize=(10, 8))
    for BG_dac in np.unique(df_all.BG_dac):
        selection = (df_all.bias_1V_dac == 0) & (df_all.BG_dac == BG_dac)
        plt.plot(df_all.loc[selection, 'temperature'], df_all.loc[selection, 'BG_mV'], label='BG_dac %d'%BG_dac)

    plt.xlabel('Temperature [°C]')
    plt.ylabel('Vbg [mV]')
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_folder + "Vbg_vs_temp_vs_dac.png")

    plt.show()
    pass

if __name__ == "__main__":
    # conso_TDC_vs_channel("output/DC/0_B1*.csv")
    # conso_TDC_vs_channel("output/DC/1_B2*.csv")
    # plot_BG_range("output/DC/5_B2*")
    # plot_BG_range("../output/basic/DC/2/raw/")
    # plot_BG_range("../output/combined_BG_TDC_tests/13/raw/")
    plot_BG_vs_temp_vs_range("../output/temperature/", [4,5,6,9,13,15,17,19])
    # plot_Vth_range("output/DC/4_B2*")
    # plot_input_dac_range("output/DC/6_B2*")
    # plot_channel_dc_level("output/DC/7_B2*")
    # plot_oscillo_delaybox_step("output/tdc_scan/delaybox_step_oscillo_delay/1*.csv")

    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_320_MHz/raw/0/frame_count.csv")
    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_320_MHz/raw/1/frame_count.csv")
    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_160_MHz/raw/0/frame_count.csv")
    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_160_MHz/raw/1/frame_count.csv")
    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_40_MHz/raw/0/frame_count.csv")
    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_160_MHz/raw/2/frame_count.csv")
    # plot_scan_frame_count_versus_nb_trigger_vs_injected_channels("output/basic/frame_count/dig_ck_160_MHz/raw/3/frame_count.csv")
    pass
