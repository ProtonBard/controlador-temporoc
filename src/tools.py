import threading

from a7585d.a7585d import A7585D
from a7585d.a7585d import A7585D_REG
import serial
import serial.tools.list_ports

import vxi11 as vx
import yaml
from src.utils import *



# pip install python-vxi11
# DOC for remote control on lecroy oscilloscope :
# http://cdn.teledynelecroy.com/files/manuals/maui-remote-control-and-automation-manual.pdf
import vxi11.vxi11

class lecroyOscilloDAQ:
    def __init__(self, hostIP):
        self.oscillo = vx.Instrument(hostIP)
        # or host name (better because not sensitive to IP changes with DHCP)

        if self.oscillo is not None:
            scope_idn = '*IDN LECROY,WAVERUNNER9104,LCRY4703N41520,10.3.0'
            if self.oscillo.ask("*IDN?")==scope_idn:
                # self.oscillo.write("BUZZ BEEP")
                # self.oscillo.write("BUZZ BEEP")
                # self.oscillo.write("BUZZ BEEP")
                print("Oscillo connected ! :)")
            else:
                print("Wrong equipment connected. Expected "+scope_idn)
        else:
            print("Check if oscilloscope is on LXI protocol (not TCP/IP)")

    def clearSweep(self):
        self.oscillo.write(r"""vbs 'app.measure.clearsweeps' """)
        self.oscillo.write(r"""vbs 'app.Math.ClearSweeps' """)
    def save_insitu_waveforms(self):
        self.oscillo.ask(r"""vbs 'app.SaveRecall.Waveform.SaveFile' """)

    def get_waveforms(self, output_folder, filename):
        self.oscillo.write('TRMD STOP')

        # method 2 in 1 step
        deltaT_suffix = 'F1'
        LG_sh_amplitude_master_suffix = 'F3'
        LG_sh_amplitude_slave_suffix = 'F2'
        TOT_width_master_suffix = 'F4'
        TOT_width_slave_suffix = 'F5'
        file_start_index = 12
        file_stop_index = -1
        index_step = 14
        trace_list = [deltaT_suffix, LG_sh_amplitude_master_suffix, LG_sh_amplitude_slave_suffix, TOT_width_master_suffix, TOT_width_slave_suffix]

        trace_data_list = []
        for trace in trace_list:
            trace_data_list.append(self.oscillo.ask(trace + ":INSP? 'DATA_ARRAY_2',FLOAT").replace("\r\n", ''))  # truncate header and footer

            # trace_data_list.append(scopeLecroy.oscillo.ask(trace + ":INSP? 'DATA_ARRAY_2',FLOAT")
            #             .replace("\r\n", '')[file_start_index:file_stop_index]  # truncate header and footer
            #             .replace('   ', '\n').replace('  ', '\n'))  # deal with spaces for + and - float

        events_number = int((len(trace_data_list[0])-10)/14)
        # all col have the same events_number since trend mode = average and scope stopped between data fetches "

        # csv_file = ','.join([f'{trace=}'.split('=')[0] for trace in trace_list])
        csv_file = 'deltaT,LG_sh_amplitude_master,LG_sh_amplitude_slave,TOT_width_master,TOT_width_slave\n'
        for i in range(events_number):
            for ti, trace in enumerate(trace_data_list):
                csv_file += trace[12 + i * 14 : 10 + 13 + i * 14]
                if ti != len(trace_data_list)-1:
                    csv_file += ','
                else:
                    csv_file += '\n'

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        with open(output_folder+filename, "w") as text_file:
            text_file.write(csv_file)

        text_file.close()

        pass
        self.oscillo.write('TRMD NORM')

        # method 1 in 2 steps
        # scopeLecroy.oscillo.ask("STO ALL_DISPLAYED,FILE")
        # for trace in trace_list:
        #     with open(trace+output_file, "w") as text_file:
            # scopeLecroy.oscillo.ask("TRFL? DISK,HDD,FILE,'D:\\file.txt'")

        # method 3
        # to get byte to save and recall, not to read
        # scopeLecroy.oscillo.ask_raw(str("CHDR SHORT; C1:WaveForm?").encode("utf-8"))

    def getMeasure(self, channel, measureType, exponent=0):
        validMeasureType = {'mean', 'sdev', 'num'}
        if measureType not in validMeasureType:
            raise ValueError("Lecroy measure function call has received a wrong measure type :" + str(measureType))
        stringAnswer = self.oscillo.ask(r"""vbs? 'return=app.measure.p{0}.{1}.result.value' """
                                        .format(channel, measureType))
        try:
            # val = float(stringAnswer.split()[1]) * 10 ** exponent
            val = float(stringAnswer.split()[1])
        except:
            val = 0

        # val = '%.3f' % val
        return val

    def getSetupChannel(self, channel):
        return self.oscillo.ask("C" + str(channel) + ":PAVA?")

    def getSetupMeasure(self, measureNumber):
        return self.oscillo.ask('PACU? ' + str(measureNumber))

    def setTimebase(self, time):  # unit : second
        self.oscillo.write(r"""vbs? 'app.Acquisition.Horizontal.HorScale = {:.0e}' """.format(time))

    def write(self, measure):
        self.oscillo.write(measure)

    def ask(self, measure):
        return self.oscillo.ask(measure)

    def save_setup(self, filepath):
        self.oscillo.write('*SAV 2')
        setup = self.oscillo.ask('PANEL_SETUP?')
        output_folder = os.path.dirname(filepath)
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        with open(filepath, "w") as text_file:
            text_file.write(setup)
        text_file.close()

    def load_setup(self, filepath):
        with open(filepath, "r") as text_file:
            read_setup = text_file.read()
        text_file.close()
        self.oscillo.write(read_setup)
        self.oscillo.write('*RCL 2')

