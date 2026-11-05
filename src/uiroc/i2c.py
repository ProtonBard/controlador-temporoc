# Standard libraries
from typing import Final
import pathlib
import time
import src.CONSTANTS


# 3rd party packages
import numpy as np  # do not delete, needed in eval()
import pandas as pd
from PyQt6 import QtCore, QtWidgets


# Delay between two usb communications for the sake of setting slow control, in seconds.
SLOW_CONTROL_DELAY : Final[float] = 0.001

class i2c:
    def __init__(self, dev, df_i2c, chip_id):
        self.device = dev
        # Parameters
        assert isinstance(chip_id, int)
        assert chip_id < 8
        assert chip_id >= 0
        self.chipID = chip_id
        self.addLength = 8
        self.subaddLength = 8

        # Global variables
        self.df_i2c = df_i2c

        # SC statistics
        self.nb_reg_to_write = 0
        self.nb_write_operation = 0
        self.SC_warnings = ''
        self.SC_errors = ''

    def SC_stats(self):
        # ideal is 1, bad is above 1, under 1 is not possible
        ratio = self.nb_write_operation/self.nb_reg_to_write
        if ratio<1:
            print('SC errors detected !\n%.2f write operations needed per register to write (after successfully writing %d reg)' % (ratio, self.nb_reg_to_write))
            print('%.2f %% errors'%((self.nb_write_operation-self.nb_reg_to_write)/self.nb_reg_to_write*100))
            print('%d errors'%(self.nb_write_operation-self.nb_reg_to_write))
        return ratio

    def SC_details(self):
        print(self.SC_warnings)
        print(self.SC_errors)

    def enable_I2C_clock(self):
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                              src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, 1)

    def disable_I2C_clock(self):
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status,
                              src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, 0)

    def reset_I2C_slave_state_machine(self):
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status, src.CONSTANTS.REGISTERS.addr_sc_status_bit_resetn_I2C, 0)
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status, src.CONSTANTS.REGISTERS.addr_sc_status_bit_resetn_I2C, 1)

    def get_bits(self, address: int, subaddress: int, bit_offset_lsb: int, bit_size: int) -> int:
        return int("{0:08b}".format(self.get(address, subaddress))[8 - bit_size - bit_offset_lsb:8 - bit_offset_lsb], 2)

    def get(self, address : int, subaddress : int, safer=False) -> int :
        assert isinstance(address,    int)
        assert isinstance(subaddress, int)
        assert address    >=   0
        assert address    <  256
        assert subaddress >=   0
        assert subaddress <  256

        data = self.read_register(address, subaddress)

        if safer: # save to local & compare
            dataOK = self.verify_data([data], self.df_i2c)
            assert dataOK==True

        return data

    def set_bit(self, address : int, subaddress : int, bit_offset_lsb: int, value : int, methodA=True) -> None :
        self.set_bits(address, subaddress, bit_offset_lsb, 1, value, methodA)
        return

    def set_bits(self, address: int, subaddress: int, bit_offset_lsb: int, bit_size: int, value: int, methodA=True) -> None :
        assert isinstance(address, int)
        assert isinstance(subaddress, int)
        assert isinstance(bit_offset_lsb, int)
        assert isinstance(bit_size, int)
        assert isinstance(value, int)
        assert address >= 0
        assert address < 256
        assert subaddress >= 0
        assert subaddress < 256
        assert bit_offset_lsb >= 0
        assert bit_offset_lsb < 8
        assert value >= 0
        assert value < 2**bit_size
        assert bit_size >= 1
        assert bit_size < 9

        if methodA:  # write distant & read distant & compare & retry once if error & print error if any & update local
            old_data = int(self.df_i2c.loc[(self.df_i2c["add"] == address) & (self.df_i2c["subadd"] == subaddress), 'data'].iloc[0],2)
            new_data = (old_data & (~((2**bit_size-1) << bit_offset_lsb) & 0xff)) | (value << bit_offset_lsb)
            if old_data == new_data:  # only check if data in df was correct
                self.write_register(address, subaddress, new_data, check_and_retry=True, skip_write=True,
                                    force_update=True)
            else:
                # print("address: ", address, " subaddr: ", subaddress, " old_data : ", bin(old_data), " value: ",
                #       '0b' + bin(value)[2:].zfill(bit_size), " bit_offset_lsb:",
                #       bit_offset_lsb, " new data : ", bin(new_data))
                self.write_register(address, subaddress, new_data, check_and_retry=True)

        else:       # safer : update local & write distant, read distant, compare with local
            mask = (self.df_i2c["add"] == address) & (self.df_i2c["subadd"] == subaddress)
            data = self.df_i2c.loc[mask, "data"].values[0]  # "{0:08b}".format(
            new_data = "{0:08b}".format(value)
            data = data[0:8 - bit_offset_lsb - bit_size] + new_data[8 - bit_size:8] + data[7 - bit_offset_lsb + 1:8]

            self.update_from_dataframe(pd.DataFrame({'add': [address], 'subadd' : [subaddress], 'data': [data]}))
        return

    def set_bit_list(self, address_list: list, subaddress: int, bit_offset_lsb: int, value: int,
                     methodA=True) -> None:
        self.set_bits_list(address_list, subaddress, bit_offset_lsb, 1, value, methodA)
        return

    def set_bits_list(self, address_list: list, subaddress: int, bit_offset_lsb: int, bit_size: int, value: int,
                      methodA=True) -> None:
        assert isinstance(address_list, list)
        assert isinstance(subaddress, int)
        assert isinstance(bit_offset_lsb, int)
        assert isinstance(bit_size, int)
        assert isinstance(value, int)

        assert subaddress >= 0
        assert subaddress < 256
        assert bit_offset_lsb >= 0
        assert bit_offset_lsb < 8
        assert value >= 0
        assert value < 2**bit_size
        assert bit_size >= 1
        assert bit_size < 9


        if methodA:  # write distant & read distant & compare & retry once if error & print error if any & update local
            # one by one
            for address in address_list:
                assert address >= 0
                assert address < 256
                old_data = int(self.df_i2c.loc[(self.df_i2c["add"] == address) & (self.df_i2c["subadd"] == subaddress), 'data'].iloc[0],2)
                new_data = (old_data & (~((2 ** bit_size - 1) << bit_offset_lsb) & 0xff)) | (value << bit_offset_lsb)
                if old_data == new_data: # only check if data in df was correct
                    self.write_register(address, subaddress, new_data, check_and_retry=True, skip_write=True, force_update=True)
                else:
                    # print("address: ", address, " subaddr: ", subaddress, " old_data : ", bin(old_data), " value: ", '0b'+bin(value)[2:].zfill(bit_size), " bit_offset_lsb:",
                    #       bit_offset_lsb, " new data : ", bin(new_data))
                    self.write_register(address, subaddress, new_data, check_and_retry=True)

            # all at once
            # self.df_i2c.iloc[mask, 2] = new_data
            # self.write_fifo(self.df_i2c[mask])

        else:  # safer: update local & write distant, read distant, compare with local
            mask = (self.df_i2c["add"].isin(address_list)) & (self.df_i2c["subadd"] == subaddress)
            data_list = self.df_i2c[mask]['data'].values

            new_data_list = []
            for data in data_list:
                new_data_list.append(
                    data[0:8 - bit_offset_lsb - bit_size] + "{0:08b}".format(value)[8 - bit_size:8] + data[
                                                                                                      7 - bit_offset_lsb + 1:8])
            self.update_from_dataframe(pd.DataFrame(
                {'add': address_list, 'subadd': [subaddress] * len(address_list),
                 'data': new_data_list}))
        return

    def write_register_list(self, add_list: list, subadd: int, data: int) -> None:
        # NOT TO BE USED : WRITE FIFO SUBJECT TO ERRORS
        mask = (self.df_i2c["add"].isin(add_list)) & (self.df_i2c["subadd"] == subadd)
        self.df_i2c.iloc[self.df_i2c[mask].index, 2] = "{0:08b}".format(data)
        self.write_fifo(self.df_i2c[mask])

    def intrinsic_write(self, data):
        val1 = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_status)
        val2 = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_status)
        val3 = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_status)
        # val = # vote maj python
        val = val1

        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_status, val & ~(1<<4))
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_status, val & ~(1<<4))
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_status, val & ~(1<<4))

        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, data)
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, data)
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, data)

        self.device.write_word(val | (1<<4))
        self.device.write_word(val | (1<<4))
        self.device.write_word(val | (1<<4))

        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_status, val & ~(1<<4))
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_status, val & ~(1<<4))
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_status, val & ~(1<<4))

    def write_register(self, add: int, subadd: int, data: int, verbose=False, check_and_retry=True, skip_write=False, force_update=True) :
        assert isinstance(add, int)
        assert isinstance(subadd, int)
        assert add >= 0
        assert add < 256
        assert subadd >= 0
        assert subadd < 256
        assert data >= 0
        assert data < 256

        # if (subadd==66) | (subadd==65):
        #     print(add, subadd, data)

        self.enable_I2C_clock()
        time.sleep(SLOW_CONTROL_DELAY)

        if not skip_write:
            # single communication

            self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, 0x00)
            self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, data)
            self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, add)
            self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, subadd)
            time.sleep(2*SLOW_CONTROL_DELAY)

        value_well_written = True
        max_repetition = 5
        error_msg = f""

        if check_and_retry:
            i = 0
            for i in range(max_repetition):
                value = self.read_register(add, subadd, turn_on_n_off_i2c_ck=False)
                if value != data:

                    # self.disable_I2C_clock()
                    self.reset_I2C_slave_state_machine()
                    # self.enable_I2C_clock()
                    time.sleep(SLOW_CONTROL_DELAY)

                    error_msg += f"\tAttempt {i}: add {add} subadd {subadd}: read={'{0:08b}'.format(value)} != sent={'{0:08b}'.format(data)}\n"
                    value_well_written = False
                    if i<max_repetition-1:
                        # Write again value
                        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, 0x00)
                        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, data)
                        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, add)
                        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, subadd)
                        time.sleep(2*SLOW_CONTROL_DELAY)
                else:
                    if i > 0:
                        SC_new_warning = f"SC correct after {i + 1} attempt(s) for add {add} subadd {subadd}  data {'{0:08b}'.format(value)}({value}) {self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_error_cnt)} error {self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_unack_cnt)} unack"
                        self.SC_warnings += SC_new_warning
                        if verbose:
                            print(SC_new_warning)
                    value_well_written = True
                    break
            self.nb_write_operation += i + 1
            self.nb_reg_to_write += 1


        if not value_well_written:
            SC_new_error = f"SC failure for add {add} subadd {subadd}  {self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_error_cnt)} error {self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_unack_cnt)} unack"
            status_sc = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_status)
            if status_sc & (1 << 3):

                SC_new_error += "with decoder busy error bit " + '{0:08b}'.format(status_sc) +'\n'+error_msg
            print(SC_new_error)
            self.SC_errors += SC_new_error
            # exit(-1)

        if value_well_written | force_update | (not check_and_retry): # default behaviour : update df
            mask = (self.df_i2c["add"] == add) & (self.df_i2c["subadd"] == subadd)
            self.df_i2c.iloc[mask, 2] = '{0:08b}'.format(data)
            if force_update & (not value_well_written):
                print("I2C local df was overwritten after reading %d times a different value than expected !"%max_repetition)
                print("Correct this I2C error ! ")
                exit()
        self.disable_I2C_clock()

    def write_fifo(self, df: pd.DataFrame):

        # enable i2c clock
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status, src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, 1)
        time.sleep(SLOW_CONTROL_DELAY)

        nb_data = len(df.index) * 4
        i2c_data = b''

        for d in df.iloc:
            add = int(d["add"])
            subadd = int(d["subadd"])
            data = int(str(d["data"]), 2)

            assert isinstance(add, int)
            assert isinstance(subadd, int)
            assert isinstance(data, int)
            assert add >= 0
            assert add < 256
            assert subadd >= 0
            assert subadd < 256
            assert data >= 0
            assert data < 256

            i2c_data += b'\x00'
            i2c_data += data.to_bytes(1, byteorder='little')
            i2c_data += add.to_bytes(1, byteorder='little')
            i2c_data += subadd.to_bytes(1, byteorder='little')

        # MAX number of bytes te be stream/send per call is 255
        count=63 # 4*count should be lower than 255
        nb_cycles = int(nb_data / count)
        remaining = int(nb_data % count)

        # print("before : statut SC ",self.device.read_word(24))
        # print("before : bytes left in fifo sent SC ",self.device.read_word(25))
        if nb_cycles > 0:
            for i in range(nb_cycles):
                i2c_temp = i2c_data[i*count:i*count+count]
                self.device.write_words(src.CONSTANTS.REGISTERS.addr_sc_shift_in, i2c_temp, len(i2c_temp))
                time.sleep(SLOW_CONTROL_DELAY)
                # print("after sleep : bytes left in fifo sent SC ", self.device.read_word(25))

        if remaining > 0:
            i2c_temp = i2c_data[nb_cycles*count:nb_cycles*count+remaining]
            self.device.write_words(src.CONSTANTS.REGISTERS.addr_sc_shift_in, i2c_temp, len(i2c_temp))
            time.sleep(SLOW_CONTROL_DELAY)


        # print("after write words : bytes left in fifo sent SC ",self.device.read_word(25))

        time.sleep(SLOW_CONTROL_DELAY)
        # print("write fifo : after sleep : bytes left in fifo sent SC ",self.device.read_word(25))

        # disable i2c clock
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status, src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, 0)
        return


    def check_all_register(self, config):
        df = self.df_i2c.copy()
        error_count = 0
        for i, row in self.df_i2c.iterrows():
            add = row["add"]
            subadd = row["subadd"]
            read_value = self.read_register(add, subadd)
            default_value = int(row["data"], 2)
            if read_value != default_value:
                if error_count==0:
                    print("Comparing hardware SC with default expected:")
                    print("add, subadd, read_value, default_value")
                error_count += 1
                print(add, subadd, "{0:08b}".format(read_value), "{0:08b}".format(default_value))
            df.at[i, "data"] = "{0:08b}".format(read_value)
        if error_count>0:
            df.to_csv(config['save_folder']+"/temporoc3_hw_default_SC.csv", index=False)
            print("-> %d SC errors"%error_count)

    def read_register(self, add: int, subadd: int, turn_on_n_off_i2c_ck=True) -> int:
        assert isinstance(add, int)
        assert isinstance(subadd, int)
        assert add >= 0
        assert add < 256
        assert subadd >= 0
        assert subadd < 256

        if turn_on_n_off_i2c_ck:
            self.enable_I2C_clock()
            time.sleep(SLOW_CONTROL_DELAY)

        # single communication
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, 0xff)  # Direction
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, 0x00)  # Data (unused here)
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, add)  # Address
        self.device.write_word(src.CONSTANTS.REGISTERS.addr_sc_shift_in, subadd)  # Sub address

        time.sleep(SLOW_CONTROL_DELAY)
        # data to read
        result = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_data_out)

        if turn_on_n_off_i2c_ck:
            self.disable_I2C_clock()

        return result

    def read_fifo(self, df: pd.DataFrame):

        # enable i2c clock
        time.sleep(0.1)
        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status, src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, 1)
        time.sleep(0.1)

        nb_data = len(df.index) * 4
        i2c_data = b''

        add_format = "{{0:#0{}b}}".format(self.addLength + 2)
        subadd_format = "{{0:#0{}b}}".format(self.subaddLength + 2)
        for d in df.iloc:
            add = int(d["add"])
            subadd = int(d["subadd"])

            assert isinstance(add, int)
            assert isinstance(subadd, int)
            assert add >= 0
            assert add < 256
            assert subadd >= 0
            assert subadd < 256

            fulladd = (add<<8)+subadd
            i2c_data += b'\xff\x00'
            i2c_data += fulladd.to_bytes(2, byteorder='big')

        byte_count = 64
        nb_cycles = int(nb_data / byte_count)
        remaining = int(nb_data % byte_count)

        # print("read fifo :0: bytes left in fifo sent SC ", self.device.read_word(25))
        if nb_cycles > 0:
            for i in range(nb_cycles):
                i2c_temp = i2c_data[i * byte_count:i * byte_count + byte_count]
                self.device.write_words(src.CONSTANTS.REGISTERS.addr_sc_shift_in, i2c_temp, len(i2c_temp))
                time.sleep(2*SLOW_CONTROL_DELAY)

                a = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch)
                i = 0
                while a > 0:
                    i += 1
                    a = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch) # bytes left in fifo
                    if i % 10:
                        print(a)
                        print(bin(self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_status)))

                        # print("read fifo :  1    : bytes left in fifo sent SC ",self.device.read_word(25))
        # print(bin(self.device.read_word(24)))

        if remaining > 0:
            i2c_temp = i2c_data[nb_cycles * byte_count:nb_cycles * byte_count + remaining]
            self.device.write_words(src.CONSTANTS.REGISTERS.addr_sc_shift_in, i2c_temp, len(i2c_temp))
            time.sleep(2*SLOW_CONTROL_DELAY)

        a = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch)
        i = 0
        while a > 0:
            i+=1
            a = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch)
            if i%10:
                print(a)
        # print("read fifo :  2    : bytes left in fifo sent SC ", self.device.read_word(25))

        # print(bin(self.device.read_word(24)))
        # print(self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_data_out))
        # data to read
        result = self.device.read_words(src.CONSTANTS.REGISTERS.addr_sc_data_out, int(nb_data/4))

        # disable i2c clock
        while self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_launch) > 0:
            time.sleep(SLOW_CONTROL_DELAY)

        self.device.write_bit(src.CONSTANTS.REGISTERS.addr_sc_status, src.CONSTANTS.REGISTERS.addr_sc_status_bit_enable_i2c_ck, 0)

        return result


    def update_from_dataframe(self, df: pd.DataFrame, ui=None):
        # update df_i2c with data from df
        # df can be partial and data can be partial too e.g. if data = xx1xxxxx only 1 bit will be updated
        dataOK = True
        for i, row in df.iterrows():
            index = self.df_i2c.index[(self.df_i2c["add"] == row["add"]) & (self.df_i2c["subadd"] == row["subadd"])].tolist()[0]
            data = list(self.df_i2c.iloc[index, 2])
            for j, b in enumerate(list(row["data"])):
                if b == '0' or b == '1':
                    data[j] = b

            data = "".join(data)
            df.iloc[i, 2] = data
            self.df_i2c.iloc[index, 2] = data


        # method A : with write_words
        # self.write_fifo(df)
        # data_read = self.read_fifo(df)
        # status_sc = self.device.read_word(src.CONSTANTS.REGISTERS.addr_sc_status)
        # if status_sc & (1 << 3):
        #     print("SC failure : see status reg from FPGA "+bin(status_sc))
        # dataOK = self.verify_data(data_read, df, feedback=False)
        # # if data not OK update the full dataframe
        # if not dataOK:
        #     self.write_fifo(df)
        #     data_read = self.read_fifo(df)
        #     dataOK = self.verify_data(data_read, df)


        return dataOK

    def verify_data(self, data_read, df: pd.DataFrame, feedback=True):
        # df will be modified by this function to be kept updated with values read
        dataOK = True
        for i, d in enumerate(df.iloc):
            if int(data_read[i]) != int(str(d["data"]),2):
                print(f"error i2c add{d['add']} subadd{d['subadd']}: read={'{0:08b}'.format(int(data_read[i]))} != sent={d['data']}")
                dataOK = False
                if feedback:
                    df.iloc[i, 2] = '{0:08b}'.format(int(data_read[i]))
        return dataOK


