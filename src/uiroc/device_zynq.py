import socket
import serial
import struct
import time
import src
import src.CONSTANTS 

IP_ADDRESS  : str = "192.168.2.239"  # doit etre saisie ou auto 
IP_PORT     : int = 40200
SERIAL_PORT : str = "COM4"  #doit etre automatique ou saisie 
SERIAL_BAUD : int = 115200
ETHERNET_PACKET_SIZE : int = 6000

sock = None
ser = None

connect_status = 1
status_message = ""




class USBInterface:
    def __init__(self):
        self.PID = "EA60"
        self.VID = "10C4"
        self.device= None
        
        # Command definitions
        self.CMD_READ       = 0x01
        self.CMD_WRITE      = 0x02
        self.CMD_RESET      = 0x03
        self.CMD_WRITE_USB  = 0x04
        self.CMD_READ_USB   = 0x05
        self.CMD_DAQ        = 0x06
        self.CMD_CONFIG	    = 0X07
        self.CMD_SEL_ASIC   = 0x08

        # Response codes
        self.RESP_OK        = 0x01
        self.RESP_ERROR     = 0xFF
        self.RESP_BAD_ARGS  = 0xFE
        self.RESP_BAD_CMD   = 0xFD

        self.COMM_VAL = False

    def sel_asic(self, asic_id):
        args = [asic_id]  # 1 argument: ASIC ID
        self.device.read_all()  # Clear any existing data in the buffer
        status = self._send_command(self.CMD_SEL_ASIC, args)
        
        if status != self.RESP_OK:
            raise ValueError(f"Select ASIC failed with status: {status:02X}")
            
    def connect(self):
        try:
            ports = serial.tools.list_ports.comports()
            for port, desc, hwid in ports:
                if self.PID in hwid and self.VID in hwid:
                    self.device= serial.Serial(
                        port=port,
                        baudrate=115200,
                        timeout=1
                    )
                    print(f"Connected successfully to USB FPGA")
                    return True
        except serial.SerialException as e:
            print(f"Connection failed: {e}\n")
            return False
    def close(self):
        if self.device:
            self.device.close()
            self.device = None
            print("Device connection closed.")

    def _send_command(self, command, args):
        """
        Send command with variable number of arguments
        Format: [CMD][ARG_COUNT][ARG1][ARG2]...
        """
        # Create packet: command byte + argument count + arguments
        packet = struct.pack('BB' + 'B' * len(args), 
                           command, 
                           len(args), 
                           *args)
        
        self.device.write(packet)
        
        # Read response
        response = self.device.read(1)
        if not response:
            raise TimeoutError("No response received")
        
        status = struct.unpack('B', response)[0]
        return status
    
    def assert_connected(self) -> bool:
        if self.device is None:
            self.connect_status = 4
            self.status_message = "No device detected, plug/power on your device and click to connect."
            #raise FtdInterfaceError("Device is not connected.") #TODO change class name after testing 
        return True
    def assert_status(self) -> bool:
        #status: int = self.device.getEventStatus() #TODO add embed zynq code to imitate this 
        if self.device == None:
            #self.device.close()
            self.device = None
            self.connect_status = 2
            self.status_message = f"Connection error, FTDI chip status: {self.assert_connected()}."
            #raise FtdInterfaceError(f"Status error : {str(1)}.")
        return True

    def is_connected(self) -> bool:
        add = src.CONSTANTS.REGISTERS.addr_version_major
        self.assert_connected()
        self.assert_status()
        expected_length = 5
        encrypted_data = struct.pack('BBB', self.CMD_READ, add, 0X00)
        self.device.write(encrypted_data)
        time.sleep(0.00001)
        res = int(self.device.read(expected_length).hex(), 16)
        if res == 0x00:
            return True
        else:
            return False

    def set_asic(self, asic_id):
        args = [asic_id]  # 1 argument: ASIC ID
        status = self._send_command(self.CMD_SEL_ASIC, args)
        
        if status != self.RESP_OK:
            raise ValueError(f"Select ASIC failed with status: {status:02X}")
    
    def reset_i2c(self, board=0):
        """Reset I2C with new command format"""
        args = [board & 0xFF]  # 1 argument: board
        status = self._send_command(self.CMD_RESET, args)
        
        if status != self.RESP_OK:
            raise ValueError(f"Reset failed with status: {status:02X}")

    def start_daq(self, board=0, rate=0, channels=0, mode=0):
        """Start DAQ with configuration"""
        #TODO add the comm_val start/stop for daq 
        self._send_command(self.CMD_CONFIG, [0, 0x02])
        self.COMM_VAL
        pass

    def write_word(self, addr, data=0x00):
        args = [addr & 0xFF, data & 0xFF]
        # if addr == src.CONSTANTS.REGISTERS.addr_deser_common:
        #     status = self._send_command(self.CMD_CONFIG, [0, data])
        # else:
        status = self._send_command(self.CMD_WRITE_USB, args)
        #TODO check the return code 
        return status
    def read_word(self, addr, data=0x00):
        args = [addr & 0xFF, data & 0xFF]
        # if addr == src.CONSTANTS.REGISTERS.addr_deser_common:
        #     value = self._send_command(self.CMD_CONFIG, [1, data])
        # else:
        value = self._send_command(self.CMD_READ_USB, args)
        #if value == self.RESP_BAD_ARGS:
        #    raise ValueError("Invalid argument count")
        #elif value == self.RESP_BAD_CMD:
        #    raise ValueError("Invalid command")
        #elif value == self.RESP_ERROR:
        #    raise ValueError("I2C operation failed or timeout")
        return value
    
    def write_words(self, add: int, words: bytes, length: int) -> None:
        assert isinstance(add, int)
        assert isinstance(words, bytes)
        assert add >= 0
        assert add < 128
        assert len(words) > 0
        assert length == len(words)
        self.assert_connected()
        self.assert_status()
        
        # Send each byte individually using write_word
        for i, word in enumerate(words):
            # Ensure we don't exceed address range
            assert add < 128
            
            # Use write_word to send each byte
            print(f"[DEBUG] write word: {hex(word)}")
            self.write_word(add, word)

    def write_bit(self, addr, bit_offset, bit_value):
        """Write a single bit while preserving others"""
        word = self.read_word(addr)
        new_word = (word & ~(1 << bit_offset)) | (bit_value << bit_offset)
        self.write_word(addr, new_word)
        r_new_word = self.read_word(addr)
        
        if r_new_word != new_word:
            print(f"not the same after change bit prev {word:02X} new {new_word:02X}")
        return new_word
    
    def set_bit(self, address, bit_offset_lsb, value):
        """Write a single bit while preserving others"""
        # Simply delegate to set_bits with bit_size=1
        return self.set_bits(address, 1, bit_offset_lsb, value)

    def set_bits(self, address, bit_size, bit_offset_lsb, value):
        """Write multiple bits while preserving others"""
        # Read current value
        word = self.read_word(address)
        
        # Create mask of the bits we want to change
        mask = ((1 << bit_size) - 1) << bit_offset_lsb
        
        # Clear the bits we want to change and set new value
        new_word = (word & ~mask) | ((value << bit_offset_lsb) & mask)
        
        # Write new value
        self.write_word(address, new_word)
        
        # Verify the write
        r_new_word = self.read_word(address)
        
        if r_new_word != new_word:
            print(f"not the same after change bits prev {word:02X} new {new_word:02X}")
        return new_word
    def set_bit_list(self, address_list, bit_offset_lsb, value):
        """Write a single bit while preserving others for multiple addresses"""
        # Simply delegate to set_bits_list with bit_size=1
        return self.set_bits_list(address_list, 1, bit_offset_lsb, value)

    def set_bits_list(self, address_list, bit_size, bit_offset_lsb, value):
        """Write multiple bits while preserving others for multiple addresses"""
        # Create mask of the bits we want to change
        mask = ((1 << bit_size) - 1) << bit_offset_lsb
        
        for address in address_list:
            # Read current value
            word = self.read_word(address)
            
            # Clear the bits we want to change and set new value
            new_word = (word & ~mask) | ((value << bit_offset_lsb) & mask)
            
            # Write new value
            self.write_word(address, new_word)
            
            # Verify the write
            r_new_word = self.read_word(address)
            
            if r_new_word != new_word:
                print(f"not the same after change bits at addr {address:02X}| prev {word:02X} new {new_word:02X}")
        
        return new_word




class EthernetController:
    ETHERNET_PACKET_SIZE = ETHERNET_PACKET_SIZE  # Standard buffer size

    def __init__(self, ip_address="192.168.1.10", port=40200):
        self.ip_address = ip_address
        self.port = port
        self.sock = None
        self.connect()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5)
            #self.sock.setblocking(False)
            return True
        except socket.error as e:
            print(f"Socket creation failed: {e}")
            return False

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def sendto(self, ba) -> None:
        if self.sock:
            self.sock.sendto(ba, (self.ip_address, self.port))

    def recvfrom(self):
        if self.sock:
            try:
                return self.sock.recvfrom(self.ETHERNET_PACKET_SIZE)
            except :
                return None
        return None