# install lib from https://github.com/nelsond/prologix-gpib-ethernet
# using pip install git+git://github.com/nelsond/prologix-gpib-ethernet.git

# doc : http://prologix.biz/downloads/PrologixGPIB-ETHAgilentIOSetup.pdf
# doc multimeter keithley 2000 : https://download.tek.com/manual/2000-900_J-Aug2010_User.pdf
# doc SCAN card : https://assets.testequity.com/te1/Documents/pdf/keithley/2000-SCAN-Manual.pdf
# doc sourcemeter 2410 :


# from plx_gpib_ethernet import PrologixGPIBEthernet  # to communicate using GPIB over Ethernet
import time
import numpy as np
# import pyperclip  # to copy output to clipboard


class prologixController:
    def __init__(self, prologix_ip):
        self.controller = PrologixGPIBEthernet(prologix_ip)
        self.controller.connect()


    def getDataKeithley(self, gpib_port, chan_start, *chan_stop):
        # todo : use :trigger:signal instead of :init
        self.controller.select(gpib_port)
        # Indentify the self.connected device
        # print(self.controller.query('*IDN?'))
        self.controller.write('*RST')  # Suspends triggering

        self.controller.write("TRAC:CLE")  # clear the buffer before writing anything there

        # self.controller.write(":FORM:DATA ASCII")  # ASCII formatted results
        # self.controller.write(":SENS:FUNC 'VOLT:DC'")  # Read DC volts
        # self.controller.write("SENS:VOLT:DC:NPLC 1")  # set integration rate (line cycles) to 1
        # self.controller.write("SENS:VOLT:DC:RANGE 10")  # select voltage range 1V (ie above 9.99 V => overflow !!)
        # self.controller.write(":TRIG:DELAY 2.000")  # // No (additional) delay between samples
        self.controller.write(":ROUT:OPEN:ALL")  # open all channels for scan
        # self.controller.write("*WAIT")
        self.controller.write(":Trigger:Delay:AUTO 1")


        if chan_stop:  # multi channel wise acquisition
            chan_stop = chan_stop[0]
            buf_size = chan_stop - chan_start + 1
            print("close")
            self.controller.write("ROUT:SCAN:LSEL INT")  # select internal scanning

            self.controller.write(
                "ROUT:SCAN:INT (@" + str(chan_start) + ":" + str(chan_stop) + ")")  # select channels you want to scan
            # print(self.controller.query("ROUT:SCAN:INT?"))
            self.controller.write("TRAC:POIN 3")  # + str(buf_size + 1))  # select buffer size
        else:
            buf_size = 1
            self.controller.write(":ROUT:CLOSE (@ " + str(chan_start) + ")")  # select the channel you want to scan
            self.controller.query(":ROUTe:CLOSe:STATe?")
            self.controller.write("TRAC:POIN 2")  # select buffer size

        self.controller.write("TRACE:FEED SENSE1")  # put raw reading in buffer
        self.controller.write("TRACE:FEED:CONT NEXT")  # storage process starts, fills buffer, then stops

        self.controller.write("INIT")  # launch measurement trigger
        time.sleep(0.1)

        # exit SCAN mode on Keithley controller
        self.controller.write(":ROUT:SCAN:LSEL NONE")  # exit SCAN mode, but go to REM mode, so then press LOCAL on front panel
        self.controller.write(":SYST:KEY 1")  # equivalent to shift key press
        self.controller.write(":SYST:KEY 29")  # equivalent to scan key press

        # Read buffer
        data = np.array([])
        # for i in range(buf_size):
        newData = self.controller.query(":TRAC:DATA?")  # read data
        newData = [round(float(m), 4) for m in newData.split(",")]  # keep 4 decimals for each value
        data = np.append(data, np.array(newData))

        return data

        # print(data.reshape(-1, N))
        # return np.around(np.mean(data.reshape(-1, N), axis=1), 4)

    def rebootPowerSupply(self, gpib_port):
        self.controller.select(gpib_port)
        self.controller.write("OUTPUT OFF")

        time.sleep(1)
        self.controller.write("OUTPUT ON")
        print("Power supply rebooted")

    def getDataKeithley0(self, gpib_port, chan_start, *chan_stop):

        self.controller.select(gpib_port)
        # Indentify the self.connected device
        # print(self.controller.query('*IDN?'))

        self.controller.write('*RST')  # Suspends triggering

        self.controller.write(":FORM:DATA ASCII")  # ASCII formatted results
        self.controller.write(":SENS:FUNC 'VOLT:DC'")  # Read DC volts
        self.controller.write("SENS:VOLT:DC:NPLC 1")  # set integration rate (line cycles) to 1
        self.controller.write("SENS:VOLT:DC:RANGE 10")  # select voltage range 1V (ie above 9.99 V => overflow !!)

        self.controller.write(":DISP:ENABLE 0")
        self.controller.write(":TRAC:POIN 10")  # Set to 1024 points in buffer
        self.controller.write(":TRIG:COUNT 1")  # // Set one trigger
        self.controller.write(":TRIG:DELAY 1.000")  # // No (additional) delay between samples
        self.controller.write(":TRIG:SOURCE EXT ")  # // Set trigger source to external
        self.controller.write(":SAMPLE:COUNT 10")  # // Collect 1024 samples
        self.controller.write(":INIT")  # // Start collecting samples now

        time.sleep(2)
        self.controller.write(":DISP:ENABLE 1")  # // Reenable the front panel display
        a = self.controller.write(":TRAC:DATA?")
        print(a)
        return 1

