import os
import re
import shutil

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import scipy
import scipy.optimize as opt
from scipy.special import erf, erfc
from src.CONSTANTS import *
from typing import Optional
import yaml


def str_to_int(s: str) -> Optional[int]:
    assert isinstance(s, str)
    i: int = 0
    try:
        i = int(s, 0)
    except ValueError:
        return None
    return i


def update_config_dict(config, cluster_list):
    config.update({"frame_count_cluster%d" % ci: [0] for ci in cluster_list})
    return config


def save_config_file(config, filename="config"):
    config_file = config["save_folder"] + filename + ".yaml"
    with open(config_file, "w") as outfile:
        yaml.dump(
            dict(config), outfile, default_flow_style=False, Dumper=VerboseSafeDumper
        )
    outfile.close()


def save_post_analysis_config_file(config, filename='config_post_analysis.yaml'):
    config_file = config["save_folder"] + filename
    with open(config_file, "w") as outfile:
        yaml.dump(
            dict(config), outfile, default_flow_style=False, Dumper=VerboseSafeDumper
        )
    outfile.close()

def save_config_file_copy(config):
    config_file = config["save_folder"] + "config.yaml"
    config_file_copy = config["output_folder"] + "config_post_analysis.yaml"
    if not os.path.exists(config_file_copy):
        shutil.copyfile(config_file, config_file_copy)
    with open(config_file_copy, "w") as outfile:
        yaml.dump(
            dict(config), outfile, default_flow_style=False, Dumper=VerboseSafeDumper
        )
        outfile.close()


class VerboseSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def modelFitLinear(x, a, b):
    return a * x + b


def asic_map(
    data,
    fig=None,
    ax=None,
    clabel=None,
    vmin=None,
    vmax=None,
    nbOfLines=8,
    cmap="rainbow",
    txt="",
):
    """
    This fonction plot the 2D matrix of the 8x8 pixels array.
    `pix` must be a 1D array of 64 elements of any quantities.
    The first 8 pixels is the first column etc ...
    `clabel` is the label of the color bar.
    `vmin` and `vmax` are limit values for the color bar
    `fig` and `ax` can be specified to plot these maps on subplots.
    """

    # Re-shaping of the array
    m = np.array(
        [data[i * nbOfLines : (i + 1) * nbOfLines] for i in range(0, nbOfLines)],
        dtype=float,
    )
    m = np.swapaxes(m, 0, 1)
    m = m[::-1,]

    # Figure and axis
    if not fig:
        fig = plt.gcf()
    if not ax:
        ax = plt.gca()

    # white space
    # plt.subplots_adjust(top = 0.98, bottom = 0.02, right = 0.98, left = 0.02,
    #                     hspace = 0, wspace = 0)

    # Range of the z-axis
    # median=np.median(data[data > 0])
    # diff=max( abs(np.max(data[data > 0])-median), abs(np.min(data[data > 0])-median))
    if not vmin:
        # vmin=median-diff
        vmin = data.min()
    if not vmax:
        # vmax=median+diff
        vmax = data.max()
    # Plot
    im = ax.imshow(m, alpha=0.8, cmap=cmap)
    im.set_clim(vmin, vmax)

    # Color bar
    cbar = fig.colorbar(im, ax=ax)
    if clabel:
        cbar.set_label(clabel)
    # ax.set_aspect('equal')
    ax.set_aspect("auto")

    # Grid
    ax.set_xticks(np.arange(m.shape[1] + 1) - 0.5)
    ax.set_yticks(np.arange(m.shape[0] + 1) - 0.5)
    ax.xaxis.set_ticklabels([])
    ax.yaxis.set_ticklabels([])
    # ax.grid(color="w", linestyle='-', linewidth=1.5, alpha=1)

    median = np.median(data)
    rms = np.std(data)

    plt.text(
        1.14,
        0.94,
        "Max {:.1f} mV\nMedian {:.1f} mV\nMean {:.1f} mV\nMin {:.1f}mV\nRMS {:.2f} mV".format(
            np.max(data), median, np.mean(data), np.min(data), rms
        ),
        transform=ax.transAxes,
        fontsize=8,
    )

    # rms =np.std(data[data >0])
    plt.text(1.14, 0.89, "".format(rms), transform=ax.transAxes, fontsize=8)
    print(data)

    # write numbers
    for (j, i), label in np.ndenumerate(m):
        r = 1
        if label < 1:
            r = 2
        plt.text(i, j, str(round(label, r)), ha="center", va="bottom")
        plt.text(i, j, i * 8 + (7 - j), ha="center", va="top")

    # ax.set_xticks(range(8), range(8))
    # ax.set_yticks(range(8), reversed(range(8)))
    # ax.set_xlabel("Column index")
    # ax.set_ylabel("Row index")

    plt.tight_layout()
    return


