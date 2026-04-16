
import logging
from logging.handlers import RotatingFileHandler
from sds_globalSettings import ConsoleAlertLogPath, ConsoleLogPath

#levelName=State
'''A global Logging level (GLL) is defined as part of the setup
If logging_level <= GLL:
Log
Else:
    pass
If I set GLL to 90 everything is logged, if I set to 10 only logging messages 0&10 are logged.
Logging_level=0 (for all critical issues (Asserts, CRITICAL)
Logging_level=10 (for all normal INFO & WARNING)
Logging_level=20 onwards (for code debug tracing, this will depend on the programmer decision)'''

def loggerArgs(element,elementName,loglevel,action):
    loggerArgs={}
    loggerArgs['element']=element
    loggerArgs['elementname']=elementName
    loggerArgs['LogLevel']=loglevel
    loggerArgs['action']=action
    return loggerArgs


def init_CONlogger(name):
    return_values = []
    logger = logging.getLogger(name+"C")
    log_format = '@%(asctime)s @%(message)s'
    handler = RotatingFileHandler(ConsoleLogPath,maxBytes=1000000,backupCount=4)
    logger_format=logging.Formatter(fmt=log_format,datefmt="%d/%m/%Y-%H:%M:%S")
    handler.setFormatter(logger_format)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return_values.append(logger)
    
    alerts_file = logging.FileHandler(ConsoleAlertLogPath)
    #logger_formatter = logging.Formatter(fmt=log_format,datefmt="%d/%m/%Y-%H:%M:%S")
    #alerts_file.setFormatter(logger_formatter)
    logger = logging.getLogger(name+"A")
    logger.addHandler(alerts_file)
    logger.setLevel(logging.ERROR)
    return_values.append(logger)
    return return_values