import pyvisa
import os


class tektronix_AFG:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        print(self.rm.list_resources())
        self.AFG = self.rm.open_resource('USB0::0x0699::0x0345::C010328::INSTR')
        self.AFG.timeout = 25000
        # self.AFG.write("*CLS")
        # # Get information about the connected device
        # id = self.AFG.query("*IDN?")
        # if id=="":
        #     id = self.AFG.query("*IDN?")
        self.AFG.clear()
        self.AFG.query("*RST;*OPC?")
        # self.AFG.write("*RST")
        # self.AFG.query("SYST:ERR?")

        # Investigating timeout errors to no avail...
        # https://github.com/asvela/tektronix-func-gen/blob/main/tektronix_func_gen.py
        # self.AFG.write_termination = '\n' # still produces timeout
        # self.AFG.read_termination = '\n' # still produces timeout
        # https://pyvisa.readthedocs.io/en/latest/api/resources.html#pyvisa.resources.USBInstrument
        # https://download.tek.com/manual/AFG3000-Series-Arbitrary-Function-Generator-Programmer-EN.pdf

        # does not work neither :
        # from WeeLab import VisaConnection, Tektronix_AFG3252
        # afg = Tektronix_AFG3252(conn=VisaConnection("USB0::0x0699::0x0345::C010630::INSTR"))
        # afg.do_set_voltage_ch1(5)  # Sets voltage on ch1 to 5 V


        # *OPC? needed to wait just the right amount of time before sending the next cmd (up to timout after 2")
        # requires query() to block the script execution

    def analog_injection(self):
        # pulse config
        self.AFG.query("FUNCTION PULSE;*OPC?")  # not found how to control a channel specitic function mode : alters only currently displayed mode

        # for i in [1,2]:
        i = 1
        self.AFG.query("SOURce%d:PULSe:PERiod 10us;*OPC?"%i)
        self.AFG.query("SOURce%d:PULSe:TRANsition:LEADing 2.5ns;*OPC?"%i)
        self.AFG.query("SOURce%d:PULSe:WIDTh 5us;*OPC?"%i)
        self.AFG.query("SOURce%d:PULSe:TRANsition:TRAiling 6us;*OPC?"%i)
        self.AFG.query("SOURce%d:PULSe:DELay 0s;*OPC?"%i)
        self.AFG.query("SOURce%d:VOLTage:LEVel:IMMediate:LOW 0mV;*OPC?"%i)

        # OUTPut:TRIGger:MODE todo

        self.copy_config_ch1_to_ch2()
        # print("No 50 ohm resistor before injection capacitance => pulser in high impedance mode")

    def ext_trigger(self, frequency_Hz):
        assert frequency_Hz > 1
        assert frequency_Hz <= 120e6
        period_ns = int(1e9/frequency_Hz)
        i = 1
        frequency_Hz = 1e9/period_ns
        print("Ext pulser frequency set to %.1f Hz"%frequency_Hz)

        # pulse config
        self.AFG.query("FUNCTION PULSE;*OPC?")  # not found how to control a channel specitic function mode : alters only currently displayed mode

        self.AFG.query("SOURce%d:PULSe:PERiod %sns;*OPC?" % (i, period_ns))
        self.AFG.query("SOURce%d:PULSe:TRANsition:LEADing 2.5ns;*OPC?" % i)
        self.AFG.query("SOURce%d:PULSe:WIDTh 4ns;*OPC?" % i)
        self.AFG.query("SOURce%d:PULSe:TRANsition:TRAiling 2.5ns;*OPC?" % i)
        self.AFG.query("SOURce%d:PULSe:DELay 0s;*OPC?" % i)
        self.AFG.query("SOURce%d:VOLTage:LEVel:IMMediate:LOW 0mV;*OPC?" % i)
        self.AFG.query("SOURce%d:VOLTage:LEVel:IMMediate:HIGH 1.2V;*OPC?"% i)

        self.copy_config_ch1_to_ch2()
        return frequency_Hz

    def set_voltage_amplitude(self, voltage_high_mV):
        # limits in 50 ohm load impedance
        # x2 for limits in high impedance
        assert voltage_high_mV >= 50 # minimum injectable pulse amplitude
        assert voltage_high_mV <= 5000
        self.AFG.query("SOURce1:VOLTage:LEVel:IMMediate:HIGH %dmV;*OPC?"%voltage_high_mV)
        self.AFG.query("SOURce2:VOLTage:LEVel:IMMediate:HIGH %dmV;*OPC?"%voltage_high_mV)

    def trigger(self):
        self.AFG.write('*TRG')

    def continuous_mode(self):
        for i in [1,2]:
            self.AFG.query("SOURce%d:BURSt:STATe OFF;*OPC?"%i)

    def burst_mode(self, cycles=100):
        assert isinstance(cycles, int)
        # setup burst mode on OUT 1
        # for i in [1,2]:
        i=1
        self.AFG.write("SOURce%d:BURSt:STATe ON"%i)
        self.AFG.query("*OPC?")
        self.AFG.write("SOURce%d:BURSt:MODE TRIGgered"%i)
        self.AFG.query("*OPC?")
        self.AFG.write("SOURce%d:BURSt:NCYCles %d"%(i, cycles))
        self.AFG.query("*OPC?")
        # self.AFG.write("SOURce%d:BURSt:DELay 0s"%i) todo : '-113,"Undefined header; unrecognized command - SOURce1:BURSt:DELay "\n'
        # self.AFG.query("*OPC?")
        self.AFG.query("TRIGger:SEQuence:SOURce EXTERNAL;*OPC?") # manual or trigger by a external pulse self.connected to TTL trigger input
        self.copy_config_ch1_to_ch2()

        # needed to make sure pulses on both channels are synchronous...
        self.AFG.query("FUNCTION SQUARE;*OPC?")
        self.AFG.query("FUNCTION PULSE;*OPC?")

    def ext_trigger_TOT_sweep(self):
        i=1
        cycles=100
        self.AFG.write("SOURce%d:BURSt:STATe ON"%i)
        self.AFG.query("*OPC?")
        self.AFG.write("SOURce%d:BURSt:MODE TRIGgered"%i)
        self.AFG.query("*OPC?")
        self.AFG.write("SOURce%d:BURSt:NCYCles %d"%(i, cycles))
        self.AFG.query("*OPC?")

        self.AFG.query("TRIGger:SEQuence:SOURce EXTERNAL;*OPC?") # manual or trigger by a external pulse self.connected to TTL trigger input
        self.copy_config_ch1_to_ch2()

        # needed to make sure pulses on both channels are synchronous...
        self.AFG.query("FUNCTION SQUARE;*OPC?")
        self.AFG.query("FUNCTION PULSE;*OPC?")

        self.AFG.query("SOURce%d:PULSe:PERiod %sus;*OPC?" % (i, 10))
        self.AFG.query("SOURce%d:PULSe:TRANsition:LEADing 2.5ns;*OPC?" % i)
        self.AFG.query("SOURce%d:PULSe:WIDTh 4ns;*OPC?" % i)
        self.AFG.query("SOURce%d:PULSe:TRANsition:TRAiling 2.5ns;*OPC?" % i)
        self.AFG.query("SOURce%d:PULSe:DELay 0s;*OPC?" % i)
        self.AFG.query("SOURce%d:VOLTage:LEVel:IMMediate:LOW 0mV;*OPC?" % i)
        self.AFG.query("SOURce%d:VOLTage:LEVel:IMMediate:HIGH 1.2V;*OPC?"% i)

    def copy_config_ch1_to_ch2(self):
        self.AFG.write("AFGCONTROL:CSCOPY CH1,CH2")

    def enable_output(self):
        for i in [1,2]:
            self.AFG.query("OUTPut%d:POLarity NORMal;*OPC?"%i)
            self.AFG.query("OUTPUT%d:STATE ON;*OPC?"%i)
            self.AFG.query("OUTPut%d:Impedance 50ohm;*OPC?"%i)

    def close(self):
        self.AFG.close()
        self.rm.close()