def asic_col(
    data,
    fig=None,
    ax=None,
    clabel=None,
    vmin=None,
    vmax=None,
    nbOfLines=8,
    cmap="rainbow",
    txt="",
):
    """
    This fonction plot the 2D matrix of the 8x8 pixels array.
    `pix` must be a 1D array of 64 elements of any quantities.
    The first 8 pixels is the first column etc ...
    `clabel` is the label of the color bar.
    `vmin` and `vmax` are limit values for the color bar
    `fig` and `ax` can be specified to plot these maps on subplots.
    """

    # Re-shaping of the array
    # m = np.array([data[ i *nbOfLines:( i +1 ) *nbOfLines] for i in range(0, nbOfLines)], dtype=float)
    # m = np.swapaxes(m, 0, 1)
    # m = m[::-1 ,]

    m = np.array([data])
    m = np.swapaxes(m, 0, 1)
    # m = m[::-1 ,]

    # Figure and axis
    if not fig:
        fig = plt.gcf()
    if not ax:
        ax = plt.gca()

    # white space
    # plt.subplots_adjust(top = 0.98, bottom = 0.02, right = 0.98, left = 0.02,
    #                     hspace = 0, wspace = 0)

    # Range of the z-axis
    # median=np.median(data[data > 0])
    # diff=max( abs(np.max(data[data > 0])-median), abs(np.min(data[data > 0])-median))
    if not vmin:
        # vmin=median-diff
        vmin = data.min()
    if not vmax:
        # vmax=median+diff
        vmax = data.max()
    # Plot
    im = ax.imshow(m, alpha=0.8, cmap=cmap)
    im.set_clim(vmin, vmax)

    # Color bar
    cbar = fig.colorbar(im, ax=ax)
    if clabel:
        cbar.set_label(clabel)
    ax.set_aspect("auto")

    # Grid
    ax.set_yticks(np.arange(63, -1, -1))
    ax.invert_yaxis()
    ax.xaxis.set_ticklabels([])

    median = np.median(data)
    rms = np.std(data)

    fitParam, cov = opt.curve_fit(modelFitLinear, range(64), data)
    slope = fitParam[0]

    plt.text(
        1.14,
        0.94,
        "Max {:.1f} mV\nMedian {:.1f} mV\nMean {:.1f} mV\nMin {:.1f}mV\nRMS {:.2f} mV\nGradient {:.1f} mV/ch".format(
            np.max(data), median, np.mean(data), np.min(data), rms, slope
        ),
        transform=ax.transAxes,
        fontsize=8,
    )

    print(data)

    # write numbers
    for (ch, _), value in np.ndenumerate(m):
        plt.text((ch % 16) / 16 - 0.5, ch - 0.5, str(round(value, 1)))

    ax.set_ylabel("Channel")

    plt.tight_layout()
    return


