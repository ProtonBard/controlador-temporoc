import random
import re, os, glob

import numpy as np
import pandas as pd
import yaml
from matplotlib import pyplot as plt
import matplotlib
from common_analysis_TDC import *
from common_analyse_ADC import *

def analyse_charge_scan(search_folder, suffix):

    files = glob.glob(search_folder + '/*cluster_0_%s_*.csv'%suffix)
    suffix_list = []
    for file in files:
        suffix_value = re.findall("(?<=%s_)[0-9]+[.]?[0-9]?+"%suffix, file)
        suffix_value = float(suffix_value[0])
        suffix_list.append(suffix_value)

    res = {suffix: suffix_list}
    res.update({'%s_ch%d_%s'%(gain, ch, meas): [] for gain in ['low', 'high'] for ch in range(64) for meas in ['std', 'mean']})

    df_all = pd.DataFrame()


    for suffix_value in suffix_list:
        file_suffix = suffix+'_%d' % suffix_value
        config = read_config('.', search_folder, file_suffix=file_suffix)
        df = analyse_init(search_folder, config, file_suffix=file_suffix)

        board = config['board'][0]
        board_config = config['config_B%d' % board]

        for gain in ['low', 'high']:
            for ch in range(64):
                injected_adc_serie = df['adc_%s_ch%d_B%d'%(gain, ch, board)]
                res['%s_ch%d_mean'%(gain, ch)].append(injected_adc_serie.mean())
                res['%s_ch%d_std'%(gain, ch)].append(injected_adc_serie.std())

        df[suffix] = suffix_value
        df_all=pd.concat([df, df_all])

    df_all.to_csv(config['save_folder']+'../df_all.csv')

    df = pd.DataFrame(res)
    df.to_csv(config['save_folder']+'../linearity.csv')


    plt.figure(0)
    markers = ['x', '.']
    injected_channel = board_config['injected_channel'][0][0]

    for ch in [injected_channel]: #(64):
        for i, gain in enumerate(['low', 'high']):
            plt.scatter(df_all[suffix], df_all['adc_%s_ch%d_B%d'%(gain, ch, board)], marker=markers[i])

    plt.ylabel('Energy [adc]')
    plt.xlabel(suffix)
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['save_folder']+'../all_points_vs_%s.png'%suffix)
    plt.close()
    # plt.show()


def plot_RMS_evolution_with_suffix_variable(search_folder, suffix):

    df = pd.read_csv(search_folder+'../linearity.csv')
    df = df.sort_values(by=suffix)

    config_file = search_folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)
    outfile.close()

    board = config['board'][0]
    board_config = config['config_B%d' % board]
    injected_channel = board_config['injected_channel'][0][0]
    Cinj = board_config['cinj_pF']

    plt.figure()
    ls = ['dashed', 'solid']
    for ch in [injected_channel]: #range(64):
        for i, gain in enumerate(['low', 'high']):
            plt.plot(df[suffix], df['%s_ch%d_std'%(gain, ch)], ls=ls[i])
    plt.ylabel('RMS energy [adc]')
    plt.xlabel(suffix)
    plt.title('Linearity with pulser through a Cinj %d pF in ch%d'%(Cinj, injected_channel))
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['save_folder']+'../RMS_energy_vs_%s.png'%suffix)
    plt.show()
    # plt.close()


