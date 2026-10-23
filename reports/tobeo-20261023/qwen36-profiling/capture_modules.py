"""Read Windows module load addresses for offline symbolization of our engine child."""
import ctypes as C
from ctypes import wintypes as W


class ModuleInfo(C.Structure):
    _fields_=[('base',C.c_void_p),('size',W.DWORD),('entry',C.c_void_p)]


def modules(pid):
    kernel=C.WinDLL('kernel32',use_last_error=True)
    psapi=C.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE]
    psapi.EnumProcessModulesEx.argtypes=[W.HANDLE,C.POINTER(C.c_void_p),W.DWORD,C.POINTER(W.DWORD),W.DWORD]
    psapi.GetModuleInformation.argtypes=[W.HANDLE,C.c_void_p,C.POINTER(ModuleInfo),W.DWORD]
    psapi.GetModuleFileNameExW.argtypes=[W.HANDLE,C.c_void_p,W.LPWSTR,W.DWORD]
    process=kernel.OpenProcess(0x410,False,pid)
    if not process:raise C.WinError(C.get_last_error())
    try:
        handles=(C.c_void_p*1024)();needed=W.DWORD()
        if not psapi.EnumProcessModulesEx(process,handles,C.sizeof(handles),C.byref(needed),3):raise C.WinError(C.get_last_error())
        if needed.value>C.sizeof(handles):raise RuntimeError('Module buffer too small')
        result=[]
        for handle in handles[:needed.value//C.sizeof(C.c_void_p)]:
            name=C.create_unicode_buffer(32768);info=ModuleInfo()
            if not psapi.GetModuleFileNameExW(process,handle,name,len(name)):raise C.WinError(C.get_last_error())
            if not psapi.GetModuleInformation(process,handle,C.byref(info),C.sizeof(info)):raise C.WinError(C.get_last_error())
            result.append({'path':name.value,'base':info.base,'size':info.size})
        return result
    finally:kernel.CloseHandle(process)
