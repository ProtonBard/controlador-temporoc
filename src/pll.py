import os
import re
import subprocess
import time
from typing import List
import src.CONSTANTS
    
class PLL:
    def __init__(self, dev, deserializer_list):
        self.dev = dev
        self.deserializer_list = deserializer_list
        self.delay = 0.001

    def set_pll_rstb(self, value_1b):
        # read back
        length = 1
        offset = src.CONSTANTS.REGISTERS.pll_rstb
        old_val = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_tpr_status_2)

        # write new bit(s) : keep old bits, add new bits
        mask = (~(((2 ** length) - 1) << offset) & 0xff)
        new_val = (old_val & mask) | (value_1b << offset)
        self.dev.write_word(src.CONSTANTS.REGISTERS.addr_tpr_status_2, new_val)

    def soft_rstb(self):
        self.write_PLL(0x001E06)
        self.write_PLL(0x001E00)

    def pll_rstb(self):
        self.set_pll_rstb(0)
        self.set_pll_rstb(1)

    def write_PLL(self, data):
        data = data.to_bytes(4, byteorder="little")
        self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, data, 4)

    def read_PLL(self, page_address, printAnswer=False):

        read_opcode = 0xff
        page_add = (page_address & 0xffff00) >> 8
        data = (page_address | (read_opcode << 24)).to_bytes(4, byteorder="little")
        expected_data = page_address & 0xff
        self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, data, 4)
        time.sleep(self.delay)  # time delay required otherwise source of USB error
        read_data = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_pll_spi_data)
        if printAnswer:
            print("PLL reg at page_add 0x%4x : read_data = 0x%2x expected_data = 0x%2x" % (page_add, read_data, expected_data))
        return read_data

    def read_PLL_register(self, page, add, printAnswer=False):
        # 0 as expected answer
        return self.read_PLL((page << 16) + (add << 8), printAnswer=printAnswer)


    def flashtest(self):
        # self.set_pll_rstb(0)  # reset
        # time.sleep(0.1)
        self.set_pll_rstb(1)  # remove pll reset
        # time.sleep(0.2)
        self.write_PLL(0x0017AC)
        self.read_PLL(0x0017AC)
        time.sleep(0.2)
        #
        tmp_data = 0x0B24C0
        # tmp_data = 0x001CFF soft reset
        tmp_data = 0x001E02

        # self.write_PLL(0x0B2500)

        # self.write_PLL(0x001E02) # hard reset
        # time.sleep(0.5)
        # self.write_PLL(0x001E00)  # hard reset back to normal
        # time.sleep(0.5)


        # self.write_PLL(0x054000)
        # self.write_PLL(0x0B24C3)
        # self.write_PLL(0x0B2502)
        # time.sleep(0.5)
        # self.write_PLL(0x0B24C0)
        # self.write_PLL(0x0B2500)
        # self.write_PLL(0x054001)
        # time.sleep(0.5)





        # SPI_PLL_FIFO_byte_count = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_pll_spi_count)
        # print("Number of bytes stored in FIFO for SPI com (multiple of 4): %d"%SPI_PLL_FIFO_byte_count)

    def read_config_file(self, config_file):
        # with preamble needed in file
        preamble: List[int] = []
        registers: List[int] = []
        postamble: List[int] = []

        with open(config_file, "r", encoding="ascii") as f:
            line = f.readline()
            assert line == "Address,Data\n"
            line = f.readline()
            assert line == "# \n"
            line = f.readline()
            assert line == "# Start configuration preamble\n"
            line = f.readline()
            preamble.append(self.parse_line(line))
            line = f.readline()
            preamble.append(self.parse_line(line))
            line = f.readline()
            preamble.append(self.parse_line(line))
            line = f.readline()
            assert line == "# End configuration preamble\n"
            line = f.readline()
            assert line == "# \n"
            line = f.readline()
            assert line == "# Delay 300 msec\n"
            line = f.readline()
            assert line == "#    Delay is worst case time for device to complete any calibration\n"
            line = f.readline()
            assert line == "#    that is running due to device state change previous to this script\n"
            line = f.readline()
            assert line == "#    being processed.\n"
            line = f.readline()
            assert line == "# \n"
            line = f.readline()
            assert line == "# Start configuration registers\n"
            line = f.readline()
            while line != "# End configuration registers\n":
                registers.append(self.parse_line(line))
                line = f.readline()
            # line = f.readline()
            # assert line == "# End configuration registers\n"
            line = f.readline()
            assert line == "# \n"
            line = f.readline()
            assert line == "# Start configuration postamble\n"
            line = f.readline()
            postamble.append(self.parse_line(line))
            line = f.readline()
            postamble.append(self.parse_line(line))
            line = f.readline()
            postamble.append(self.parse_line(line))
            line = f.readline()
            postamble.append(self.parse_line(line))
            line = f.readline()
            postamble.append(self.parse_line(line))
            line = f.readline()
            assert line == "# End configuration postamble\n"
            line = f.readline()
            assert line == ""
            pass
        return preamble, registers, postamble

    def write_list_register(self, preamble):

        for i in range(0, len(preamble)):
            data = preamble[i].to_bytes(4, byteorder="little")
            self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, data, 4)
            time.sleep(self.delay)  # time delay required otherwise source of USB error
            # print("Preamble : " + str(i) + " / " + str(len(preamble) - 1) + " %06x"% preamble[i])
            pass
        # patch due to clock builder behaviour change between version 4.12 and 4.13


    def flash(self, config_file, tempo_dig_clock=320, force_flash=False) -> int:

        if 'tdc_ck' in config_file:
            tempo_dig_clock = int(float(re.findall("(?<=tdc_ck_)[0-9]+[.]?[0-9]+", config_file)[0]) / 1e6)
        for deserializer in self.deserializer_list:
            deserializer.set_frequency(tempo_dig_clock)
        self.dig_clock_freq = tempo_dig_clock

        preamble, registers, postamble = self.read_config_file(config_file)

        self.set_pll_rstb(1)  # remove pll reset
        time.sleep(0.01)
        self.write_PLL(0x002b02) # force 4 wire SPI communication when reading
        if self.check_if_PLL_reprogramming_is_not_needed(config_file):
            print("PLL configuration already up-to-date : %s" % config_file)
            return 1
        else:
            self.set_pll_rstb(0)  # reset pll
            self.set_pll_rstb(1)  # remove pll reset
        time.sleep(0.3)

        self.write_list_register(preamble)
        time.sleep(0.3)  # time delay required by PLL
        self.write_list_register(registers)
        self.write_list_register(postamble)
        time.sleep(0.05)

        # check value written
        read_opcode = 0xff
        # return 1
        for i in range(0, len(registers)):
            data = (registers[i] | (read_opcode << 24)).to_bytes(4, byteorder="little")
            page_add = (registers[i] & 0xffff00) >> 8
            expected_data = registers[i] & 0xff
            self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, data, 4)
            time.sleep(self.delay)  # time delay required otherwise source of USB error
            read_data = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_pll_spi_data)
            time.sleep(self.delay)  # time delay required otherwise source of USB error

            # print(
            #     "PLL reg %d at page_add 0x%4x : read_data = 0x%2x expected_data = 0x%2x" % (
            #         i, page_add, read_data, expected_data))
            if read_data != expected_data:
                # if i == 524 or i == 525:
                #     # normal if different
                #     # write only post-amble register (self clear registers)
                #     pass
                # else:
                print("PLL reg %d at page_add 0x%4x : read_data = 0x%2x does not match expected_data = 0x%2x" % (
                        i, page_add, read_data, expected_data))
                if read_data != expected_data:
                    pass
                        # raise Exception("PLL configuration failed: returned data does not match with written.")
        print("PLL configuration %s loaded" % config_file)
        print("   Last modified on %s"%(time.ctime(os.path.getmtime(config_file))))

        # for fimware 2025_06_19_15_00
        # SPI_PLL_FIFO_byte_count = self.dev.read_word(src.CONSTANTS.REGISTERS.addr_pll_spi_count)
        # print("Number of bytes stored in FIFO for SPI com (multiple of 4): %d"%SPI_PLL_FIFO_byte_count)

        return 1

    def check_if_PLL_reprogramming_is_not_needed(self, config_file):
        PLL_config_ID = re.findall("(?<=Si5345_)[0-9a-zA-Z]+", config_file)[0]
        return self.get_PLL_design_ID() == PLL_config_ID

    def flash_PLL_Si5345(self, config_file):
        # copy existing python and fw from adele
        # FPGA should feed a 100M from on-board crystal to the Si5345 PLL as reference clock on IN0
    
        # config_file should not include preamble and postamble
        with open(config_file, "r", encoding="ascii") as f:
            t = f.readlines()[1:]  # skip first header line = Address,Data\n
        fifo_pll = []
        for line in t:
            ret = line.split(",")
            fifo_pll.append(
                0)  # temporisation byte to let the fw select the next register to write storing the page (ie MSB of the address)
            fifo_pll.append(int(ret[0][2:4], 16))
            fifo_pll.append(int(ret[0][4:6], 16))
            fifo_pll.append(int(ret[1][2:4], 16))
    
        # reset fifo needed ?
    
        preamble = [0x00, 0x0B, 0x24, 0xC0,
                    0x00, 0x0B, 0x25, 0x00,
                    0x00, 0x05, 0x40, 0x01]
        self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, bytes(preamble), len(preamble))
        time.sleep(0.3)  # 300 ms
    
        numberMaxBytesSentPerWriteWordsFunctionCalls = 256
        for i in range(len(fifo_pll) // numberMaxBytesSentPerWriteWordsFunctionCalls + 1):
            data = bytes(fifo_pll[256 * i:256 * (i + 1)])
            # print(len(data), data)
            self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, data, len(data))
    
        postamble = [0x00, 0x05, 0x14, 0x01,
                     0x00, 0x00, 0x1C, 0x01,
                     0x00, 0x05, 0x40, 0x00,
                     0x00, 0x0B, 0x24, 0xC3,
                     0x00, 0x0B, 0x25, 0x02]
        self.dev.write_words(src.CONSTANTS.REGISTERS.addr_pll_spi_data, bytes(postamble), len(postamble))
    
        print("PLL configuration %s loaded" % config_file)
            
            
    def configure_PLL_no_clocks_except_FPGA(self):
        self.flash("../config/PLL/Si5345_0-Registers.txt")
        # PLL outputs
        # 0 : FPGA clock : OFF
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : off
        # 7 : standalone TDC ck : off
        # 8 : external hit : off



    def configure_with_default_behaviour(self, mode, tempo_dig_ck_freq):
        self.flash("../config/PLL/Si5345_11%s_ck_%dMHz-Registers.txt" % (mode, tempo_dig_ck_freq),
                        tempo_dig_clock=tempo_dig_ck_freq)
        # PLL outputs
        # 0 : FPGA clock : 80M
        external_hit = 80e6
        # 3 : FPGA clock : 80M # What is the impact of the clock duty cycle deformation passing through the FPGA ?)
        # 6 : TEMPOROC digital : 80M (variable)
        # 7 : external hit resync CK : 320M
        # 8 : standalone TDC ck : OFF

        # Expected PLL inputs
        # IN0 : 100M from cristal if MASTER
        #     :  80M from MASTER FPGA is SLAVE

        return tempo_dig_ck_freq, external_hit

    def configure_PLL_40M_dig_ck(self):
        tempo_dig_clock = 40
        external_hit = 40e6
        self.flash("../config/PLL/Si5345_11-Registers.txt", tempo_dig_clock)
        # PLL outputs
        # 0 : FPGA clock : 80M
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 40M
        # 7 : external hit : 40M
        # 8 : standalone TDC ck : OFF
        return tempo_dig_clock, external_hit
    
    
    def configure_PLL_dig_ck_for_code_density(self, tempo_dig_clock_freq, force_flash_PLL=True):

        if tempo_dig_clock_freq == 40:
            self.flash("../config/PLL/Si5345_14-Registers.txt", tempo_dig_clock_freq, force_flash=force_flash_PLL)
            # PLL outputs
            # 0 : FPGA clock : 2*OUT7
            # 3 : FPGA clock : 320M
            # 6 : TEMPOROC digital : 40M
            # 7 : external hit : 1 506 810
            # 8 : standalone TDC ck : OFF

        elif tempo_dig_clock_freq == 160:
            external_hit_freq = 753405
            self.flash("../config/PLL/Si5345_13-Registers.txt", tempo_dig_clock_freq, force_flash=force_flash_PLL)
            # PLL outputs
            # 0 : FPGA clock : 753 405
            # 3 : FPGA clock : 320M
            # 6 : TEMPOROC digital : 160M
            # 7 : external hit : 753 405
            # 8 : standalone TDC ck : OFF

        elif (tempo_dig_clock_freq == 320) | (tempo_dig_clock_freq == 80):

            external_hit_freq = 753405

            self.flash("../config/PLL/Si5345_30%s_ck_%dMHz-Registers.txt" % ('master', tempo_dig_clock_freq),
                       tempo_dig_clock=tempo_dig_clock_freq, force_flash=force_flash_PLL)
            # PLL outputs
            # 0 : FPGA clock : 753 405
            # 3 : FPGA clock : 80M
            # 6 : TEMPOROC digital : 80M
            # 7 : external hit resync CK : =OUT0
            # 8 : standalone TDC ck : OFF

        else:
            print("%d MHz clock frequency not allowed " % tempo_dig_clock_freq)
            exit(0)

        if tempo_dig_clock_freq == 40:
            external_hit_freq = 1506810  # todo
        elif tempo_dig_clock_freq == 160:
            external_hit_freq = 753405
        elif (tempo_dig_clock_freq == 320) | (tempo_dig_clock_freq == 80):
            external_hit_freq = 753405
        else:
            print("%d MHz clock frequency not allowed " % tempo_dig_clock_freq)
            exit(0)
        return external_hit_freq
    
    
    def configure_PLL_160M_dig_ck(self):
        self.flash("../config/PLL/Si5345_12-Registers.txt")
        # PLL outputs
        # 0 : FPGA clock : 80M
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 160M
        # 7 : external hit : 160M
        # 8 : standalone TDC ck : OFF
        tempo_dig_clock = 160
        external_hit = 160e6
        return tempo_dig_clock, external_hit
    
    
    def configure_PLL_sync_ext_trigger(self):
        # PLL outputs
        # 0 : FPGA clock : 80M          Y3/AA3 (bank 34)
        # 3 : FPGA clock : 320M          T4/R4 (bank 34)
        # 6 : TEMPOROC digital : 320M
        # 7 : external hit : 80M
        # 8 : standalone TDC ck : 320M
        # 9 : fb ck : None because otherwise receives LOS & OOF from PLL todo
    
        self.flash("../config/PLL/Si5345_2-Registers.txt")
        # self.flash_PLL_Si5345_alternative("../config/PLL/Si5345_2-Registers.txt")
        # self.flash_PLL_Si5345("../config/PLL/Si5345_2-Registers.txt")
        tempo_dig_clock = 320
        external_hit = 80e6
        return tempo_dig_clock, external_hit
    
    
    def configure_PLL_async_ext_trigger(self):
        self.flash("../config/PLL/Si5345_4-Registers.txt")
        # PLL outputs
        # 0 : FPGA clock : 8 000 128 Hz (= #8/2)
        # 3 : FPGA clock : 320M
        # 6 : TEMPOROC digital : 320M
        # 7 : external hit : 16 000 256 Hz
        # 8 : standalone TDC ck : 320M
        tempo_dig_clock = 320
        external_hit = 8000128
        return tempo_dig_clock, external_hit
    
    def get_PLL_design_ID(self):
        design_ID = ''
        page = (0x02 << 16)
        first_register_address = (0x6b << 8)
        page_address_first_reg = page + first_register_address

        for i in range(8):
            byte_result = self.read_PLL(page_address_first_reg + (i<<8))
            if (byte_result < 0) | (byte_result >= 128):
                # Unexpected result
                print("non ascii byte read from PLL register 0x" + hex(byte_result)+" Reboot board.")
                exit(0)
            design_ID += chr(byte_result)
        return design_ID
        # ord('a') to convert ascii char to int
        # see page 147 https://twiki.nevis.columbia.edu/twiki/pub/ATLAS/AnalogTestboard/Si5345-44-42-D-RM.pdf

    def set_clk(self, frequency):
        fp = "./config/PLL/"
        with open(fp + "edits.txt", 'w+') as f:
            f.write("Clock,State,Frequency\nOUT0,Enabled," + str(frequency) + " MHz")
        self.run_command(
            "CBProProjectEdit --edit-file " + fp + "edits.txt --in-project " + fp + "in.slabtimeproj --out-project " + fp + "out.slabtimeproj")
        self.run_command(
            "CBProProjectRegistersExport --format csv --project " + fp + "out.slabtimeproj --outfile " + fp + "out.txt")  # --include-load-writes")
        return self.flash_PLL_Si5345(fp + "out.txt")

    def run_command(command):
        try:
            result = subprocess.run(command, capture_output=True, text=True, shell=True, check=True)
            output = result.stdout
            return output
        except subprocess.CalledProcessError as e:
            print("Error executing command:", e)
            return None

    def flash_PLL_Si5345_alternative(self, config_file):

        # config_file should not include preamble and postamble
        try:
            with open(config_file) as f:
                t = f.readlines()[1:]  # skip first header line
            fifo_pll = []
            for line in t:
                ret = line.split(",")
                fifo_pll.append(
                    0)  # temporisation byte to let the fw select the next register to write storing the page (ie MSB of the address)
                fifo_pll.append(int(ret[0][2:4], 16))
                fifo_pll.append(int(ret[0][4:6], 16))
                fifo_pll.append(int(ret[1][2:4], 16))

            # reset fifo needed ?

            preamble = [0x00, 0x0B, 0x24, 0xC0,
                        0x00, 0x0B, 0x25, 0x00,
                        0x00, 0x05, 0x40, 0x01]
            for i, word in enumerate(preamble):
                # self.dev.write_word(src.CONSTANTS.REGISTERS.addr_pll_spi_data, format(word, '#010b'))
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_pll_spi_data, word)
                # time.sleep(0.01)

            time.sleep(0.3)  # 300 ms required by the PLL

            for i, word in enumerate(fifo_pll):
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_pll_spi_data, word)
                time.sleep(0.01)

            postamble = [0x00, 0x05, 0x14, 0x01,
                         0x00, 0x00, 0x1C, 0x01,
                         0x00, 0x05, 0x40, 0x00,
                         0x00, 0x0B, 0x24, 0xC3,
                         0x00, 0x0B, 0x25, 0x02]

            for i, word in enumerate(postamble):
                self.dev.write_word(src.CONSTANTS.REGISTERS.addr_pll_spi_data, word)
                # time.sleep(0.01)
            print("config PLL over ")
            return True
        except:
            return False

    def parse_line(self, line: str) -> int:
        line = line.replace("\n", "")  # remove the \n character
        parts = line.split(",")
        if len(parts) != 2:
            raise ValueError("Bad formatting of a pll configuration line : " + line)
        addr = int(parts[0], 16) << 8
        data = int(parts[1], 16) << 0
        cmd = addr | data
        return cmd

    def check_is_locked(self):

        status = True
        reg1 = self.read_PLL_register(0, 0x0c)
        if (reg1 & 0b101011) != 0:
            status = False
            if reg1 & 0b1:
                print("PLL is calibrating !")
            if reg1 & 0b10:
                print("PLL has no signal on XAXB pins (crystal) !")
            if reg1 & 0b1000:
                print("48MHz PLL crystal is not locked !")
            if reg1 & (1<<5):
                print("SMBBus timeout error !")


        reg2 = self.read_PLL_register(0, 0x0d)
        if reg2 != 0:
            status = False
            for i in range(4):
                if reg2 & (1 << i):
                    print("Clock input %d has LOS (Loss Of Signal) !" % i)
                if reg2 & (1 << (i+4)):
                    print("Clock input %d is OOF (Out Of Frequency) compared to plan !" % i)

        if status==False:
            pass

        return status