def plot_evolution_with_injected_charge(search_folder):

    df = pd.read_csv(search_folder+'../linearity.csv')
    df = df.sort_values(by='Qinj_pC')

    config_file = search_folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)
    outfile.close()

    board = config['board'][0]
    board_config = config['config_B%d' % board]
    injected_channel = board_config['injected_channel'][0][0]
    Cinj = board_config['cinj_pF']

    plt.figure()
    ls = ['dashed', 'solid']
    for ch in range(64):
        for i, gain in enumerate(['low', 'high']):
            plt.errorbar(df['Qinj_pC'], df['%s_ch%d_mean'%(gain, ch)], yerr=df['%s_ch%d_std'%(gain, ch)], ls=ls[i])
    plt.ylabel('Energy [adc]')
    plt.xlabel('Injected charge [pC]')
    plt.title('Linearity with pulser through a Cinj %d pF in ch%d'%(Cinj, injected_channel))
    plt.grid()
    plt.tight_layout()
    plt.savefig(config['save_folder']+'../energy_errorbar_vs_Qinj.png')
    plt.close()


    plt.figure()
    ls = ['dashed', 'solid']
    for ch in [injected_channel]: #range(64):
        for i, gain in enumerate(['low', 'high']):
            plt.plot(df['Qinj_pC'], df['%s_ch%d_std' % (gain, ch)], ls=ls[i], label=gain)
    plt.ylabel('RMS energy [adc]')
    plt.xlabel('Injected charge [pC]')
    plt.title('External pulser injection through a Cinj %d pF in ch%d' % (Cinj, injected_channel))
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['save_folder']+'../RMS_energy_vs_Qinj.png')
    plt.close()

    plt.figure()
    ls = ['dashed', 'solid']
    for ch in [injected_channel]: #range(64):
        for i, gain in enumerate(['low', 'high']):
            SNR = df['%s_ch%d_mean' % (gain, ch)]/df['%s_ch%d_std' % (gain, ch)]
            plt.plot(df['Qinj_pC'], SNR, ls=ls[i], label=gain)
    plt.ylabel('SNR')
    plt.xlabel('Injected charge [pC]')
    plt.title('External pulser injection through a Cinj %d pF in ch%d' % (Cinj, injected_channel))
    plt.grid()
    plt.yscale('log')
    plt.legend()
    plt.tight_layout()
    plt.savefig(config['save_folder']+'../SNR_vs_Qinj.png')
    plt.show()


    df_all = pd.read_csv(config['save_folder']+'../df_all.csv')
    for i, gain in enumerate(['low', 'high']):
        plt.figure()
        for Qinj in np.unique(df_all['Qinj_pC']):
            for ch in [injected_channel]:
                serie = df_all.loc[df_all['Qinj_pC']==Qinj, 'adc_%s_ch%d_B%d' % (gain, ch, board)]
                serie -= serie.mean()
                counts, bins = np.histogram(serie, bins=10, density=True)
                # plt.stairs(counts, bins, fill=True, label='dt' + ch_suffixA + ch_suffixB)
                plt.hist(bins[:-1], bins, weights=counts, align='left', fill=True, label=gain)
        plt.xlabel('Energy deviation from mean [adc]')
        plt.ylabel('Count')
        plt.title('Histogram of the energy deviation versus Qinj with Cinj %d pF in ch%d '%(Cinj, injected_channel)+gain)
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.close()


        # plt.savefig(config['save_folder']+'../RMS_energy_vs_Qinj.png')



    # # probed_channel = 63
    # external_ADC_labels = [col for col in df.columns if col.startswith('pdet_')]
    # # external_ADC_labels = ['pdet_LG_ch%d'%probed_channel, 'pdet_HG_ch%d'%probed_channel]
    # for gi, gain in enumerate(['low', 'high']):
    #     plt.subplot(1, 2, gi + 1)
    #
    #     labels = [external_ADC_labels[gi]]  # ['adc_%s_ch%d' % (gain, ch) for ch in range(3)] +
    #     df_pivot_mean = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="mean").reset_index()
    #
    #     df_pivot_std = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="std").reset_index()
    #
    #     for label in labels:
    #         plt.errorbar(df_pivot_mean.loc[:, 'Qinj_pC'], df_pivot_mean.loc[:, label],
    #                      yerr=df_pivot_std.loc[:, label], label=label, fmt='o')
    #
    #     plt.xlabel('Charge injected [pC]')
    #     plt.ylabel('ADC [lsb]')
    #     plt.grid()
    #     plt.legend()  # ncols=4
    #     plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
    #                  xycoords='axes pixels')
    # plt.tight_layout()
    # plt.savefig(folder + "external ADC pdet HL LG versus charge.png")
    # # plt.show()
    # plt.close()
    #
    # plt.figure(0, figsize=(10, 8))
    # for gi, gain in enumerate(['low', 'high']):
    #     plt.subplot(1, 2, gi + 1)
    #     plt.title(gain)
    #     labels = ['adc_%s_ch%d' % (gain, ch) for ch in range(16)]
    #     df_pivot_mean = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="mean").reset_index()
    #
    #     df_pivot_std = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="std").reset_index()
    #
    #     for label in labels:
    #         plt.errorbar(df_pivot_mean.loc[:, 'Qinj_pC'], df_pivot_mean.loc[:, label],
    #                      yerr=df_pivot_std.loc[:, label], label=label, fmt='o')
    #
    #     plt.xlabel('Charge injected [pC]')
    #     plt.ylabel('ADC [lsb]')
    #     plt.grid()
    #     plt.legend()  # ncols=4
    #     plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7),
    #                  xycoords='axes pixels')
    # plt.tight_layout()
    # plt.savefig(folder + "internal ADC pdet HL LG versus charge.png")
    # # plt.show()
    # plt.close()


