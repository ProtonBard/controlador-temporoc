
from src.emulation.emulator_exceptions import SlowControlRegisterNotDefined
from src.emulation.emulator_exceptions import SlowControlRegisterNotWritable
from src.emulation.emulator_exceptions import SlowControlRegisterNotEmulated
from slow_control_registers        import SlowControlRegisters

class SlowControlSlaveEmulator () :

    def __init__ (self) -> None :
        # configuration registers
        self.registers = SlowControlRegisters()
        # slow control registers
        self.subaddress : int = 0 # aka lsb
        self.address    : int = 0 # aka msb
        return

    def write (self, index : int, data : int) -> None :
        assert isinstance(index, int)
        assert isinstance(data, int)
        assert index >=   0
        assert index <    8
        assert data  >=   0
        assert data  <  256
        match index :
            case 0 : self.subaddress = data
            case 1 : self.address    = data
            case 2 :
                self.registers.set(self.address, self.subaddress, data)
                print(f"[{self.address},{self.subaddress}] <= {data}")
            case 3 : raise SlowControlRegisterNotEmulated()
            case 7 : raise SlowControlRegisterNotWritable()
            case _ : raise SlowControlRegisterNotDefined()
        return

    def read (self, index : int) -> int :
        assert isinstance(index, int)
        assert index >= 0
        assert index <  8
        match index :
            case 0 : return self.subaddress
            case 1 : return self.address
            case 2 :
                data : int = self.registers.get(self.address, self.subaddress)
                print(f"[{self.address},{self.subaddress}] => {data}")
                return data
            case 3 : raise SlowControlRegisterNotEmulated()
            case 7 : return 0
            case _ : raise SlowControlRegisterNotDefined()
        return 0

    pass


