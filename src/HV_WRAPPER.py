import serial
import serial.tools.list_ports
import time
import threading
from colorama import Fore, Style
from datetime import datetime


class HV_WRAPPER:
    def __init__(self, board_config):
        if 'CAEN_serial_number' in board_config.keys():
            serial_number = board_config['CAEN_serial_number']
        else:
            serial_number = None
        
        self.board_config = board_config
        self.serial_number = serial_number
        self.connected = False
        self.serialPort = 0
        self.a7585Timer = 0
        self.mutex = threading.Lock()
        # self.serial_number = '0'
        self.timer = None
        self.board = None

    def connect(self):
        board_config = self.board_config
        if board_config['mode'] == 'slave':
            end = '\t'
        else:
            end = '\n'

        if not self.connected:
            ports = serial.tools.list_ports.comports()
            exception_msg_list = []
            exception_port_list = []

            available_serial_number =  [port.serial_number for port in ports if port.serial_number is not None]
            if self.serial_number not in available_serial_number:
                raise Exception(f"Error: CAEN HV module A7585 biasing SiPM named {self.serial_number} seems not connected to the computer."
                                f"\nAvailable ones are : {available_serial_number}")

            for port in ports:
                if self.serial_number:
                    if port.serial_number != self.serial_number:
                        continue
                try:
                    # print(port.device)
                    self.serialPort = serial.Serial(port=port.device, baudrate=115200, bytesize=8, parity='N',
                                                    stopbits=1,
                                                    timeout=1)

                    self.set_machine_mode()
                    self.set(0, 0)
                    r = self.read_line_with_timeout(1000)
                    self.serial_number = port.serial_number
                    if "OK" in r:
                        self.set(0, 0)  # Turn OFF initially
                        self.set(1, 0)  # digital mode
                        self.set(3, 5)  # ramp [V/s]
                        self.set(2, 20)  # voltage [V]
                        self.set(5, 5)  # max current [mA]
                        self.set(4, 80)  # max voltage [V]
                        time.sleep(0.2)

                        self.connected = True
                        self.read_all()
                        # a7585Timer = threading.Timer(1, lambda: cb(ui))
                        # a7585Timer.start()
                        break
                    else:
                        self.serialPort.close()
                except Exception as ex:
                    # print(f"Error connecting to port {port}: {ex}")
                    exception_msg_list.append(ex)
                    exception_port_list.append(port)
            if not self.connected:
                for port, ex in zip(exception_msg_list, exception_port_list):
                    print(f"Error connecting to port {port}: {ex}")
                raise Exception("Error: CAEN HV module A7585 biasing SiPM could not be accessed")
        else:
            self.a7585Timer.cancel()
            a7585Timer = 0
            self.set(0, 0)
            self.set(1, 0)
            self.set(3, 10)
            self.set(2, 20)
            self.set(5, 1)
            time.sleep(0.2)
            self.serialPort.close()
            self.serialPort = 0
            self.connected = False

        self.board = self.board_config['board']
        self.mode = self.board_config['mode']
        # self.board_config = self.board_config
        self.target_hv = 0

        print("CAEN HV %s -> B%d %s" % (self.serial_number, self.board_config['board'], self.board_config['mode']), end=end)
        # board_label = '_B%d' % board
        board_label = ''
        self.board_config['current_time'] = []
        self.board_config['hv_eff_voltage' + board_label] = []
        self.board_config['hv_eff_current' + board_label] = []

    def turn_on(self):
        # print('Turning ON HV to %.1f V'%self.board_config['target_hv'])
        self.target_hv = self.board_config['target_hv']
        self.set_voltage(self.board_config['target_hv'])
        # self.hv.print_when_setpoint_reached()
        self.save_periodically_SiPM_HV()


    def turn_on_slowly(self):
        print('Turning ON slowly HV to %.1f V'%self.board_config['target_hv'])
        self.target_hv = self.board_config['target_hv']
        self.set_voltage_modulating_ramp(self.board_config['target_hv'], self.board_config['SiPM_breakdown'])
        # self.hv.print_when_setpoint_reached()
        self.save_periodically_SiPM_HV()

    def set_machine_mode(self):
        with self.mutex: self.serialPort.write("AT+MACHINE\n\r".encode())

    def set(self, add, val):
        with self.mutex: self.serialPort.write(("AT+SET," + str(add) + "," + str(val) + "\n\r").encode())

    def get(self, add):
        with self.mutex: self.serialPort.write(("AT+GET," + str(add) + "\n\r").encode())

    def read_all(self):
        with self.mutex: r = self.serialPort.read_all()
        return r.decode()

    def read_line_with_timeout(self, timeout_milliseconds):
        line_read = False
        received_line = ""

        def read_from_serial():
            nonlocal line_read, received_line
            with self.mutex: received_line = self.serialPort.readline().decode()
            line_read = True

        serial_thread = threading.Thread(target=read_from_serial)
        serial_thread.start()
        serial_thread.join(timeout_milliseconds)
        if serial_thread.is_alive(): line_read = False
        if line_read:
            return received_line
        else:
            return ""

    def set_mode(self, mode):
        if self.serialPort == 0: return
        self.set(1, mode)
        r = self.read_line_with_timeout(1000)
        if r == "": print("Timeout error")

    def set_voltage(self, value_V):
        if self.serialPort == 0: return
        self.set(2, value_V)  # Volts
        r = self.read_line_with_timeout(1000)
        if r == "": print("Timeout error")
        self.set_enHV(1)
        self.set_enHV(1)

    def set_voltage_modulating_ramp(self, value_V, SiPM_breakdown):

        self.set(3, 10)  # ramp [V/s]
        if value_V < SiPM_breakdown:
            self.set_voltage(value_V)
        else:
            self.set_voltage(SiPM_breakdown)
            time.sleep(SiPM_breakdown / 10)
            self.set(3, 5)  # ramp [V/s]
            self.set_voltage((SiPM_breakdown + value_V) / 2)
            time.sleep((SiPM_breakdown + value_V) / 2 / 5)
            self.set(3, 2)  # ramp [V/s]
            self.set_voltage(value_V)

    def set_max_current(self):
        if self.serialPort == 0: return
        self.set(5, 1)  # mA
        r = self.read_line_with_timeout(1000)
        if r == "": print("Timeout error")

    def set_ramp_speed(self):
        if self.serialPort == 0: return
        self.set(3, 5)  # V/s
        r = self.read_line_with_timeout(1000)
        if r == "": print("Timeout error")

    def set_enHV(self, bit):
        if self.serialPort == 0: return
        self.set(0, bit)
        r = self.read_line_with_timeout(1000)
        if r == "": print("Timeout error")

    def get_IV(self):
        hv_eff_current, hv_eff_voltage = 0, 0
        if self.connected:
            self.read_all()
            self.get(231)
            r = self.read_line_with_timeout(1000)
            if len(r) > 4: hv_eff_voltage = float(r[3:-3])
            self.get(232)
            r = self.read_line_with_timeout(1000)
            if len(r) > 4: hv_eff_current = float(r[3:-3])
        return hv_eff_current, hv_eff_voltage


    def close(self):
        self.set_enHV(0)
        if self.timer:
            self.timer.cancel()
            print('Exiting thread for periodic SiPM IV measurement')
        self.serialPort.close()

    def save_IV(self, hv_eff_current, hv_eff_voltage):
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")

        # mode_config = config['config_B%d'%(self.board)]
        self.board_config['current_time'].append(current_time)
        self.board_config['hv_eff_current'].append(hv_eff_current)
        self.board_config['hv_eff_voltage'].append(hv_eff_voltage)

        # local_output_dir = config['save_folder']
        # config_file = local_output_dir + 'config.yaml'
        # with open(config_file, 'w') as outfile:
        #     yaml.dump(config, outfile, default_flow_style=False, Dumper=VerboseSafeDumper)
        # outfile.close()


    def measure_SiPM_HV(self):
        hv_eff_current, hv_eff_voltage = self.get_IV()

        self.save_IV(hv_eff_current, hv_eff_voltage)

        return self.serial_number+" bias SiPM under: %.1f V %.2f µA  "%(hv_eff_voltage, hv_eff_current*1e3)

    def save_periodically_SiPM_HV(self, period_in_minutes=5):
        self.timer = threading.Timer(60 * period_in_minutes, self.measure_SiPM_HV)
        self.timer.start()


    # def print_when_setpoint_reached(self):
    #     self.timer_setpoint_reached = threading.Timer(2, self.wait_setpoint_reached)
    #     self.timer_setpoint_reached.start()

    def wait_setpoint_reached(self, target_hv=None):
        iter = 0
        if target_hv is None:
            target_hv = self.target_hv
        while iter < 40: # 20 seconds
            hv_eff_current, hv_eff_voltage = self.get_IV()
            self.save_IV(hv_eff_current, hv_eff_voltage)

            if (hv_eff_voltage > (target_hv-0.2)) & (hv_eff_voltage < (target_hv+0.2)):
                # self.timer_setpoint_reached.cancel()
                print(Fore.GREEN + "Setpoint reached for %s (B%d): %.2f µA  %.1f V" % (self.mode, self.board, hv_eff_current * 1e3, hv_eff_voltage)+ Style.RESET_ALL)
                break
            elif iter == 19:
                print(Fore.RED + "Setpoint NOT reached for %s (B%d): %.2f µA  %.1f V" % (
                    self.mode, self.board, hv_eff_current * 1e3, hv_eff_voltage) + Style.RESET_ALL)
            iter += 1
            time.sleep(0.5)

