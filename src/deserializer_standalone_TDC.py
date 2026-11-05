import os

import pandas as pd
from termcolor import colored
import src.CONSTANTS

class deserializer_standalone_TDC:

    def __init__(self, dev):
        self.dev = dev

    def reset_fifo_standalone_TDC(self):
        # reset FPGA FIFO when changing mode
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_rst, 1)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_test_tdc_rst, 0)


    def extract_data_standalone_tdc(self, N, csv_file, delay, temperature):
        # append data to existing data in csv_file

        # check fifo is not empty
        count = self.get_number_of_events_in_FIFO_stdalone_tdc()

        if count != 0:
            # read fifo
            frame = self.dev.read_words(src.CONSTANTS.REGISTERS.addr_test_tdc_data, N * 7)  # 7 bytes per event stored in fifo

            # decode
            if not self.decode_standalone_tdc_data(frame, csv_file, delay, temperature):
                print("Fail to decode")
                return False

        else:
            print("Fifo for standalone TDC is empty !")
            return False

        return True

    def decode_standalone_tdc_data(self, frame: bytes, csv_file: str, delay: int, temperature: int):

        nb_bytes_per_frame = 7
        events_number = len(frame) // nb_bytes_per_frame
        if delay is None:
            res = {'frame': [], 'temperature': [], 'iter': [], 'TOAcoarse': [], 'TOAfine': [], 'CALcoarse': [],
                   'CALfine': [],
                   'CPT': []}
        else:
            res = {'frame': [], 'delay': [], 'temperature': [], 'iter': [], 'TOAcoarse': [], 'TOAfine': [],
                   'CALcoarse': [],
                   'CALfine': [], 'CPT': []}
        # super coarse digital counter to add !! todo

        if events_number != len(frame) / nb_bytes_per_frame:
            print("number of bytes in frame is not a multiple of 3")
            return False

        for i in range(events_number):
            event_frame = frame[i * nb_bytes_per_frame:(i + 1) * nb_bytes_per_frame]
            event_frame = int.from_bytes(event_frame, byteorder='big')

            res['frame'].append(event_frame)
            res['CPT'].append((event_frame & 0xff_ff_ff_ff_00_00_00) >> (3 * 8))
            # first 4 bytes
            # FPGA firmware can handle 5*8 bits

            padding_bits = (event_frame & (0b1111_1100 << (2*8))) >> (2*8+2)
            if padding_bits!=0:
                debug = bin(event_frame)
                print(debug[2:4 * 8] + colored(debug[4 * 8:5 * 8 + 6], 'green') + debug[5 * 8 + 6:] + "len = %d" % len(
                    debug))
                pass
            assert padding_bits == 0

            event_frame = format(event_frame & 0xff_ff_ff, '018b')
            # last 3 bytes + cut from 24 to 18 bits

            res['iter'].append(i)
            if delay is not None:
                res['delay'].append(delay)
            res['temperature'].append(temperature)

            res['TOAfine'].append(int(event_frame[0:5], 2))
            res['TOAcoarse'].append(int(event_frame[5:5 + 4], 2))
            res['CALfine'].append(int(event_frame[5 + 4: 5 + 4 + 5], 2))
            res['CALcoarse'].append(int(event_frame[5 + 4 + 5: 5 + 4 + 5 + 4], 2))

        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df = pd.concat([df, pd.DataFrame(res)])
        else:
            df = pd.DataFrame(res)
        df.to_csv(csv_file, index=False)
        return True


    def decode_data_py(self, asic, frame_binary_str, csv_file=None):

        res = {'channel': [],
               'ADC_LG': [], 'TOAcoarse_LG': [], 'TOAfine_LG': [], 'CALcoarse_LG': [], 'CALfine_LG': [], 'CPT_LG': [],
               'ADC_HG': [], 'TOAcoarse_HG': [], 'TOAfine_HG': [], 'CALcoarse_HG': [], 'CALfine_HG': [], 'CPT_HG': []}

        if asic.interface.select.dig_modeRO.RO_code == 15:
            header = frame_binary_str[0:4]
            global_counter = frame_binary_str[4:14]
            footer = frame_binary_str[14 + 64 * 16:]

            for i in range(16):
                start = 14 + 64 * i
                channel_frame = frame_binary_str[start:start + 64]

                res['channel'].append(i)
                for g, gain in enumerate(['HG', 'LG']):
                    start = 32 * g
                    res['ADC_' + gain].append(int(channel_frame[start:start + 10], 2))
                    res['TOAfine_' + gain].append(int(channel_frame[start + 10:start + 10 + 5], 2))
                    res['TOAcoarse_' + gain].append(int(channel_frame[start + 10 + 5:start + 10 + 5 + 4], 2))
                    res['CALfine_' + gain].append(int(channel_frame[start + 10 + 5 + 4:start + 10 + 5 + 4 + 5], 2))
                    res['CALcoarse_' + gain].append(
                        int(channel_frame[start + 10 + 5 + 4 + 5:start + 10 + 5 + 4 + 5 + 4], 2))
                    res['CPT_' + gain].append(int(channel_frame[start + 28:start + 32], 2))

        df = pd.DataFrame(res)
        if csv_file:
            df.to_csv(csv_file)
        return df

    def test_decode_frame_py(self):

        df = self.decode_data_py(15,
                                 "1001000000000100100010011001100110011110010011000101100110011001100111100100110010001001100100011001111001001100010110011001000110011110010011001000100110010001100110100100110001011001100100011001101001001100100010011001000110011010010011000101100110010001100110100100110010001001100010011001011001001100010110011000100110010110010011000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000110")
        for g, gain in enumerate(['LG', 'HG']):
            df['TOA_' + gain] = df['TOAfine_' + gain] + 31 * df['TOAcoarse_' + gain]
            df['CAL_' + gain] = df['CALfine_' + gain] + 31 * df['CALcoarse_' + gain]
            df['N_' + gain] = df['CAL_' + gain] - df['TOA_' + gain]
            df['lsb_fromCAL_' + gain] = 2 * 3125 / df['N_' + gain]
            df['TOA_ns_' + gain] = df['TOA_' + gain] * df['lsb_fromCAL_' + gain] / 1e3