class visaController:
    # tested with KEITHLEY 2000 MULTIMETER
    # Agilent 82357B GPIB to USB interface
    #
    # see https://github.com/MarkDing/GPIB-pyvisa?tab=readme-ov-file

    def __init__(self, channel: int):

        rm = pyvisa.ResourceManager()
        # print("Instruments availables : "+[str(r) for r in rm.list_resources()])


        self.keithley = rm.open_resource('GPIB0::'+str(channel)+'::INSTR')


        if self.keithley is None:
            print("Choose among available instruments : ")
            print(rm.list_resources())
            exit()
        else:
            print("self.connected to ", self.keithley.query('*IDN?') )
        self.keithley.timeout = 60000
        # print('*IDN? returned: %s' % idn.rstrip('\n'))

    def get_current_consumption(self, decimal=2):

        self.keithley.write(":FORM:DATA ASCII")  # ASCII formatted results
        self.keithley.write(":SENS:FUNC 'VOLT:DC'")  # Read DC volts
        self.keithley.write("SENS:VOLT:DC:NPLC 1")  # set integration rate (line cycles) to 1
        self.keithley.write("SENS:VOLT:DC:RANGE 1")  # select voltage range 1V (ie above 9.99 V => overflow !!)
        # visaController.keithley.write(":TRIG:DELAY 2.000")  # // No (additional) delay between samples

        self.keithley.write(":ROUT:OPEN:ALL")  # open all channels for scan

        serie_resistance = 0.1  # ohm   on PCB 1% precision

        keithley_ch = 1
        self.keithley.write(":ROUT:CLOS (@" + str(keithley_ch) + ")")  # connect channel
        time.sleep(0.5)
        digital_voltage = float(self.keithley.query("SENSE:DATA?"))
        if digital_voltage<0:
            print("Negative value returned, probably overflow, try to wait more before reading value")
            exit(0)
        digital_current = digital_voltage * 1e3/serie_resistance
        if digital_voltage<0.0015:
            print('Digital conso seems low ! %.3f mV / 0.1 Ohm => %d mA  Make sure jumper on VDDD is removed !'%(digital_voltage, digital_current))
        self.keithley.write(":ROUT:OPEN:ALL")  # open all channels for next

        keithley_ch = 2
        self.keithley.write(":ROUT:CLOS (@" + str(keithley_ch) + ")")  # connect channel
        time.sleep(0.5)
        analog_voltage = float(self.keithley.query("SENSE:DATA?"))
        if analog_voltage<0:
            print("Negative value returned, probably overflow, try to wait more before reading value")
            exit(0)
        analog_current = analog_voltage * 1e3/serie_resistance
        if analog_voltage<0.0035:
            print('Analog conso seems low ! %.3f mV / 0.1 Ohm => %d mA  Make sure jumper on VDDD is removed !'%(analog_voltage, analog_current))

        if decimal==0:
            digital_current = int(digital_current)
            analog_current = int(analog_current)
        else:
            digital_current = round(digital_current, decimal)
            analog_current = round(analog_current, decimal)

        total_power_per_ch=(digital_current+analog_current)*1.2/64
        print("dig %d mA analog %d mA = %.1f mW/ch"%(digital_current, analog_current, total_power_per_ch))
        return digital_current, analog_current

    def setup_DC_voltage(self):
        self.keithley.write(":FORM:DATA ASCII")  # ASCII formatted results
        self.keithley.write(":SENS:FUNC 'VOLT:DC'")  # Read DC volts
        self.keithley.write("SENS:VOLT:DC:NPLC 1")  # set integration rate (line cycles) to 1
        self.keithley.write("SENS:VOLT:DC:RANGE 1")  # select voltage range 1V (ie above 9.99 V => overflow !!)

    def get_channel_voltage(self, keithley_ch):
        self.keithley.write(":ROUT:OPEN:ALL")  # open all channels for scan
        self.keithley.write(":ROUT:CLOS (@" + str(keithley_ch) + ")")  # connect channel
        time.sleep(0.5) # needed time (tested 0.2 was not enough)
        voltage = float(self.keithley.query("SENSE:DATA?"))
        return voltage


    def getDataKeithley0(self, chan_start, *chan_stop):
        # todo : use :trigger:signal instead of :init

        # Indentify the self.connected device
        # print(self.controller.query('*IDN?'))
        self.keithley.write('*RST')  # Suspends triggering

        self.keithley.write(":TRAC:CLE")  # clear the buffer before writing anything there

        # self.controller.write(":FORM:DATA ASCII")  # ASCII formatted results
        # self.controller.write(":SENS:FUNC 'VOLT:DC'")  # Read DC volts
        # self.controller.write("SENS:VOLT:DC:NPLC 1")  # set integration rate (line cycles) to 1
        # self.controller.write("SENS:VOLT:DC:RANGE 10")  # select voltage range 1V (ie above 9.99 V => overflow !!)
        # self.controller.write(":TRIG:DELAY 2.000")  # // No (additional) delay between samples
        self.keithley.write(":ROUT:OPEN:ALL")  # open all channels for scan
        # self.controller.write("*WAIT")
        self.keithley.write(":Trigger:Delay:AUTO 1")

        if chan_stop:  # multi channel wise acquisition
            chan_stop = chan_stop[0]
            buf_size = chan_stop - chan_start + 1

            self.keithley.write(":ROUT:SCAN:LSEL INT")  # select internal scanning

            self.keithley.write(":ROUT:SCAN:INT (@" + str(chan_start) + ":" + str(chan_stop) + ")")  # select channels you want to scan
            # print(self.controller.query("ROUT:SCAN:INT?"))
            self.keithley.write(":TRAC:POIN 3")  # + str(buf_size + 1))  # select buffer size
        else:
            buf_size = 1
            self.keithley.write(":ROUT:CLOSE (@ " + str(chan_start) + ")")  # select the channel you want to scan
            self.keithley.query(":ROUTe:CLOSe:STATe?")
            self.keithley.write(":TRAC:POIN 2")  # select buffer size

        self.keithley.write(":TRACE:FEED SENSE1")  # put raw reading in buffer
        self.keithley.write(":TRACE:FEED:CONT NEXT")  # storage process starts, fills buffer, then stops

        self.keithley.write(":INIT")  # launch measurement trigger
        time.sleep(0.1)

        # exit SCAN mode on Keithley controller
        self.keithley.write(":ROUT:SCAN:LSEL NONE")  # exit SCAN mode, but go to REM mode, so then press LOCAL on front panel
        self.keithley.write(":SYST:KEY 1")  # equivalent to shift key press
        self.keithley.write(":SYST:KEY 29")  # equivalent to scan key press

        # Read buffer
        data = np.array([])
        # for i in range(buf_size):
        newData = self.keithley.query(":TRAC:DATA?")  # read data
        newData = [round(float(m), 4) for m in newData.split(",")]  # keep 4 decimals for each value
        data = np.append(data, np.array(newData))
        print(data)
        pass
        return data


