
class REGISTERS:
    addr_reserved = 0
    addr_debug = 1
    addr_dac_enable = 2  # should be raised to 1 then to 0 to write both DAC configuration
    addr_dac_d1_high = 3
    addr_dac_d1_low = 4
    addr_dac_d2_high = 5
    addr_dac_d2_low = 6


    addr_test_tdc_rst = 12
    addr_test_tdc_data = 13
    addr_test_tdc_hicn = 14  # count on 2 bytes
    addr_test_tdc_locn = 15  #

    addr_tmp_shift_in = 16
    addr_tmp_write = 17
    addr_tmp_read = 18
    addr_tmp_read_fifo = 19

    # addr_tmp_write_at_addr = 16
    # addr_tmp_temp_low = 17
    # addr_tmp_temp_high = 18
    # addr_tmp_configuration = 19
    # addr_tmp_thr_low_low = 20
    # addr_tmp_thr_low_high = 21
    # addr_tmp_thr_high_low = 22
    # addr_tmp_thr_high_high = 23

    addr_sc_status = 24
    addr_sc_status_bit_resetn_SC = 0
    addr_sc_status_bit_resetn_I2C = 1
    addr_sc_status_bit_enable_i2c_ck = 2  # 1.56 MHz for fast clock for state machine   78 kHz (1.56M/20) for slow clock for SCL
    addr_sc_status_bit_count_rst = 3  # count ack without expected polarity
    # addr_sc_status_bit_fifo_write_enable = 4
    addr_sc_status_bit_bus_idle = 7 # if 0, then decoder busy

    addr_sc_launch = 25
    addr_sc_shift_in = 26
    addr_sc_data_out = 27
    addr_sc_error_cnt = 28
    addr_sc_unack_cnt = 29

    addr_unused_1e = 30
    addr_unused_1f = 31

    # 32 to 47
    addr_deser_base = 32
    addr_deser_status = 0
    addr_deser_count_low = 1
    addr_deser_count_high = 2
    addr_deser_fifo_data = 3
    addr_deser_size = 4
    #
    addr_deser_common = 48
    # bit 0: closed : 0 (deserialiser closed) by default     1: open (= accept new events)
    # NB : should not be open when flushed
    # bit 1: flush : 1 (deserialiser under reset) by default
    # bit 3/2: 0= 320  (default) 1= 160 2= 80 3= 40
    # bit 4 : coincidence mode 0 by def (none)
    # bit 5 : foreign_reset_enable
    # bit 6 : enable_charge_filter
    # bit 7 : enable_inter_cluster_filter


    addr_deser_time_lsb = 49
    addr_deser_time_msb = 50

    addr_deseri_start_addr = 32
    addr_deseri_status = 0  # addr_deseri_start + cluster number * addr_deseri_status
    addr_deseri_count_low = 1
    addr_deseri_count_high = 2
    addr_deseri_fifo_reset = 3
    addr_deseri_fifo_data = 4
    addr_deseri_drop_reset = 5
    addr_deseri_drop_count = 6
    addr_deseri_pipe_ctrl = 7

    # bit1 flush: reset all state machines of frame sampler + serialisation + fifo (as addr_deseri_fifo_reset)
    # bit0 open: (each time a frame ends or 320 MHz clock is still) and FPGA frame sampler enabled and open at 0, then will refuse all next frames
    # otherwise, if open is 1, will accept next incoming frame


    # use case :
    # flush 1 open 0
    # reset 1
    # wait a frame ending is detected
    # reset 0
    # flush 0 open 1

    addr_test_adc_low = 52
    addr_test_adc_high = 53
    addr_debug_morse = 56

    # special status register (either for writing,
    addr_tpr_status_1 = 64
    # detail status bits
    tpr_conv_sys = 7
    tpr_ro_enable = 6
    tpr_val_evt = 5
    tpr_rstn_probe = 4
    tpr_power_on = 3
    tpr_hold_ext = 2
    tpr_rstn_latch = 1
    tpr_clk_mux_sel = 0

    addr_tpr_status_2 = 65
    # detail status bits
    resetn = 0
    pll_rstb = 5



    addr_unused_42 = 66
    addr_chip_id = 67
    # bit 0-4 : chip_id

    addr_delayer_high = 68
    addr_delayer_low = 69
    addr_unused_46 = 70
    addr_unused_47 = 71

    addr_test_tdc_config = 72
    addr_test_tdc_pulse_lo = 73
    addr_test_tdc_pulse_hi = 74
    addr_test_tdc_rstep_lo = 75
    addr_test_tdc_rstep_hi = 76
    addr_test_tdc_wstep_lo = 77
    addr_test_tdc_wstep_hi = 78

    addr_unused_4f = 79

    addr_probe_mon_reset = 80
    addr_probe_mon_time0 = 81
    addr_probe_mon_time1 = 82
    addr_probe_mon_val0 = 83
    addr_probe_mon_val1 = 84
    addr_probe_mon_val2 = 85
    addr_probe_mon_val3 = 86

    addr_unused_57 = 87

    # MSB to LSB : TRIG L ; TRIG H ; TRIG Q
    addr_read_reg_channel = 88 # nb of channels scan + 1  (0 = no channel,  1 = only channel 0)
    addr_read_reg_scan = 89  # write any value to reset the 3 sum counter (for L/H/Q)
    addr_read_reg_val_evt = 90

    # bit order detail of read register scan
    def get_index(discri: int|str):
        high_gain_index = 0
        low_gain_index = 1
        charge_index = 2

        # return read register index
        if (discri==1) | (discri=='TL'):
            return low_gain_index
        elif (discri==2) | (discri=='TH'):
            return high_gain_index
        elif discri == "TQ":
            return charge_index
        else:
            print('Unknown discriminator')
            exit(0)


    addr_read_reg_iter = 91

    addr_version_major = 92
    addr_version_minor = 93
    addr_version_string = 94

    addr_pll_spi_data = 95
    addr_pll_spi_count = 95 + 16 # firmware 2025_06_19_15_00 dumped

    addr_sma_control = 96
    addr_sma_control_io_2 = 97
    addr_sma_control_io_3 = 98
    addr_sma_control_io_4 = 99
    addr_sma_control_io_6 = 100
    addr_sma_control_io_7 = 101
    addr_sma_trigger_adc = 102 # rising edge sensitive to launch the ADC
    addr_sma_eof_foreign = 103 # rising edge sensitive to launch the ADC
    addr_sma_trigger_mon = 104
    addr_sma_trigger_ext = 105

    # Firmware synthesis date
    addr_timestamp_0 = 108
    addr_timestamp_1 = 109
    addr_timestamp_2 = 110
    addr_timestamp_3 = 111

    addr_adc_status = 112  # launch acquisition and fetch previous acquisition
    # write 1 launch adc
    # read tells if adc busy or not

    addr_adc_d0_high = 113
    addr_adc_d0_low = 114
    addr_adc_d1_high = 115
    addr_adc_d1_low = 116
    addr_adc_tdelay = 117  # 8bits count ck at 50 MHz

    addr_tpr_fpga_to_asic_clk_sel = 120
    addr_tpr_epll_clk_sel = 121


    addr_interrupt = 127

    default_value = {0: 0, 1: 0, 2: 1, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 1, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0, 19: 0, 20: 0, 21: 0, 22: 0, 23: 0, 24: 11, 25: 0, 26: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0, 32: 2, 33: 0, 34: 0, 35: 0, 36: 0, 37: 52, 38: 127, 39: 141, 40: 0, 41: 52, 42: 127, 43: 140, 44: 2, 45: 0, 46: 0, 47: 0, 48: 25, 49: 107, 50: 0, 51: 0, 52: 0, 53: 0, 54: 0, 55: 0, 56: 0, 57: 0, 58: 0, 59: 0, 60: 0, 61: 0, 62: 0, 63: 0, 64: 123, 65: 43, 66: 0, 67: 0, 68: 0, 69: 0, 70: 0, 71: 0, 72: 3, 73: 0, 74: 0, 75: 0, 76: 0, 77: 2, 78: 0, 79: 0, 80: 1, 81: 0, 82: 0, 83: 0, 84: 0, 85: 0, 86: 0, 87: 0, 88: 0, 89: 0, 90: 0, 91: 0, 92: 0, 93: 1, 94: 105, 95: 0, 96: 78, 97: 1, 98: 58, 99: 59, 100: 0, 101: 63, 102: 0, 103: 55, 104: 0, 105: 0, 106: 0, 107: 0, 108: 0, 109: 0, 110: 0, 111: 0, 112: 1, 113: 0, 114: 0, 115: 0, 116: 0, 117: 0, 118: 0, 119: 0, 120: 0, 121: 0, 122: 0, 123: 0, 124: 0, 125: 0, 126: 0, 127: 0}

