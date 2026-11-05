import ctypes
import re
import sys
import threading

import src.CONSTANTS

from src.ASIC.asic import asic


class ASIC_deserializer:

    def __init__(self, dev, asic:asic):
        self.dev = dev
        self.asic = asic
        # FPGA default
        self.deser_freq = 0 # FPGA deserialiser
        self.dig_clock_freq = 320 # MHz
        self.decodeLib = None
        self.decodeLibName = 'temdec_2026_05_12_16_40'  # 'temdec_2026_05_07_15_20' #without realigner

        self.load_decode_frame_dll()
        self.filter = self.deserializer_filter(self.dev)
        self.__csv_file_lock = threading.Lock()

    def load_decode_frame_dll(self):
        if sys.platform == "win32":  # check only if windows but not if it's a 32-bit or 64-bits plateform
            self.decodeLib = ctypes.cdll.LoadLibrary("../src/"+self.decodeLibName+".dll") # take all frames at once
            self.decodeLib.temdec_decode.restype = ctypes.c_uint
            self.decodeLib.temdec_decode.argtypes = ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(
                ctypes.c_uint8), ctypes.c_uint32, ctypes.c_char_p

            # # self.decodeLib.temdec_debug_add.restype = ctypes.c_void_p
            # self.decodeLib.temdec_debug_add.argtypes = ctypes.c_uint,
            #
            # self.decodeLib.temdec_debug_decode.restype = ctypes.c_uint
            # self.decodeLib.temdec_debug_decode.argtypes = ctypes.c_uint,
            #
            # self.decodeLib.temdec_debug_clear()
            # for i in range(len(frame_bytes)):
            #
            #     self.decodeLib.temdec_debug_add(frame_bytes[i])

            # print(self.decodeLib.temdec_debug_decode(ctypes.c_uint(15)))

        else:  # linux
            self.decodeLib = ctypes.cdll.LoadLibrary("../src/"+self.decodeLibName+".so")
            print("DLL call for linux was not tested! ")

    def decode_data_cpp(self, RO_code, frame, csv_file, flag):

        # status = self.decodeLib.temdec_decode(ctypes.c_uint(RO_code), ctypes.c_uint(len(frame)), frame, csv_file.encode())

        # threading produces errors in output file (number of columns not constant)
        # x = threading.Thread(target = self.decodeLib.temdec_decode, args = (ctypes.c_uint(RO_code), ctypes.c_uint(len(frame)), frame, csv_file.encode()))
        # x.start()

        # Using semphore
        self.__csv_file_lock.acquire(timeout=10)
        try:
            self.decodeLib.temdec_decode(ctypes.c_uint(RO_code), ctypes.c_uint(len(frame)), frame, flag, csv_file.encode())
        finally:
            self.__csv_file_lock.release()

        # https://www.bestdivision.com/questions/what-is-the-use-of-the-ctypespointer-module-in-python
        # https://docs.python.org/3/library/ctypes.html#ctypes.pointer
        # https://www.f-legrand.fr/scidoc/docmml/langages/python/libC/libC.html

    def test_decode_data_cpp(self):

        # build frame from simulation data
        payload = "1001000000000100100010011001100110011110010011000101100110011001100111100100110010001001100100011001111001001100010110011001000110011110010011001000100110010001100110100100110001011001100100011001101001001100100010011001000110011010010011000101100110010001100110100100110010001001100010011001011001001100010110011000100110010110010011000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000001001110000000000000000000000000010011100000000000000000000000000100111000000000000000000000000110"
        payload = '0' * (8 - len(payload) % 8) + payload
        marker = 0x55
        payload_length_in_bytes = len(payload) // 8
        frame_length_in_bytes = payload_length_in_bytes + 7

        frame = (ctypes.c_uint8 * frame_length_in_bytes)()
        frame[0] = marker
        frame[1] = frame_length_in_bytes
        frame[2] = marker

        frame[-1] = marker
        frame[-2] = 0  # global time
        frame[-3] = 0  # global time
        frame[-4] = marker
        # https://stackoverflow.com/questions/72984236/passing-pointers-to-dll-function-with-ctypes

        for i in range(payload_length_in_bytes):
            a = int(payload[i * 8:(i + 1) * 8], 2)
            frame[i + 3] = a

        self.modeRO = 1  # 15 in temporoc digital  full
        file = './csv_file_max.csv'

        self.decode_data_cpp(frame, file)

    def set_frequency(self, freq_MHz) -> None:
        if freq_MHz == 320:
            self.deser_freq = 0
        elif freq_MHz == 160:
            self.deser_freq = 1
        elif freq_MHz == 80:
            self.deser_freq = 2
        elif freq_MHz == 40:
            self.deser_freq = 3
        else:
            print("Wrong deserialiser frequency")
            return
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, (val & 0b1111_0011) | (self.deser_freq << 2))

    def reset(self) -> None:
        # deserialiser :
        # 1) flushed while closed
        # 2) not flushed (not under reset) while still closed
        # 3) not flushed (not under reset) and OPEN to receive new events !
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, (val & 0b1111_1100) | 0b10)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, (val & 0b1111_1100) | 0b00)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, (val & 0b1111_1100) | 0b01)
        return

    def reset_then_leave_closed(self):
        # deserialiser :
        # 1) flushed while closed
        # 2) not flushed (not under reset) while still CLOSED (not accepting new events)
        val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, (val & 0b1111_1100) | 0b10)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, (val & 0b1111_1100) | 0b00)

    def reset_fifo_for_all_cluster(self):
        byte_count = ()
        self.reset()
        for cluster in range(4):
            byte_count = (*byte_count, self.get_number_of_bytes_in_fifo(cluster))
        return byte_count

    def get_number_of_bytes_in_fifo(self, cluster: int) -> int:
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster <= 3

        addr_count_msb: int = src.CONSTANTS.REGISTERS.addr_deser_base + (
                    src.CONSTANTS.REGISTERS.addr_deser_size * cluster) + src.CONSTANTS.REGISTERS.addr_deser_count_high
        addr_count_lsb: int = src.CONSTANTS.REGISTERS.addr_deser_base + (
                    src.CONSTANTS.REGISTERS.addr_deser_size * cluster) + src.CONSTANTS.REGISTERS.addr_deser_count_low
        count_msb: int = self.dev.read_word(addr_count_msb)
        count_lsb: int = self.dev.read_word(addr_count_lsb)
        return (count_msb << 8) + count_lsb

    def get_MSB_number_of_bytes_in_fifo(self, cluster: int) -> int:
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster <= 3
        addr_count_msb: int = src.CONSTANTS.REGISTERS.addr_deser_base + (
                src.CONSTANTS.REGISTERS.addr_deser_size * cluster) + src.CONSTANTS.REGISTERS.addr_deser_count_high
        return self.dev.read_word(addr_count_msb)

    def get_number_of_bytes_in_all_FIFO(self):
        number_of_bytes = ()
        for cluster in range(4):
            count = self.get_number_of_bytes_in_fifo(cluster)
            # print(msb_add, lsb_add)
            number_of_bytes = (*number_of_bytes, count)
        return number_of_bytes

    def get_number_of_dropped_events_in_FIFO(self, cluster: int) -> int:
        isinstance(cluster, int)
        assert cluster >= 0        
        assert cluster < 4
        return self.dev.read_word(
            src.CONSTANTS.REGISTERS.addr_deseri_start_addr + src.CONSTANTS.REGISTERS.addr_deseri_drop_count + 8 * cluster)

    def get_status(self):
        status = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        print("Deserialisers are :")
        print("\t "+"CLOSED" if (status&1)==0 else "\t open (ready to receive)" )
        if (status & 2) == 2:
            if (status & 1) == 0:
                print("\t " + "under RESET (flush)")
            else:
                print("\t " + "under RESET (flush) : Forbidden when open !")
        else:
            print("\t " + "not under reset")

        deserialiser_ck = (status & 0b1100)>>2
        if deserialiser_ck==0:
            print("\t " + "Expecting 320 MHz")
        elif deserialiser_ck==1:
            print("\t " + "Expecting 160 MHz")
        elif deserialiser_ck==2:
            print("\t " + "Expecting 80 MHz")
        elif deserialiser_ck==3:
            print("\t " + "Expecting 40 MHz")
        else:
            print("\t" + "Wrong clock defined ! ")

        print("\t"+" coincidence mode " if (status&16)==16 else "\t single board (no coincidence)")
        print("\t"+" foreign_reset_enable (slave ?)" if (status&32)==32 else "\t no foreign_reset (because single or master)")
        print("\t"+" charge_filter enabled " if (status&64)==64 else "\t no charge filter")
        print("\t"+" inter_cluster_filter enabled " if (status&128)==128 else "\t no inter_cluster_filter")
        print("\t Byte(s) count for cluster/FIFO (0,1,2,3) = "+str(self.get_number_of_bytes_in_all_FIFO()))

    def close(self):
        pipe_ctrl = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, pipe_ctrl & 0b1111_1110)

    def open(self):
        pipe_ctrl = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, pipe_ctrl | 1)

    def set_time(self, dig_ck_cycles):
        # lsb = 256e-9 # = 4 ns * 64
        # lsb = 512e-9 # = 4 ns * 128 # starting from fw : top_2024_09_27_10_34
        lsb = 256e-9  # = 4 ns * 64 # starting from fw : top_2024_10_02_13_35
        dig_ck_period = 1e-6 / self.dig_clock_freq

        value_11b = round(dig_ck_cycles * dig_ck_period / lsb)
        print("set_time %d = %.1f µs" % (dig_ck_cycles, value_11b * lsb * 1e6))
        assert value_11b >= 0
        assert value_11b < 2 ** 11

        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_time_lsb, value_11b & 0xff)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_time_msb, (value_11b & (3 << 8)) >> 8)

    def extract_all_data(self, cluster_list, csv_file_list, config, debug=False):
        events_extracted_list = []

        if isinstance(cluster_list, int):
            cluster_list = [cluster_list]
        assert len(cluster_list)==len(csv_file_list)

        for i,cluster in enumerate(cluster_list):
            events_extracted = self.__extract_all_data_cluster(cluster, csv_file_list[i], config, debug=debug)
            events_extracted_list.append(events_extracted)

        return events_extracted_list

    def extract_all(self, csv_file_list=None, config=None, debug=False):
        events_extracted_list = []
        self.close()
        for cluster in config['power_cluster'][0]:
            if csv_file_list:
                csv_file = csv_file_list[cluster]
            else:
                csv_file = "../output/cluster_%d.csv"%cluster
            events_extracted = self.__extract_all_data_cluster(cluster, csv_file, config, debug=debug)
            events_extracted_list.append(events_extracted)
        self.open()
        return events_extracted_list

    def __extract_all_data_cluster(self, cluster, csv_file, config, debug):
        bytes_count = self.get_number_of_bytes_in_fifo(cluster)
        expected_bytes_per_event = self.asic.interface.select.dig_modeRO.RObit_count / 8 + 9  # + 9 bytes including 32 bits ovf counter
        # 3 bytes added by FPGA at start to indicate frame size : marker(1byte)+size(1byte)+marker
        # 6 bytes added by FPGA at start to indicate FPGA time : marker(1byte)+timestamp(4bytes)+marker
        events_extracted = round(bytes_count / expected_bytes_per_event)
        if bytes_count > 0:
            cluster_suffix = '_cluster%d' % cluster
            if config:
                config['frame_count' + cluster_suffix][0] += events_extracted
            self.extract_data(bytes_count, cluster, csv_file, debug=debug)
        return events_extracted

    def is_FIFO_empty(self, cluster):
        addr_status: int = src.CONSTANTS.REGISTERS.addr_deser_base + (
                cluster * src.CONSTANTS.REGISTERS.addr_deser_size) + src.CONSTANTS.REGISTERS.addr_deser_status
        status: int = self.dev.read_word(addr_status)
        if (status & 0x02) == 0:
            empty = False
        else:
            empty = True
        return empty
    # bit 1 : empty bit 0 busy


    def extract_data(self, bytes_count_to_extract, cluster, csv_file, debug):
        # fifo source = 1 out of 4 cluster fifo or standalone tdc fifo
        # save data to csv_file
        assert isinstance(cluster, int)
        assert cluster >= 0
        assert cluster <= 3

        # check fifo is not empty


        pipe_ctrl = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
        if (pipe_ctrl & 0x01) == 0:
            # print("The deserialisers are not open. This may be deliberate.")
            pass
        if (pipe_ctrl & 0x02) != 0:
            print("The deserialisers are being flushed. It is nonsense to try and read them in this state.")
            return False

        empty = self.is_FIFO_empty(cluster)
        if empty:
            print("Fifo %d is empty" % cluster)
            return False

        target_register: int = src.CONSTANTS.REGISTERS.addr_deser_base + (
                cluster * src.CONSTANTS.REGISTERS.addr_deser_size) + src.CONSTANTS.REGISTERS.addr_deser_fifo_data

        frame_byte_array = self.dev.read_words(target_register, bytes_count_to_extract+2)
        # +2 to completely empty the pre-reading register of the BRAM, see first-word fall-through (FWFT) fifos
        # otherwise error 99 give non-null number of bytes that could not be decoded by the DLL (gave up) in the 4th index (csv file)


        frame_bytes = bytes(frame_byte_array)

        empty = self.is_FIFO_empty(cluster)
        if not empty:
            print(self.get_number_of_bytes_in_fifo(cluster))

        pointer_to_frame = (ctypes.c_uint8 * len(frame_bytes))()
        for i in range(len(frame_bytes)):
            pointer_to_frame[i] = frame_bytes[i]

        if debug:
            with open(csv_file + '.bytes', "a") as binary_file:
                frame_byte_list = ['{:08b}'.format(int(frame_byte)) for frame_byte in frame_bytes]
                binary_file.write(".".join(frame_byte_list) + "\n")
                binary_file.close()

        RO_code = self.asic.interface.select.dig_modeRO.RO_code
        self.decode_data_cpp(RO_code, pointer_to_frame, csv_file, 0)

    def get_number_of_events_in_FIFO_stdalone_tdc(self):
        count_msb = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_hicn)
        count_lsb = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_test_tdc_locn)
        return ((count_msb << 8) + count_lsb) // 7

    class deserializer_filter:

        def __init__(self, dev):
            self.dev = dev
            self.enable = self.__enable(self.dev)
            self.disable = self.__disable(self.dev)

        class __enable:
            def __init__(self, dev):
                self.dev = dev

            def coincidence_inter_asic(self):
                word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word | (1 << 4))

            def charge(self):
                word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word | (1 << 6))

            def coincidence_inter_cluster(self):
                word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word | (1 << 7))


        class __disable:
            def __init__(self, dev):
                self.dev = dev

            def coincidence_inter_asic(self):
                word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word & ~(1 << 4))

            def charge(self):
                word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word & ~(1 << 6))

            def coincidence_inter_cluster(self):
                word = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_deser_common)
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_deser_common, word & ~(1 << 7))