def analyse_charge_scan_old(search_string):
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    channel = 0
    channel_gain = 'low'
    stats_dict = {'raw_event_count': [],
                  # 'asked_event_count': [],
                  # 'readout_mode': [],
                  # 'status_32_count': [],
                  # 'status_35_count_after_removing_digital_retriggering_frames': [],
                  # 'frame_count_per_injection_found': [],
                  # 'exploitable_event_count': [],
                  # 'file': [],
                  # 'delay': [],
                  # 'hit_freq': [],
                  # 'hitPeriod_in320MHz': []
                  }


    for csv_file in csv_files:

        df = pd.read_csv(csv_file)
        df_len_init = len(df)

        for status in np.unique(df.status):
            if status == 0:
                continue
            mask_status = df.status == status
            status_count_array = mask_status.value_counts()[mask_status.value_counts().index == True].values
            status_count = status_count_array[0] - 1 if status_count_array else 0

            df = df[~mask_status].reset_index()
            if 'status_%d_count'%status not in stats_dict:
                # stats_dict.update({'status_%d_count': [0]*len(stats_dict['raw_event_count'])})
                stats_dict['status_%d_count'%status] = [0]*len(stats_dict['raw_event_count'])
            stats_dict['status_%d_count'%status].append(status_count)

        df['CPT'] = df.time.apply(lambda x: x << 14) + df.msb_cpt.apply(lambda x: x << 4) + df[
            'cpt_%s_ch%d' % (channel_gain, channel)]
        hitPeriod_in_320MHz_ck_cycles = int(10e-6/3.125e-9)
        df['CPT_modulo_hit_period'] = df.CPT % hitPeriod_in_320MHz_ck_cycles

        for Qinj in np.unique(df.Qinj_pC):
            charge_selection = df.Qinj_pC == Qinj
            clock_phases = df.loc[charge_selection, 'CPT_modulo_hit_period'].value_counts()
            dominant_clock_phase = clock_phases[clock_phases == np.max(clock_phases)].index[0]
            event_with_dominant_ck_phase = df.CPT_modulo_hit_period == dominant_clock_phase
            clock_phase_above_modulo = (df.loc[event_with_dominant_ck_phase & charge_selection, 'CPT'] // hitPeriod_in_320MHz_ck_cycles).min()
            clock_phase_above_modulo = clock_phase_above_modulo * hitPeriod_in_320MHz_ck_cycles
            # clock_phase_above_modulo = (df.loc[event_with_dominant_ck_phase & one_delay_selection & good_tdc_selection, 'CPT']//hitPeriod_in_320MHz_ck_cycles).iloc[3]
            # clock_phase_above_modulo =  (clock_phase_above_modulo-3) * hitPeriod_in_320MHz_ck_cycles

            charge_count_array = charge_selection.value_counts()[charge_selection.value_counts().index == True].values
            charge_count = charge_count_array[0] if charge_count_array else 0
            df.loc[charge_selection, 'iter'] = ((df.loc[charge_selection, 'iter'] - df.loc[charge_selection, 'iter'].min())%charge_count)
            df.loc[charge_selection,'expected_CPT'] =  df.loc[charge_selection, 'iter'] * hitPeriod_in_320MHz_ck_cycles + dominant_clock_phase + clock_phase_above_modulo
            df['diff_CPT'] = df.CPT.diff(-1)
            df['diff'] = df.expected_CPT - df.CPT

            dfa = df.loc[charge_selection, ['iter', 'diff', 'diff_CPT', 'CPT', 'expected_CPT']]
            pass
        # readout_mode = re.findall("(?<=mode_)[a-z_]+", filepath)[0]

        # for ch in range(2):
        #     # if (df['adc_low_ch%d'%i].apply(lambda x:x&0b11) == 0).all():
        #         # all 2 lsb bits at 0
        #     for g in ['low', 'high']:
        #         label = 'adc_%s_ch%d'%(g, ch)

                # plt.scatter(df.Qinj_pC, df[label], label=label)
        # plt.grid()
        # plt.legend(ncols=4)
        # plt.show()

        # # if DLL invert bits order within each adc fields :
        # for ch in range(16):
        #     for i, gain in enumerate(['low', 'high']):
        #         label = 'adc_%s_ch%d' % (gain, ch)
        #         df[label] = df[label].apply(lambda x: (reverse_mask(x) >> (32 - 10)))

        stats_dict['raw_event_count'].append(df_len_init)
        # stats_dict['asked_event_count'].append(expected_frame_count)
        # stats_dict['readout_mode'].append(readout_mode)
        print(stats_dict)

        # stats_dict['status_35_count_after_removing_digital_retriggering_frames'].append(status_35_count)
        # stats_dict['frame_count_per_injection_found'].append(number_frame_per_injection)
        # stats_dict['exploitable_event_count'].append(len(df))

        plt.figure(0, figsize=(10, 8))
        # probed_channel = 63
        external_ADC_labels = [col for col in df.columns if col.startswith('pdet_')]
        # external_ADC_labels = ['pdet_LG_ch%d'%probed_channel, 'pdet_HG_ch%d'%probed_channel]
        for gi, gain in enumerate(['low', 'high']):
            plt.subplot(1, 2, gi+1)

            labels = [external_ADC_labels[gi]]  #['adc_%s_ch%d' % (gain, ch) for ch in range(3)] +
            df_pivot_mean = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="mean").reset_index()

            df_pivot_std = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="std").reset_index()

            for label in labels:
                plt.errorbar(df_pivot_mean.loc[:, 'Qinj_pC'], df_pivot_mean.loc[:, label],
                             yerr=df_pivot_std.loc[:, label], label=label, fmt='o')


            plt.xlabel('Charge injected [pC]')
            plt.ylabel('ADC [lsb]')
            plt.grid()
            plt.legend()  #ncols=4
            plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
        plt.tight_layout()
        plt.savefig(folder + "external ADC pdet HL LG versus charge.png")
        # plt.show()
        plt.close()

        plt.figure(0, figsize=(10, 8))
        for gi, gain in enumerate(['low', 'high']):
            plt.subplot(1, 2, gi+1)
            plt.title(gain)
            labels = ['adc_%s_ch%d' % (gain, ch) for ch in range(16)]
            df_pivot_mean = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="mean").reset_index()

            df_pivot_std = pd.pivot_table(df, values=labels, index='Qinj_pC', aggfunc="std").reset_index()

            for label in labels:
                plt.errorbar(df_pivot_mean.loc[:, 'Qinj_pC'], df_pivot_mean.loc[:, label],
                             yerr=df_pivot_std.loc[:, label], label=label, fmt='o')


            plt.xlabel('Charge injected [pC]')
            plt.ylabel('ADC [lsb]')
            plt.grid()
            plt.legend()  #ncols=4
            plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
        plt.tight_layout()
        plt.savefig(folder + "internal ADC pdet HL LG versus charge.png")
        # plt.show()
        plt.close()
    pass

    # plt.plot(df.loc[selection, 'index'], df.loc[selection, 'adc_low_ch0'])
    # plt.plot(df.loc[selection, 'index'], df.loc[selection, 'adc_low_ch1'])
        # plt.show()

    df['iter'] = df.index

    plt.figure(figsize=(10, 8))
    for channel in [1, 2]:
        for gain in ['low', 'high']:
            label = 'adc_%s_ch%d' % (gain, channel)
            std_list = []
            Vinj_mV_list = []
            for Vinj_mV in np.unique(df.Vinj_mV):
                std_list.append(df.loc[(df[label] > 50) & (df['Vinj_mV'] == Vinj_mV), label].std())
                Vinj_mV_list.append(Vinj_mV)
            plt.plot(Vinj_mV_list, std_list, label=label)
    plt.grid()
    plt.legend()
    plt.xlabel('Vinj_mV')
    plt.ylabel('ADC STD [adc]')
    plt.title("ADC std excluding erroneous points (pedestal ?) \nOnly ch1 is injected, ch2 sees what's left of ch1 \ndue to adc early sampling of mux output")
    plt.tight_layout()
    plt.savefig(folder + "adc_std_vs_injected_voltage.png")
    plt.show()

    df = df.sort_values(by='iter')
    for channel in range(16):
        plt.figure(figsize=(10, 8))

        channel = channel%16
        markers = ['o', 'x', '+', 'v', '^', 's', 'p', '*', 'D', 'P']
        for i, gain in enumerate(['low', 'high']):
            plt.subplot(1, 2, i+1)
            label = 'adc_%s_ch%d' % (gain, channel)

            for mi, Vinj_mV in enumerate(np.unique(df.Vinj_mV)):
                selection = df.Vinj_mV == Vinj_mV
                plt.scatter(df.loc[selection, 'iter'], df.loc[selection, label], label='Vinj_mv = %d'%Vinj_mV, marker = markers[mi])

            plt.title(label)
            plt.xlabel('iteration')
            plt.ylabel('ADC [lsb]')
            plt.grid()
            plt.legend()
            plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')

        plt.tight_layout()
        plt.savefig(folder + "adc_ch%d.png"%channel)
        # plt.close()
    plt.show()
    pass