class CONSTANTS:
    FRAME_LENGTH_RO_MODE_STR = \
    {'full_adc_tdc':    [1154,0b01111],
    'hg_adc_high_tdc':  [594, 0b01010],
    'lg_adc_low_tdc':   [594, 0b00101],
    'hg_lg_adc':        [578, 0b01100],
    'hg_adc':           [306, 0b01000],
    'lg_adc':           [306, 0b00100],
    'low_high_tdc':     [834, 0b00011],
    'high_tdc':         [434, 0b00010],
    'low_tdc':          [434, 0b00001],
    'hg_adc_low_tdc':   [706, 0b01001],
    'lg_adc_high_tdc':  [706, 0b00110],
    'hit':              [66,  0b10000],
    'fuller':           [1186,0b11111]}
    # all lengths include footer suffix of 12 bits at '1'

    FRAME_LENGTH_RO_MODE_INT = \
        {0: 34,
         1: 434,
         2: 434,
         3: 834,
         4: 306,
         5: 594,
         6: 706,
         7: 994,
         8: 306,
         9: 706,
         10: 594,
         11: 994,
         12: 578,
         13: 866,
         14: 866,
         15: 1154,
         16: 66,
         17: 466,
         18: 466,
         19: 866,
         20: 338,
         21: 626,
         22: 738,
         23: 1026,
         24: 338,
         25: 738,
         26: 626,
         27: 1026,
         28: 610,
         29: 898,
         30: 898,
         31: 1186}

    base_colnames_104 = ['status', 'mode', 'frames_found', 'bytes_dropped', 'time', 'msb_cpt', 'trigger_low', 'trigger_high']
    base_colnames_106 = ['status', 'mode', 'frames_found', 'bytes_dropped', 'time', 'mimic_time', 'mimic_time_right_shift_14', 'msb_cpt', 'trigger_low', 'trigger_high']
    cluster_channel_colnames = ['cpt_low_ch%d' % i for i in range(16)] \
                               + ['tdc_low_ch%d' % i for i in range(16)] \
                               + ['adc_low_ch%d' % i for i in range(16)] \
                               + ['cpt_high_ch%d' % i for i in range(16)] \
                               + ['tdc_high_ch%d' % i for i in range(16)] \
                               + ['adc_high_ch%d' % i for i in range(16)]

    COLNAMES104 = base_colnames_104 + cluster_channel_colnames
    COLNAMES106 = base_colnames_106 + cluster_channel_colnames


