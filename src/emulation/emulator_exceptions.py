

class EmulatorException (Exception) :
    pass

# <fpga>

class WordNotEmulatedError (Exception) :
    pass

class WordNotDefinedError (Exception) :
    pass

class WordNotWritableError (Exception) :
    pass

# </fpga>

# <slow_control_master>

class UnknownSlowControlCommandError (Exception) :
    pass

class ReadFifoUnderflowError (Exception) :
    pass

class ReadCommandError (Exception) :
    pass

# </slow_control_master>

# <slow_control_slave>

class SlowControlRegisterNotDefined (Exception) :
    pass

class SlowControlRegisterNotWritable (Exception) :
    pass

class SlowControlRegisterNotEmulated (Exception) :
    pass

# </slow_control_slave>


