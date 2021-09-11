from ctypes import *
from dwfconstants import *

dwf = cdll.LoadLibrary("libdwf.so")
hdwf = c_int()

dwf.FDwfParamSet(DwfParamOnClose, c_int(0)) # 0 = run, 1 = stop, 2 = shutdown
print("Opening first device")
dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

if hdwf.value == hdwfNone.value:
    print("failed to open device")
    quit()
print(f'{hdwf=}')

dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0))
# set up analog IO channel nodes
# enable positive supply
dwf.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(0), c_double(True))
# set voltage to 1.2 V
dwf.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(1), c_double(1.2))
# master enable
dwf.FDwfAnalogIOEnableSet(hdwf, c_int(True))
dwf.FDwfAnalogIOConfigure(hdwf)

dwf.FDwfDeviceClose(hdwf)