def find_new_folder_index(local_output_dir, config, forced_index=None):

    # for board, mode in config['board'].items():
    #     config['config_B%d'% board] = {}
    #     config['config_B%d'% board]['mode'] = mode

    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    if forced_index is not None:
        new_index = forced_index

    else: # find a new index
        dir_list = list(next(os.walk(local_output_dir))[1])
        # dir_and_files_list = os.listdir(local_output_dir)
        for dir in dir_list:
            if len(os.listdir(local_output_dir + dir + "/")) == 0:
                os.rmdir(local_output_dir + dir + "/")

        # find unique new file index
        dir_list = list(next(os.walk(local_output_dir))[1])
        if not dir_list:
            new_index = 0
        else:
            max_index = -1
            for dir in dir_list:
                # index = int(dir)
                index = int(re.findall("[0-9]+", dir)[0])
                if index > max_index:
                    max_index = index
            new_index = max_index + 1
            if "restart_from_last_step" in config.keys():
                if config["restart_from_last_step"]:
                    new_index = max_index

    local_output_dir += "%d/raw/" % new_index

    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)

    plot_folder = local_output_dir + "/../"
    if not os.path.exists(plot_folder):
        os.makedirs(plot_folder)
    config["plot_folder"] = plot_folder

    config_file = local_output_dir + "/config.yaml"

    # explorer_file = local_output_dir + "/../../explorer.bat"
    print("Will save events in folder %d" % new_index)
    print("file:///"+os.path.abspath(local_output_dir).replace('\\', '/'))
    config["save_folder"] = local_output_dir

    if "restart_from_last_step" in config.keys():
        if config["restart_from_last_step"]:
            with open(config_file, "r") as outfile:
                config.update(yaml.safe_load(outfile))
                pass

    return new_index, local_output_dir


def get_trigger_condition_from_ASIC_config(sc_file):
    # read how is configured global_trigger bits : 66, 3, 2, 0
    return


def modelGauss(x, mu, sigma, amp):
    return (
        amp
        * (1 / (sigma * (np.sqrt(2 * np.pi))))
        * (np.exp((-1.0 / 2.0) * (((x - mu) / sigma) ** 2)))
    )


def modelGaussExp(x, mu, sigma, amp, lambd):
    return amp * (
        lambd
        / 2
        * np.exp(lambd / 2 * (2 * mu + lambd * sigma * sigma - 2 * x))
        * (1 - erf((mu + lambd * sigma * sigma - x) / (1.414213562 * sigma)))
    )


def ScurveFit(x, mu, sigma):
    return 0.5 * erfc((x - mu) / (sigma * 1.414213562))

def ScurveFit_noDen(x, mu, one_over_sigma):
    return 0.5 * erfc((x - mu) * one_over_sigma / 1.414213562)

def ScurveFitA(x, mu, sigma, A):
    return A * erfc((x - mu) / (sigma * 1.414213562))

def ScurveFit_Delagnes(x, mu, sigma, No):
    # initial mu should be a very good guess
    y = 1 - np.exp(-No * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2)))
    # formula from Radioroc datasheet page 30
    y[x<mu] = 1
    # because probability function is symmetric : tends towards 0 for +inf and -inf
    return y

def Scurve_sum_fit(x, A1, mu1, sigma1, A2, mu2, sigma2, A3, mu3, sigma3):
    return (
        A1 / 2 * erfc((x - mu1) / (sigma1 * 1.414213562))
        + A2 / 2 * erfc((x - mu2) / (sigma2 * 1.414213562))
        + A3 / 2 * erfc((x - mu3) / (sigma3 * 1.414213562))
    )


# def Scurve_sum_fit(x, A1, mu1, sigma1, A2, mu2, sigma2):
#     return A1/2 * erfc((x - mu1) / (sigma1 * 1.414213562)) + A2/2 * erfc((x - mu2) / (sigma2 * 1.414213562))

# def Scurve_sum_fit(x, A1, mu1, sigma1):
#     return A1/2 * erfc((x - mu1) / (sigma1 * 1.414213562))


def half_max_x(x, y):
    half = max(y) / 2.0
    signs = np.sign(np.add(y, -half))
    zero_crossings = signs[0:-2] != signs[1:-1]
    zero_crossings_i = np.where(zero_crossings)[0]
    if len(zero_crossings_i) == 2:
        r1 = lin_interp(x, y, zero_crossings_i[0], half)
        r2 = lin_interp(x, y, zero_crossings_i[1], half)
    else:
        r1 = min(x)
        r2 = max(x)
    dist = abs(r2 - r1)
    return r1, r2, dist


def lin_interp(x, y, i, half):
    return x[i] + (x[i + 1] - x[i]) * ((half - y[i]) / (y[i + 1] - y[i]))


def find_first_crossing(x, y, half):
    signs = np.sign(np.add(y, -half))
    zero_crossings = signs[0:-2] != signs[1:-1]
    zero_crossings_i = np.where(zero_crossings)[0]
    return lin_interp(x, y, zero_crossings_i[0], half)