def is_firmware_top_2026_02_16_17_30(fw_hash):
    # assert len(config['fw_hash'])>2*84, "Firmware version could not be checked : length of hash read from FPGA not long enough"
    return '993250321021051141091199711410132102111114329711411610512032554684101109112111114111' in fw_hash,



class SIPM_CHANNEL_MAP:

    ASIC_ch_to_SiPM_ch_Hamamatsu_S13361_6597 = {
        0: None,
        1: None,
        2: None,
        3: 56,
        4: 59,
        5: 61,
        6: 58,
        7: 60,
        8: 52,
        9: 54,
        10: 57,
        11: 50,
        12: 53,
        13: 55,
        14: 46,
        15: 48,
        16: 45,
        17: 47,
        18: 51,
        19: 43,
        20: 39,
        21: 35,
        22: 38,
        23: 41,
        24: 37,
        25: 40,
        26: 44,
        27: 49,
        28: 30,
        29: 42,
        30: 28,
        31: 33,
        32: 36,
        33: 31,
        34: 27,
        35: 32,
        36: 20,
        37: 34,
        38: 29,
        39: 26,
        40: 19,
        41: 23,
        42: 13,
        43: 24,
        44: 21,
        45: 25,
        46: 22,
        47: 18,
        48: 12,
        49: 9,
        50: 7,
        51: 16,
        52: 14,
        53: 17,
        54: 15,
        55: 11,
        56: 6,
        57: 3,
        58: 1,
        59: 4,
        60: 2,
        61: 10,
        62: 8,
        63: 5
    }

    SiPM_ch_to_ASIC_ch_Hamamatsu_S13361_6597 = {
        1: 58,
        2: 60,
        3: 57,
        4: 59,
        5: 63,
        6: 56,
        7: 50,
        8: 62,
        9: 49,
        10: 61,
        11: 55,
        12: 48,
        13: 42,
        14: 52,
        15: 54,
        16: 51,
        17: 53,
        18: 47,
        19: 40,
        20: 36,
        21: 44,
        22: 46,
        23: 41,
        24: 43,
        25: 45,
        26: 39,
        27: 34,
        28: 30,
        29: 38,
        30: 28,
        31: 33,
        32: 35,
        33: 31,
        34: 37,
        35: 21,
        36: 32,
        37: 24,
        38: 22,
        39: 20,
        40: 25,
        41: 23,
        42: 29,
        43: 19,
        44: 26,
        45: 16,
        46: 14,
        47: 17,
        48: 15,
        49: 27,
        50: 11,
        51: 18,
        52: 8,
        53: 12,
        54: 9,
        55: 13,
        56: 3,
        57: 10,
        58: 6,
        59: 4,
        60: 7,
        61: 5}

    SiPM_ch_to_ASIC_ch_Broadcom_S4N44P164M = {'A1':63, 'B1':61, 'A2':59, 'B2':57, 'A3':55, 'B3':53, 'A4':51, 'B4':49, 'D8':47, 'C8':45, 'D7':43, 'C7':41, 'D6':39, 'C6':37, 'D5':35, 'C5':33, 'E1':31, 'F1':29, 'E2':27, 'F2':25, 'E3':23, 'F3':21, 'E4':19, 'F4':17, 'E5':15, 'F5':13, 'E6':11, 'F6':9, 'E7':7, 'F7':5, 'E8':3, 'F8':1, 'C1':62, 'D1':60, 'C2':58, 'D2':56, 'C3':54, 'D3':52, 'C4':50, 'D4':48, 'A5':46, 'B5':44, 'A6':42, 'B6':40, 'B8':38, 'A8':36, 'B7':34, 'A7':32, 'G1':30, 'G2':28, 'G3':26, 'G4':24, 'H1':22, 'H2':20, 'H3':18, 'H4':16, 'G5':14, 'H5':12, 'G6':10, 'H6':8, 'G7':6, 'H7':4, 'G8':2, 'H8':0}
    ASIC_ch_to_SiPM_ch_Broadcom_S4N44P164M = {63: 'A1', 61: 'B1', 59: 'A2', 57: 'B2', 55: 'A3', 53: 'B3', 51: 'A4', 49: 'B4', 47: 'D8', 45: 'C8', 43: 'D7', 41: 'C7', 39: 'D6', 37: 'C6', 35: 'D5', 33: 'C5', 31: 'E1', 29: 'F1', 27: 'E2', 25: 'F2', 23: 'E3', 21: 'F3', 19: 'E4', 17: 'F4', 15: 'E5', 13: 'F5', 11: 'E6', 9: 'F6', 7: 'E7', 5: 'F7', 3: 'E8', 1: 'F8', 62: 'C1', 60: 'D1', 58: 'C2', 56: 'D2', 54: 'C3', 52: 'D3', 50: 'C4', 48: 'D4', 46: 'A5', 44: 'B5', 42: 'A6', 40: 'B6', 38: 'B8', 36: 'A8', 34: 'B7', 32: 'A7', 30: 'G1', 28: 'G2', 26: 'G3', 24: 'G4', 22: 'H1', 20: 'H2', 18: 'H3', 16: 'H4', 14: 'G5', 12: 'H5', 10: 'G6', 8: 'H6', 6: 'G7', 4: 'H7', 2: 'G8', 0: 'H8'}
    


