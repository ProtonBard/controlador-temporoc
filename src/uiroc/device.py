#
# +-----------------------------------+
# |           Ftdi interface          |
# +-----------------------------------+
#                   |
#                  emu?
#                  y  n
#                 /    \
#                /      \
#               /        \
#              /          \
#             /            \
#            /              \
#           /                \
# +-----------------+ +---------------+
# |     ftd2xx      | |     ftd2xx    |
# |    emulator     | |               |
# +-----------------+ +---------------+
#          |                  |
#          |                  |
# +-----------------+ +---------------+
# |  FPGA emulator  | |               |
# +-----------------+ |               |
#          |          |               |
#          |          |     FPGA      |
# +-----------------+ |               |
# | Slow    control | |               |
# | master emulator | |               |
# +-----------------+ +---------------+
#          |                  |
#          |                  |
# +-----------------+ +---------------+
# | Slow    control | |     ASIC      |
# | slave  emulator | |               |
# +-----------------+ +---------------+
#
#
import datetime
import importlib
import re
from typing import Any
from uiroc.i2c import *

HEADER: int = 0xAA
FOOTER: int = 0x55


class FtdInterfaceError(Exception):

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def __str__(self):
        return self.message


class FtdInterface:

    def __init__(self, emulate=False) -> None:
        self.device = None
        self.brd_id = 0
        self.connect_status = 0
        self.status_message = "Click to connect."
        self.fw_version = 0

        if emulate:
            self.ftd2xx = importlib.import_module("emulation.ftd2xx")
            pass
        else:
            self.ftd2xx = importlib.import_module("ftd2xx")
            pass
        self.device = None
        return

    def connect(self, serial_starts_with: bytes) -> int:
        assert isinstance(serial_starts_with, bytes)
        self.ftd2xx.createDeviceInfoList()
        device_list = self.ftd2xx.listDevices()
        device_list = self.ftd2xx.listDevices() # second time is always better

        # print(device_list)
        if (device_list is None) or (len(device_list) <= 0):
            self.connect_status = 4
            self.status_message = "No device detected, plug/power on your device and click to connect."
            raise FtdInterfaceError("No device found.")

        lst = [x for x in device_list if x.startswith(serial_starts_with) & x.endswith(b'A')]
        if len(lst) <= 0:
            self.connect_status = 5
            self.status_message = "Exception raised!"
            raise FtdInterfaceError("No valid device found. Expecting Temporoc evaluation board %s "%serial_starts_with)

        self.device = self.ftd2xx.openEx(lst[0])
        # print(self.device.getDeviceInfo())
        self.device.setUSBParameters(4096, 4096)
        self.device.setTimeouts(10, 10)
        self.device.setLatencyTimer(0)

        time.sleep(0.1)
        self.connect_status = 1
        return int(re.findall(b"(?<=TP2_)[0-9]+", lst[0])[0])

    def close(self):
        return self.device.close()

    def assert_connected(self) -> bool:
        if self.device is None:
            self.connect_status = 4
            self.status_message = "No device detected, plug/power on your device and click to connect."
            raise FtdInterfaceError("Device is not connected.")
        return True

    def assert_status(self) -> bool:
        status: int = self.device.getEventStatus()
        if status != 0:
            self.device.close()
            self.device = None
            self.connect_status = 2
            self.status_message = f"Connection error, FTDI chip status: {self.get_status()}."
            raise FtdInterfaceError(f"Status error : {str(status)}.")
        return True

    def assert_header(self, b: int) -> None:
        if b != HEADER:
            raise FtdInterfaceError(f"Header mismatch : expected {hex(HEADER)}, got {hex(b)}.")
        return

    def assert_footer(self, b: int) -> None:
        if b != FOOTER:
            raise FtdInterfaceError(f"Header mismatch : expected {hex(FOOTER)}, got {hex(b)}.")
        return

    def assert_length(self, res: bytes, elen: int) -> None:
        rlen: int = len(res)
        if rlen != elen:
            raise FtdInterfaceError(
                f"Message length mismatch : expected {elen} bytes, got {rlen} bytes, message was {res.hex(' ')}.")
        return

    def is_connected(self) -> bool:
        add = src.CONSTANTS.REGISTERS.addr_version_major
        self.assert_connected()
        self.assert_status()
        expected_length = 5

        encapsulated_data = b'\xaa\x00' + (add + 128).to_bytes(1, byteorder="little") + b'\x00\x55'
        self.device.write(encapsulated_data)
        time.sleep(0.00001)
        res = self.device.read(expected_length)
        failed_USB_communication = self.is_corrupted_header_footer_length(res, expected_length, add, 1)
        return not failed_USB_communication


    def read_word(self, add: int) -> int:
        assert isinstance(add, int)
        assert add >= 0
        assert add < 128
        self.assert_connected()
        self.assert_status()
        expected_length = 5

        # add repetition, todo : check if mess up with FPGA fifo
        cpt = 10
        failed_USB_communication = True
        while failed_USB_communication and cpt != 0:
            encapsulated_data = b'\xaa\x00' + (add + 128).to_bytes(1, byteorder="little") + b'\x00\x55'
            self.device.write(encapsulated_data)
            time.sleep(0.00001)
            res = self.device.read(expected_length)
            failed_USB_communication = self.is_corrupted_header_footer_length(res, expected_length, add, 1)
            cpt -= 1


        if len(res)==0:
            raise FtdInterfaceError('usb_res_empty')

        # blocking assertion if consecutives repeated failures
        self.assert_header(res[0])
        self.assert_footer(res[-1])
        self.assert_length(res, expected_length)

        return res[3]

    def is_corrupted_header_footer_length(self, res, expected_length, add, words_length):
        if len(res) != expected_length:
            print("device.read_word: USB data length error")
            print(f"device.read_word ft status : {self.device.getEventStatus()}")
            with open("usb_error_log.txt", "a") as f:
                if words_length==1:
                    f.write("%s LENGTH "%datetime.datetime.now()+str(res)+'read_word  at add %d'%add+'\n')
                else:
                    f.write("%s LENGTH "%datetime.datetime.now()+str(res)+'read_words at add %d with length %d'%(add, words_length)+'\n')
            self.device.resetDevice()
            return True
        if res[0] != HEADER:
            print("device.read_word: USB data header error")
            if self.device.getEventStatus() != 0: print(f"device.read_word ft status : {self.device.getEventStatus()}")
            print(len(res), list(res))
            with open("usb_error_log.txt", "a") as f:
                f.write("%s HEADER "%datetime.datetime.now()+str(res)+'\n')
            self.device.resetDevice()
            return True
        if res[-1] != FOOTER:
            print("device.read_word: USB data footer error")
            if self.device.getEventStatus() != 0: print(f"device.read_word ft status : {self.device.getEventStatus()}")
            print(len(res), list(res))
            with open("usb_error_log.txt", "a") as f:
                f.write("%s FOOTER "%datetime.datetime.now()+str(res)+'\n')
            self.device.resetDevice()
            return True
        return False

    def read_words(self, add: int, words_length: int) -> bytes:
        assert isinstance(add, int)
        assert isinstance(words_length, int)
        assert add >= 0
        assert add < 128
        assert words_length >= 0
        assert words_length <= 65536
        self.assert_connected()
        self.assert_status()
        expected_length = words_length + 4

        # add repetition, todo : check if mess up with FPGA fifo
        cpt = 10
        failed_USB_communication = True
        while failed_USB_communication and cpt != 0:
            l = (words_length - 1).to_bytes(2, byteorder="little")
            encapsulated_data = b'\xaa' + l[0].to_bytes(1, byteorder="little") + (add + 128).to_bytes(1,
                                                                                                      byteorder="little") + \
                                l[1].to_bytes(1, byteorder="little") + b'\x55'
            self.device.write(encapsulated_data)
            time.sleep(0.001)  # time delay required otherwise source of USB error
            res = self.device.read(expected_length)
            failed_USB_communication = self.is_corrupted_header_footer_length(res, expected_length, add, words_length)
            cpt -= 1

        self.assert_header(res[0])
        self.assert_footer(res[-1])
        self.assert_length(res, expected_length)
        return res[3:-1]

    def read_bit(self, add: int, bit_offset: int):
        return (self.read_word(add) & (1 << bit_offset)) >> bit_offset

    def write_word(self, add: int, word: int) -> None:
        assert isinstance(add, int)
        assert isinstance(word, int)
        assert add >= 0
        assert add < 128
        assert word >= 0
        assert word < 256
        self.assert_connected()
        self.assert_status()
        encapsulated_data = b'\xaa\x00' + add.to_bytes(1, byteorder="little") + \
                            word.to_bytes(1, byteorder="little") + b'\x55'
        self.device.write(encapsulated_data)
        return

    def write_words(self, add: int, word: bytes, length: int) -> None:
        assert isinstance(add, int)
        assert isinstance(word, bytes)
        assert add >= 0
        assert add < 128
        assert len(word) > 0
        assert length == len(word)
        self.assert_connected()
        self.assert_status()
        encapsulated_data = b'\xaa' + (length - 1).to_bytes(1, byteorder="little") + add.to_bytes(1,
                                                                                                  byteorder="little") + \
                            word + b'\x55'
        self.device.write(encapsulated_data)
        return

    def write_bit(self, add, bit_offset, bit_value):
        word = self.read_word(add)
        new_word = (word & ~(1 << bit_offset)) | (bit_value << bit_offset)
        # new_word = word[0:7 - bit_offset] + str(bit_value) + word[7 - bit_offset + 1:8]
        self.write_word(add, new_word)
        return new_word

    def get_status(self):
        if self.device is not None:
            return self.device.getEventStatus()
        return

    def get_description(self):
        if self.device is not None:
            return self.device.getDeviceInfo()["description"]
        return

    def get_serial_number(self):
        if self.device is not None:
            return self.device.getDeviceInfo()["serial"]
        return

    def get_device_list(self, serial_startswith):
        self.ftd2xx.createDeviceInfoList()
        device_list = self.ftd2xx.listDevices()
        if device_list is not None and len(device_list) > 0:
            lst = [x for x in device_list if x.startswith(serial_startswith)]
            return [str(d)[2:-1] for d in lst if 'A' in str(d)]
        return []

    def reset_device(self):
        self.device.resetDevice()

    def usb_get_status(self):
        if self.device is None:
            print("no device connected")
            return 0
        if self.device.getEventStatus() != 0:
            print(f"device.read_words ft status error: {self.device.getEventStatus()}")
            return 0
        return self.device.getQueueStatus()

    def read_ex(self, cnt: int):
        ret = bytearray()
        if self.device is None:
            print("no device connected")
            return ret
        if self.device.getEventStatus() != 0:
            print(f"device.read_ex ft status error: {self.device.getEventStatus()}")
            return ret
        res = self.device.read(cnt)
        if len(res) == 0 or res[0] != 170 or res[-1] != 85:
            print(f"device.read_ex ft status : {self.device.getEventStatus()}")
            self.device.resetDevice()
            return ret
        return res[3:259] + res[263:-1]
