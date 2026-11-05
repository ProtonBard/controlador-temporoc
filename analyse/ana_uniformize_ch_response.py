import re, os, glob
import numpy as np
import pandas as pd
import yaml
from matplotlib import pyplot as plt
import matplotlib

from src.common_setup import *

matplotlib.use('Qt5Agg')
from common_analysis_TDC import *
from common_analyse_ADC import *
from analyse.common_data_decoding import *
from src.CONSTANTS import *
from colorsys import rgb_to_hsv, hsv_to_rgb


def plot_find_1pe_amplitude(search_folder):

    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("[0-9]+(?=/raw)", folder)
    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        return

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)


    plot_folder = folder + '/../plot/'
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)

    thres_scan_df_filename = search_folder + "B%d_trigger_counting_threshold_scan_HV_%.1f.csv" % (
    config['board'][0], 45.0)

    df = pd.read_csv(thres_scan_df_filename)


    res_df = find_1pe_amplitude(df, plot_folder)
    plot_SiPM_non_uniformity(res_df, plot_folder)


def plot_Sipm_gain_vs_channel(search_folder):

    folder = os.path.dirname(search_folder)
    folder_index_str = re.findall("[0-9]+(?=/raw)", folder)
    if folder_index_str:
        folder_index_str = folder_index_str[0]
    else:
        print("index in search_folder not found ", search_folder)
        return

    config_file = folder + "/config.yaml"
    with open(config_file, 'r') as outfile:
        config = yaml.safe_load(outfile)

    plot_folder = folder + '/../plot/'
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)

    res_df = pd.read_csv(plot_folder + "SiPM_gain.csv")
    plot_SiPM_non_uniformity(res_df, plot_folder)