def plot_adc(file):

    df = pd.read_csv(file)

    plt.figure(1, figsize=(10, 8))

    df_pivot_mean = pd.pivot_table(df, values=['pdet_LG', 'pdet_HG'], index='Vinj_mV',
                                  aggfunc="mean").reset_index()


    plt.grid()
    plt.legend()
    # plt.annotate("\n".join([os.path.basename(csv_file) for csv_file in csv_files]), xy=(5, 7), xycoords='axes pixels')
    plt.tight_layout()
    plt.show()



def correct_adc_value():

    tau_rise = 16.37e-9 / np.log(9) # 1st order time constant = rising time 10-90% / ln(9)
    tau_fall = 18.71e-9 / np.log(9)
    tempo_dig_ck_freq = 80e6
    K_rise = 1-np.exp(-1/(tau_rise*tempo_dig_ck_freq))
    K_fall = 1-np.exp(-1/(tau_fall*tempo_dig_ck_freq))
    K_avg = 1-np.exp(-1/(np.average([tau_rise, tau_fall])*tempo_dig_ck_freq))

    # raw_measured_adc_value_per_channel = np.random.randint(0, 1024, 16) # ch0 to ch15
    raw_measured_adc_value_per_channel = [176, 444, 921, 951, 866, 706, 908, 793, 356, 979, 188, 893, 600, 972, 121, 905]

    corrected_adc_value_per_channel = []
    corrected_adc_value_per_channel2 = []
    for i, adc_value in enumerate(raw_measured_adc_value_per_channel):
        if i == 0:
            corrected_adc_value = adc_value
            corrected_adc_value2 = adc_value
        else:
            if adc_value < corrected_adc_value_per_channel[i-1]:
                corrected_adc_value = adc_value/K_fall + corrected_adc_value_per_channel[i-1] * (1-1/K_fall)
                pass
            else:
                corrected_adc_value = adc_value/K_rise + corrected_adc_value_per_channel[i-1] * (1-1/K_rise)
                pass
            corrected_adc_value2 = adc_value/K_avg + corrected_adc_value_per_channel[i-1] * (1-1/K_avg)

        corrected_adc_value_per_channel2.append(round(corrected_adc_value2))
        corrected_adc_value_per_channel.append(round(corrected_adc_value))


    t_total = np.array([])
    V_total = np.array([])
    t_init = 0
    t_step = 50
    a = ((len(raw_measured_adc_value_per_channel)-1)*t_step)*1.1
    for i in range(1, len(corrected_adc_value_per_channel)):
        t = np.arange(0, t_step, 1)*1e-9
        delta = corrected_adc_value_per_channel[i] - corrected_adc_value_per_channel[i-1]
        tau = tau_rise if delta > 0 else tau_fall
        V = (1-np.exp(-t/tau))*delta + corrected_adc_value_per_channel[i-1]

        if i==1:
            label_green= 'corrected'
            label_blue = 'measured'
            label_Ts = 'ADC sampling time'
        else:
            label_green=''
            label_blue = ''
            label_Ts = ''

        plt.axhline(raw_measured_adc_value_per_channel[i], xmin=t_init/a, xmax=(t_init+50)/a, color='blue', linestyle='--', label=label_blue)
        plt.axhline(corrected_adc_value_per_channel[i-1], xmin=t_init/a, xmax=(t_init+50)/a, color='green', linestyle='--')
        plt.axhline(corrected_adc_value_per_channel[i], xmin=t_init/a, xmax=(t_init+50)/a, color='green', linestyle='--', label=label_green)
        plt.axvline(t_init+1e9/tempo_dig_ck_freq, color='r', linestyle='--', label=label_Ts)


        plt.axhline(corrected_adc_value_per_channel2[i-1], xmin=t_init/a, xmax=(t_init+50)/a, color='green', linestyle='solid')
        plt.axhline(corrected_adc_value_per_channel2[i], xmin=t_init/a, xmax=(t_init+50)/a, color='green', linestyle='solid')

        t_total = np.concatenate((t_total, t+t_init*1e-9))
        V_total = np.concatenate((V_total, V))
        t_init += 50

    plt.grid()
    plt.title("ADC readout for one cluster = 16 consecutive channels assuming 80 MHz clock\ntime constants from MUX simu schema tau_rise=%.1f ns tau_fall=%.1f ns"%(tau_rise*1e9, tau_fall*1e9))
    plt.plot(t_total*1e9, V_total, marker='.')
    plt.tight_layout()
    plt.legend()
    plt.ylabel("ADC value ")
    plt.xlabel("Time [ns] ")
    plt.show()


        # plt.plot(t*1e9, V, marker='.')
        # plt.axhline(raw_measured_adc_value_per_channel[i], color='blue', linestyle='--')
        # plt.axhline(corrected_adc_value_per_channel[i-1], color='green', linestyle='--')
        # plt.axhline(corrected_adc_value_per_channel[i], color='green', linestyle='--')
        # plt.axvline(1e9/tempo_dig_ck_freq, color='r', linestyle='--')
        # plt.grid()
        # plt.title("Channel %d "%i)
        # plt.show()