def get_SiPM_ch(ASIC_ch_list, SiPM_model):
    if isinstance(ASIC_ch_list, list):
        SiPM_ch_list = []
        for ASIC_ch in ASIC_ch_list:
            assert ASIC_ch >= 0
            assert ASIC_ch <= 63

            if SiPM_model == 'Hamamatsu_S13361_6597':
                SiPM_ch = SIPM_CHANNEL_MAP.ASIC_ch_to_SiPM_ch_Hamamatsu_S13361_6597[ASIC_ch]
            elif SiPM_model == 'Broadcom_S4N44P164M':
                SiPM_ch = SIPM_CHANNEL_MAP.ASIC_ch_to_SiPM_ch_Broadcom_S4N44P164M[ASIC_ch]
            else:
                print(SiPM_model, ' is not known ! Assuming  SiPM_ch = ASIC_ch ')
                SiPM_ch = ASIC_ch

            if SiPM_ch == None:
                pass
                #print("ASIC_ch %d is not connected to any SiPM_ch !" % ASIC_ch)
            else:
                SiPM_ch_list.append(SiPM_ch)
        return SiPM_ch_list

    elif isinstance(ASIC_ch_list, int):
        assert ASIC_ch_list >= 0
        assert ASIC_ch_list <= 63

        if SiPM_model == 'Hamamatsu_S13361_6597':
            SiPM_ch = SIPM_CHANNEL_MAP.ASIC_ch_to_SiPM_ch_Hamamatsu_S13361_6597[ASIC_ch_list]
        elif SiPM_model == 'Broadcom_S4N44P164M':
            SiPM_ch = SIPM_CHANNEL_MAP.ASIC_ch_to_SiPM_ch_Broadcom_S4N44P164M[ASIC_ch_list]
        else:
            print(SiPM_model, ' is not known !')
            exit()

        if SiPM_ch == None:
            print("Warning: ASIC_ch %d is not connected to any SiPM_ch !" % ASIC_ch_list)
            # exit()
        return SiPM_ch

    else:
        print("Wrong input format arg SiPM_ch_list")