def myerf(x, A, mu, sigma):
    return A * (1 + scipy.special.erf(-(x - mu) / (np.sqrt(2) * sigma)))


def thres_range(thres, half_span, step, excluding=None):
    assert half_span > 0

    # saturate threshold
    if excluding is None:
        excluding = {}
    threshold_high = thres + half_span + 1
    if threshold_high > 1023:
        threshold_high = 1023

    threshold_low = thres - half_span
    if threshold_low < 0:
        threshold_low = 0

    if excluding is not None:
        return list(set(range(threshold_low, threshold_high, step)) ^ set(excluding))
    else:
        return list(range(threshold_low, threshold_high, step))



def thres_range_start_from_center(thres, half_span, step):
    # saturate threshold
    threshold_high = thres + half_span + 1
    if threshold_high > 1023:
        threshold_high = 1023

    threshold_low = thres - half_span - 1
    if threshold_low < 0:
        threshold_low = 0

    threshold_set_to_sweep = list(range(thres, threshold_low, -step)) + list(
        range(thres, threshold_high, step)
    )
    return threshold_set_to_sweep


def plot_hex_sipm_cluster_map():

    mapping_sipm_ch = [i for i in range(1, 62)]  # SIPM channels
    mapping_asic_ch = np.array(
        get_ASIC_ch(mapping_sipm_ch, "Hamamatsu_S13361_6597")
    )  # ASIC channels
    mapping_asic_cluster = mapping_asic_ch // 16  # ASIC cluster

    dx = 1.875 * 2
    dy = 3.25
    X = [-2 * dx, -dx, 0, dx, 2 * dx]
    Y = [4 * dy for i in range(5)]
    X += [-5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2]
    Y += [3 * dy for i in range(6)]
    X += [-3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx]
    Y += [2 * dy for i in range(7)]
    X += [
        -7 * dx / 2,
        -5 * dx / 2,
        -3 * dx / 2,
        -dx / 2,
        dx / 2,
        3 * dx / 2,
        5 * dx / 2,
        7 * dx / 2,
    ]
    Y += [dy for i in range(8)]
    X += [-4 * dx, -3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx, 4 * dx]
    Y += [0 for i in range(9)]
    X += [
        -7 * dx / 2,
        -5 * dx / 2,
        -3 * dx / 2,
        -dx / 2,
        dx / 2,
        3 * dx / 2,
        5 * dx / 2,
        7 * dx / 2,
    ]
    Y += [-dy for i in range(8)]
    X += [-3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx]
    Y += [-2 * dy for i in range(7)]
    X += [-5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2]
    Y += [-3 * dy for i in range(6)]
    X += [-2 * dx, -dx, 0, dx, 2 * dx]
    Y += [-4 * dy for i in range(5)]
    X = np.array(X)
    Y = np.array(Y)
    C = mapping_asic_cluster
    # C = mapping_asic_ch
    # C = mapping_sipm_ch

    im = plt.hexbin(X, Y, C=C, gridsize=8)
    im.axes.set_aspect("equal")  # 0.8)
    im.axes.set(
        xlim=(
            X.min() - 2,
            X.max() + 2,
        ),
        ylim=(Y.min() - 2, Y.max() + 2),
    )
    plt.axis(False)
    plt.gcf().canvas.draw()  # update facecolor array
    fcolors = im.get_facecolors()
    # similar :
    # red, green, blue, l = im.cmap(im.norm(im.get_array()[j, i]))  # background_colors

    font_color = [
        (
            "white"
            if (red * 0.2126 + green * 0.7152 + blue * 0.0722) < 140 / 255
            else "black"
        )
        for (red, green, blue, _) in fcolors
    ]

    #### hexbin coordinates are different than X,Y given as input :

    # mapping = list(map(int, im.get_array())) # to compute with plt.hexbin(X, Y, C = mapping_sipm_ch)
    # print(mapping)
    # sort mapping list index based on its channel value
    # mapping = [val for (_, val) in sorted(zip(mapping, range(61)), key=lambda x: x[0], reverse=False)]
    # print(mapping)

    mapping = [
        8,
        13,
        18,
        23,
        28,
        38,
        42,
        46,
        50,
        54,
        58,
        3,
        7,
        12,
        17,
        22,
        27,
        31,
        34,
        37,
        41,
        45,
        49,
        53,
        57,
        60,
        0,
        2,
        6,
        11,
        16,
        21,
        26,
        30,
        32,
        33,
        36,
        40,
        44,
        48,
        52,
        56,
        59,
        1,
        5,
        10,
        15,
        20,
        25,
        29,
        35,
        39,
        43,
        47,
        51,
        55,
        4,
        9,
        14,
        19,
        24,
    ]
    # xy = im.get_offsets()
    # for i in range(xy.shape[0]):
    # x, y = [0], xy[i][1]

    for i in range(61):
        hexbin_index = mapping[i]  # coordinates in the hexbin system
        plt.annotate(
            str(mapping_sipm_ch[i]),
            xy=(X[i], Y[i]),
            ha="center",
            va="top",
            color=font_color[hexbin_index],
            size=6,
        )
        plt.annotate(
            str(mapping_asic_ch[i]),
            xy=(X[i], Y[i]),
            ha="center",
            va="bottom",
            color=font_color[hexbin_index],
            size=10,
        )
    cb = plt.colorbar(im, label="Cluster")
    print(im.get_array())
    print(font_color)
    plt.show()
    pass