if __name__ == "__main__":

    # analyse_charge_scan("output/charge_scan/ch1/raw/0*.csv")
    # analyse_charge_scan("output/charge_scan/ch0/raw/0*.csv")
    # analyse_charge_scan("output/charge_scan/ch31/raw/0*.csv")
    # analyse_charge_scan("output/charge_scan/ch31/raw/1*.csv")
    # analyse_charge_scan("output/charge_scan/dual_ch/raw/34/34*.csv")
    # analyse_charge_scan("../output/charge_scan/dual_ch/raw/32*.csv")
    # analyse_charge_scan("output/charge_scan/dual_ch_dig_ck_40MHz/raw/13*.csv")
    # analyse_charge_scan("output/charge_scan/dual_ch_dig_ck_160MHz/raw/0*.csv")
    # analyse_charge_scan("output/charge_scan/dual_ch_dig_ck_40MHz/raw/13*.csv")
    # plot_adc("output/charge_scan/ch1/raw/2_B1_VDDD_1.3V_Cinj_100pF_adc_externe.csv")
    # plot_adc("output/charge_scan/ch0/raw/0_B2_VDDD_1.2V_Cinj_100pF_all.csv")

    # correct_adc_value()
    folder="../output/B6_TPR108/ext_pulser/10/raw/"
    # analyse_charge_scan(folder, suffix='Qinj')
    # plot_evolution_with_injected_charge(folder)
    #
    # analyse_charge_scan(folder, suffix='PAsh')
    # plot_RMS_evolution_with_suffix_variable(folder, suffix='PAsh')

    analyse_charge_scan(folder, suffix='shaper_delay')
    plot_RMS_evolution_with_suffix_variable(folder, suffix='shaper_delay')