def get_ASIC_ch(SiPM_ch_list, SiPM_model):
    if isinstance(SiPM_ch_list, list):
        ASIC_ch_list = []
        for SiPM_ch in SiPM_ch_list:
            if SiPM_model == 'Hamamatsu_S13361_6597':
                # assert SiPM_ch > 0
                # assert SiPM_ch < 62
                if SiPM_ch in SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Hamamatsu_S13361_6597.keys():
                    ASIC_ch_list.append(SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Hamamatsu_S13361_6597[SiPM_ch])
                else:
                    print(SiPM_ch, ' is not mapped to any ASIC channel !')
                    exit()
            elif SiPM_model == 'Broadcom_S4N44P164M':
                if SiPM_ch in SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Broadcom_S4N44P164M.keys():
                    ASIC_ch_list.append(SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Broadcom_S4N44P164M[SiPM_ch])
                else:
                    print(SiPM_ch, ' is not mapped to any ASIC channel !')
                    exit()
            else:
                print(SiPM_model, ' is not known ! Assuming ASIC_ch = SiPM_ch')
                ASIC_ch_list.append(SiPM_ch)

        return ASIC_ch_list
    elif isinstance(SiPM_ch_list, int):
        if SiPM_model == 'Hamamatsu_S13361_6597':
            # assert SiPM_ch > 0
            # assert SiPM_ch < 62
            if SiPM_ch_list in SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Hamamatsu_S13361_6597.keys():
                return SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Hamamatsu_S13361_6597[SiPM_ch_list]
            else:
                print(SiPM_ch_list, ' is not mapped to any ASIC channel !')
                exit()

        elif SiPM_model == 'Broadcom_S4N44P164M':
            if SiPM_ch_list in SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Broadcom_S4N44P164M.keys():
                return SIPM_CHANNEL_MAP.SiPM_ch_to_ASIC_ch_Broadcom_S4N44P164M[SiPM_ch_list]
            else:
                print(SiPM_ch_list, ' is not mapped to any ASIC channel !')
                exit()
        else:
            print(SiPM_model, ' is not known !')
            exit()
    else:
        print("Wrong input format arg SiPM_ch_list")