def plot_hex_sipm_from_frame(
    frame, column_label, board, gain, board_config,
    title='',
    labels=None,
    plot_values=True,
    hidden_value=0,
    label_format="%d",
    font_size=10,
    plot_center_mass=False,
    threshold=None
):
    # get the channel list in the right order = SIPM order
    SiPM_channel_injected = list(np.sort(board_config["injected_channel_SiPM"][0]))
    ASIC_channels_injected = get_ASIC_ch(SiPM_channel_injected, "Hamamatsu_S13361_6597")

    missing_SiPM_channels = list(set(board_config["injected_channel_SiPM"][0]) ^ set(range(1, 62)))
    missing_ASIC_channels_values = [0] * len(missing_SiPM_channels)

    column_label_list = [column_label+"_%s_ch%d_B%d" % (gain, channel, board) for channel in ASIC_channels_injected]
    SiPM_channel_value = frame[column_label_list].to_list() + missing_ASIC_channels_values
    # print(frame[column_label_list])
    return plot_hex_sipm(
                            SiPM_channel_value,
                            title,
                            labels=labels,
                            plot_values=plot_values,
                            hidden_value=hidden_value,
                            label_format=label_format,
                            font_size=font_size,
                            plot_center_mass=plot_center_mass,
                            threshold=threshold)


def get_hex_sipm_XY_ch_coordinates():
    dx = 1.875 * 2
    dy = 3.25
    X = [-2 * dx, -dx, 0, dx, 2 * dx]
    Y = [4 * dy for i in range(5)]
    X += [-5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2]
    Y += [3 * dy for i in range(6)]
    X += [-3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx]
    Y += [2 * dy for i in range(7)]
    X += [
        -7 * dx / 2,
        -5 * dx / 2,
        -3 * dx / 2,
        -dx / 2,
        dx / 2,
        3 * dx / 2,
        5 * dx / 2,
        7 * dx / 2,
    ]
    Y += [dy for i in range(8)]
    X += [-4 * dx, -3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx, 4 * dx]
    Y += [0 for i in range(9)]
    X += [
        -7 * dx / 2,
        -5 * dx / 2,
        -3 * dx / 2,
        -dx / 2,
        dx / 2,
        3 * dx / 2,
        5 * dx / 2,
        7 * dx / 2,
    ]
    Y += [-dy for i in range(8)]
    X += [-3 * dx, -2 * dx, -dx, 0, dx, 2 * dx, 3 * dx]
    Y += [-2 * dy for i in range(7)]
    X += [-5 * dx / 2, -3 * dx / 2, -dx / 2, dx / 2, 3 * dx / 2, 5 * dx / 2]
    Y += [-3 * dy for i in range(6)]
    X += [-2 * dx, -dx, 0, dx, 2 * dx]
    Y += [-4 * dy for i in range(5)]
    X = np.array(X)
    Y = np.array(Y)
    return X, Y