def test_prologix():
    # connect to prologix, use Prologix netfinder.exe program to get ip address on a network
    # prologix_ip = "129.104.89.239"
    prologix_ip = "129.104.89.129"
    prologix = prologixController(prologix_ip)

    # connect to keithley device
    keithley_gpib_port = 16  # (Keithley 2000 Multimeter) look at the device front panel : Shift/GPIB (digit key)/enter : address is displayed

    print(prologix.getDataKeithley(keithley_gpib_port, 7)[0] * 10 ** 3)  # return single value
    # print(prologix.getDataKeithley(keithley_gpib_port, 8) * 10 ** 3)     # return single value
    # print(prologix.getDataKeithley(keithley_gpib_port, 9) * 10 ** 3)     # return single value
    # print(prologix.getDataKeithley(keithley_gpib_port, 7,
    #                                9) * 10 ** 3)  # return array of scanned channels : between 7 and 9

    # # Configuration to connect to agilent power supply   https://www.keysight.com/fr/en/assets/9018-01308/user-manuals/9018-01308.pdf
    # agilent_gpib_port = 14  # (Agilent E3631A Power Supply)
    # prologix.controller.select(agilent_gpib_port)  # (Agilent E3631A Power Supply)
    #
    # print(prologix.controller.query("*idn?"))
    # # powerSupply.write("INST P6V") # select +6V output
    # # powerSupply.write("VOLT 3.5")
    # # powerSupply.write("CURR 1.4") # maximum current drawn
    # prologix.controller.write("OUTPUT ON")
    # prologix.controller.write("OUTPUT OFF")
    # # powerSupply.write("SYSTEM:LOCAL") # Do not work, only for RS-232

def test_pyVisa():
    # v = visaController(16)
    # print(v.get_current_consumption())

    v = tektronix_AFG()
    visaController.burst_mode(cycles=1)
    visaController.set_voltage_amplitude(100)
    visaController.trigger()




def save_temperature(tempo, config):
    config['temperature_'+tempo.mode].append(tempo.temperature_sensor.read_temperature())
    threading.Timer(60 * 30, save_temperature, args=(tempo, config)).start()



if __name__ == "__main__":
    test_prologix()
    test_pyVisa()
