import glob
import math
import os
import re

import numpy as np

from src.temporoc3 import *
import src.tools as tools
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')

def analyse_static_scan(search_string):
    print(search_string)

    csv_files = glob.glob(search_string)

    folder_index_str = re.findall("[0-9]+(?=_B)", csv_files[0])
    if folder_index_str:
        folder_index_str = folder_index_str[0]

    folder = os.path.dirname(csv_files[0]) + '/' + folder_index_str + '/'
    if not os.path.exists(folder):
        os.makedirs(folder)

    # for csv_file in csv_files:
    df = pd.read_csv(csv_files[0])
    conversion_factor = 1.2/(2**12-1)
    df['Vdiff_V'] = (df.dacP - df.dacN) *conversion_factor

    plt.scatter(df.Vdiff_V, df.ADC, s=2, marker='x')

    xmin =-3890*conversion_factor
    xmax =3690*conversion_factor
    plt.axvline(xmin, color='red')
    plt.axvline(xmax, color='red')
    selection = (df.Vdiff_V > xmin) & (df.Vdiff_V < xmax)
    par = np.polyfit(df.Vdiff_V[selection], df.ADC[selection], 1).tolist()

    xfit = np.linspace(xmin,xmax, 1000)
    yfit = par[0] * xfit + par[1]
    lsb_mV_per_adc = 1e3/par[0]
    plt.plot(xfit, yfit, color='tab:red', linestyle='--',
                         label="fit gain = %.2f adc/V offset = %.3f adc\n=> ADC lsb = %.1f mV/adc >> DAC step %.1f mV" % (par[0], par[1], lsb_mV_per_adc, 2*1.2*1e3/2**12))


    # full range fit
    # par = np.polyfit(df.Vdiff_V, df.ADC, 1).tolist()
    # xfit = np.linspace(-1.2, 1.2, 1000)
    # yfit = par[0] * xfit + par[1]
    # plt.plot(xfit, yfit, color='tab:orange', linestyle='--',
    #          label="fit gain = %.2f adc/V offset = %.3f ns adc" % (par[0], par[1]))

    plt.ylabel("ADC code")
    plt.xlabel("VinP - VinN [V]")
    plt.grid()
    plt.legend()
    plt.title("Standalone ADC linearity \nusing two 12-bits COTS DAC as differential input signal")
    plt.tight_layout()
    plt.xlim([1.02, 1.1])
    plt.ylim([1000, 1030])
    plt.savefig(folder+'linearity_zoom.png')
    plt.xlim([-0.08, 0.04])
    plt.ylim([480, 540])
    plt.savefig(folder+'linearity_zoom_center.png')
    plt.autoscale()
    plt.savefig(folder+'linearity.png')
    plt.close()
    # plt.show()


    df_std = pd.pivot_table(df[selection], index='Vdiff_V', values='ADC', aggfunc='std').reset_index()
    df_count = pd.pivot_table(df[selection], index='Vdiff_V', values='ADC', aggfunc='count').reset_index()
    plt.plot(df_std.Vdiff_V, df_std.ADC, label="RMS = %.1f adc"%np.mean(df_std.ADC))
    plt.grid()
    plt.legend()
    plt.ylabel("ADC code")
    plt.xlabel("VinP - VinN [V]")
    plt.title("Standard deviation over %d samples per diff voltage tested"%np.mean(df_count.ADC))
    plt.tight_layout()
    plt.savefig(folder+'data_check_std_per_acquistion.png')
    plt.close()

    # INL
    # wrong method
    # df_mean = pd.pivot_table(df, index='Vdiff_V', values='ADC', aggfunc='mean').reset_index()
    # yfit = par[0] * df_mean.Vdiff_V + par[1]
    # df_mean['INL_adc'] = (df_mean.ADC - yfit)
    # df_mean['INL_mV'] = (df_mean.ADC - yfit)/par[0]*1e3

    df_mean = pd.pivot_table(df, index='ADC', values='Vdiff_V', aggfunc='mean').reset_index()
    df_mean = df_mean[(df_mean.ADC != 0) & (df_mean.ADC != 1023)]
    yfit = (df_mean.ADC - par[1]) / par[0]
    df_mean['INL_mV'] = (df_mean.Vdiff_V - yfit)*1e3
    df_mean['INL_adc'] = df_mean['INL_mV']/lsb_mV_per_adc

    for i, label in enumerate(['adc', 'mV']):

        rms = np.std(df_mean['INL_'+label])
        inl_min = np.min(df_mean['INL_'+label])
        inl_max = np.max(df_mean['INL_'+label])
        plt.plot(df_mean.ADC, df_mean['INL_'+label], label='INL in %s : RMS = %.1f min = %.1f max = %.1f\nexcluding edges {0 ; 1023}, lsb = %.1f mV/adc'%(label, rms, inl_min, inl_max, lsb_mV_per_adc))
        plt.legend()
        plt.grid()
        plt.xlabel("ADC code")
        plt.ylabel("Residue [%s]"%label)

        # mng = plt.get_current_fig_manager()
        # mng.full_screen_toggle()
        plt.tight_layout()
        plt.savefig(folder+'INL_%s.png'%label)
        plt.close()


    df_mean['DNL_adc'] = ((df_mean.Vdiff_V - np.roll(df_mean.Vdiff_V, 1))*1e3 - lsb_mV_per_adc)/lsb_mV_per_adc
    df_mean = df_mean.iloc[1:]

    label = 'adc'
    rms = np.std(df_mean['DNL_'+label])
    dnl_min = np.min(df_mean['DNL_'+label])
    dnl_max = np.max(df_mean['DNL_'+label])
    plt.plot(df_mean.ADC, df_mean['DNL_'+label], label='DNL in %s : RMS = %.1f min = %.1f max = %.1f\nexcluding edges {0 ; 1 ; 1023}, lsb = %.1f mV/adc'%(label, rms, dnl_min, dnl_max, lsb_mV_per_adc))
    plt.legend()
    plt.grid()
    plt.xlabel("ADC code")
    plt.ylabel("DNL [lsb]")

    # mng = plt.get_current_fig_manager()
    # mng.full_screen_toggle()
    plt.tight_layout()
    plt.savefig(folder+'DNL.png')
    # plt.close()
    plt.show()
    pass

if __name__ == '__main__':
    analyse_static_scan("output/standalone_adc/raw/0*.csv")