def plot_hex_sipm(
    SiPM_channel_value,
    title='',
    labels=None,
    plot_values=True,
    hidden_value=0,
    label_format="%d",
    font_size=10,
    plot_center_mass=False,
    threshold=None
):
    # SiPM_channel_value : list for each channel from 1 to 61 included of value to display

    mapping_sipm_ch = [i for i in range(1, 62)]  # SIPM channels
    mapping_asic_ch = np.array(
        get_ASIC_ch(mapping_sipm_ch, "Hamamatsu_S13361_6597")
    )  # ASIC channels
    # mapping_asic_cluster = mapping_asic_ch// 16  # ASIC cluster

    X,Y = get_hex_sipm_XY_ch_coordinates()
    # C = mapping_asic_cluster
    # C = mapping_asic_ch
    # C = mapping_sipm_ch


    # cm = mpl.colormaps['viridis']
    # cm.set_bad(color="white")

    im = plt.hexbin(
        X, Y, C=SiPM_channel_value, gridsize=8, mincnt=1
    )  # , edgecolors='white') #, cmap=cm) # vmin=1, mincnt=1, vmax=150) #, edgecolor = "black", linewidths = 1.5) #

    im.axes.set_aspect("equal")  # 0.8)
    im.axes.set(
        xlim=(
            X.min() - 2,
            X.max() + 2,
        ),
        ylim=(Y.min() - 2, Y.max() + 2),
    )
    plt.axis(False)
    plt.gcf().canvas.draw()  # force update facecolor array
    fcolors = im.get_facecolors()


    # similar :
    # red, green, blue, l = im.cmap(im.norm(im.get_array()[j, i]))  # background_colors

    # try to make 0 transparent but to no avail
    # counts = im.get_array()
    # fcolors[:, 3] = counts > 0  # set the alpha channel to 0 where counts <= 0
    # im.set_facecolors(fcolors)  # update the facecolors of the patches

    if threshold:
        SiPM_channel_value = np.array(SiPM_channel_value)
        SiPM_channel_value[SiPM_channel_value < threshold] = hidden_value


    if plot_center_mass:

        xg = sum(i[0] * i[1] for i in zip(SiPM_channel_value, X)) / sum(SiPM_channel_value)
        yg = sum(i[0] * i[1] for i in zip(SiPM_channel_value, Y)) / sum(SiPM_channel_value)
        plt.plot(xg, yg, "+", markersize=20, color="red")

    #### hexbin coordinates are different than X,Y given as input :

    # mapping = list(map(int, im.get_array())) # to compute with plt.hexbin(X, Y, C = mapping_sipm_ch)
    # print(mapping)
    mapping = [
        27,
        44,
        28,
        12,
        57,
        45,
        29,
        13,
        1,
        58,
        46,
        30,
        14,
        2,
        59,
        47,
        31,
        15,
        3,
        60,
        48,
        32,
        16,
        4,
        61,
        49,
        33,
        17,
        5,
        50,
        34,
        18,
        35,
        36,
        19,
        51,
        37,
        20,
        6,
        52,
        38,
        21,
        7,
        53,
        39,
        22,
        8,
        54,
        40,
        23,
        9,
        55,
        41,
        24,
        10,
        56,
        42,
        25,
        11,
        43,
        26,
    ]
    # mapping = [
    #     8,
    #     13,
    #     18,
    #     23,
    #     28,
    #     38,
    #     42,
    #     46,
    #     50,
    #     54,
    #     58,
    #     3,
    #     7,
    #     12,
    #     17,
    #     22,
    #     27,
    #     31,
    #     34,
    #     37,
    #     41,
    #     45,
    #     49,
    #     53,
    #     57,
    #     60,
    #     0,
    #     2,
    #     6,
    #     11,
    #     16,
    #     21,
    #     26,
    #     30,
    #     32,
    #     33,
    #     36,
    #     40,
    #     44,
    #     48,
    #     52,
    #     56,
    #     59,
    #     1,
    #     5,
    #     10,
    #     15,
    #     20,
    #     25,
    #     29,
    #     35,
    #     39,
    #     43,
    #     47,
    #     51,
    #     55,
    #     4,
    #     9,
    #     14,
    #     19,
    #     24,
    # ]

    # sort mapping list index based on its channel value
    channels_present_list = [
        i for i, val in enumerate(SiPM_channel_value) if ~np.isnan(val)
    ]
    mapping = [
        val
        for (_, val) in sorted(
            zip(mapping, channels_present_list), key=lambda x: x[0], reverse=False
        )
    ]

    ## mapping if 61 channels present
    # mapping = [8, 13, 18, 23, 28, 38, 42, 46, 50, 54, 58, 3, 7, 12, 17, 22, 27, 31, 34, 37, 41, 45, 49, 53, 57, 60, 0, 2, 6, 11, 16, 21, 26, 30, 32, 33, 36, 40, 44, 48, 52, 56, 59, 1, 5, 10, 15, 20, 25, 29, 35, 39, 43, 47, 51, 55, 4, 9, 14, 19, 24]

    # xy = im.get_offsets()
    # for i in range(xy.shape[0]):
    # x, y = [0], xy[i][1]
    font_color = [
        (
            "white"
            if (red * 0.2126 + green * 0.7152 + blue * 0.0722) < 140 / 255
            else "black"
        )
        for (red, green, blue, _) in fcolors
    ]
    # font_color = ['white' if (red * 0.299 + green * 0.587 + blue * 0.114) < 200/255  else 'black' for (red, green, blue, _) in fcolors]

    if plot_values:
        if labels is None:
            labels = np.array(SiPM_channel_value)

        labels_without_NaN = labels[~np.isnan(labels)]

        for ch, (i, label) in zip(channels_present_list, enumerate(labels_without_NaN)):
            # hexbin_index = mapping[i]-1  # coordinates in the hexbin system
            hexbin_index = i
            # if hexbin_index>len(font_color):
            #     pass
            if not np.isinf(label):
                # if not np.isnan(labels[i]) and not np.isinf(labels[i]):
                # plt.annotate(str(mapping_sipm_ch[i]), xy=(X[i], Y[i]), ha='center', va='top', color=font_color[hexbin_index], size=6)
                # plt.annotate(str(mapping_asic_ch[i]), xy=(X[i], Y[i]), ha='center', va='bottom', color=font_color[hexbin_index], size=10)
                if labels[i] != hidden_value:
                    plt.annotate(
                        label_format % labels_without_NaN[i],
                        xy=(X[ch], Y[ch]),
                        ha="center",
                        va="center",
                        color=font_color[hexbin_index],
                        size=font_size,
                    )
                # plt.annotate(str(round(SiPM_channel_value[i])), xy=(X[i], Y[i]), ha='center', va='center', color='white', size=10)

    # plt.show()
    return im


def plot_data_quality(category_names, results, figname, output_folder):

    labels = list(results.keys())
    if len(labels) == 0:
        print("No data = ")
        return
    data = np.array(list(results.values()))
    data = data / data.sum(axis=1).reshape(-1, 1) * 100

    data_cum = data.cumsum(axis=1)  # + offset

    category_colors = plt.colormaps["RdYlGn"](np.linspace(0.85, 0.15, data.shape[1]))

    fig, ax = plt.subplots(figsize=(9.2, 5))
    ax.invert_yaxis()
    ax.xaxis.set_visible(False)
    ax.set_xlim(0, np.sum(data, axis=1).max())

    for i, (colname, color) in enumerate(zip(category_names, category_colors)):
        widths = data[:, i]
        starts = data_cum[:, i] - widths
        rects = ax.barh(
            labels, widths, left=starts, height=0.5, label=colname, color=color
        )

        r, g, b, _ = color
        text_color = "white" if r * g * b < 0.5 else "darkgrey"
        ax.bar_label(rects, fmt="%d %%", label_type="center", color=text_color)

    ax.legend(
        ncols=len(category_names),
        bbox_to_anchor=(0, 1),
        loc="lower left",
        fontsize="small",
    )
    plt.grid()
    # plt.tight_layout()
    plt.savefig(output_folder + "/%s.png" % figname)
    # plt.show()
    plt.close()


def find_latest_folder_index(folder):
    dir_list = list(next(os.walk(folder))[1])
    if not dir_list:
        return None
    else:
        max_index = -1
        for dir in dir_list:
            # index = int(dir)
            index = int(re.findall("[0-9]+", dir)[0])
            if index > max_index:
                max_index = index
        return max_index
