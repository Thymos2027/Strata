"""Resolve recorded engine instruction pointers against its local matching PDB only."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path


class SymbolInfo(C.Structure):
    _fields_=[('SizeOfStruct',W.ULONG),('TypeIndex',W.ULONG),('Reserved',C.c_ulonglong*2),
              ('Index',W.ULONG),('Size',W.ULONG),('ModBase',C.c_ulonglong),('Flags',W.ULONG),
              ('Value',C.c_ulonglong),('Address',C.c_ulonglong),('Register',W.ULONG),
              ('Scope',W.ULONG),('Tag',W.ULONG),('NameLen',W.ULONG),('MaxNameLen',W.ULONG),('Name',W.WCHAR*1)]


class LineInfo(C.Structure):
    _fields_=[('SizeOfStruct',W.DWORD),('Key',C.c_void_p),('LineNumber',W.DWORD),
              ('FileName',W.LPWSTR),('Address',C.c_ulonglong)]


class Resolver:
    def __init__(self,image,base,size):
        self.dbg=C.WinDLL('dbghelp',use_last_error=True)
        kernel=C.WinDLL('kernel32');kernel.GetCurrentProcess.restype=W.HANDLE
        self.process=kernel.GetCurrentProcess()
        self.dbg.SymInitializeW.argtypes=[W.HANDLE,W.LPCWSTR,W.BOOL]
        self.dbg.SymSetOptions.argtypes=[W.DWORD]
        self.dbg.SymLoadModuleExW.argtypes=[W.HANDLE,W.HANDLE,W.LPCWSTR,W.LPCWSTR,C.c_ulonglong,W.DWORD,C.c_void_p,W.DWORD]
        self.dbg.SymLoadModuleExW.restype=C.c_ulonglong
        self.dbg.SymFromAddrW.argtypes=[W.HANDLE,C.c_ulonglong,C.POINTER(C.c_ulonglong),C.POINTER(SymbolInfo)]
        self.dbg.SymGetLineFromAddrW64.argtypes=[W.HANDLE,C.c_ulonglong,C.POINTER(W.DWORD),C.POINTER(LineInfo)]
        self.dbg.SymCleanup.argtypes=[W.HANDLE]
        self.dbg.SymSetOptions(0x2|0x4|0x10|0x200|0x400|0x80000|0x1000)
        if not self.dbg.SymInitializeW(self.process,str(Path(image).parent),False):raise C.WinError(C.get_last_error())
        self.base=self.dbg.SymLoadModuleExW(self.process,None,str(image),None,base,size,None,0)
        if not self.base:
            self.close();raise C.WinError(C.get_last_error())

    def lookup(self,address):
        buffer=C.create_string_buffer(C.sizeof(SymbolInfo)+4096*2)
        pointer=C.cast(buffer,C.POINTER(SymbolInfo))
        pointer.contents.SizeOfStruct=C.sizeof(SymbolInfo);pointer.contents.MaxNameLen=4096
        displacement=C.c_ulonglong()
        if not self.dbg.SymFromAddrW(self.process,address,C.byref(displacement),pointer):return None
        symbol=pointer.contents
        name=C.wstring_at(C.addressof(symbol)+SymbolInfo.Name.offset,symbol.NameLen)
        result={'name':name,'displacement':displacement.value,'symbol_address':symbol.Address}
        line=LineInfo();line.SizeOfStruct=C.sizeof(LineInfo);offset=W.DWORD()
        if self.dbg.SymGetLineFromAddrW64(self.process,address,C.byref(offset),C.byref(line)):
            result['source_file']=Path(line.FileName).name;result['source_line']=line.LineNumber
        return result

    def close(self):self.dbg.SymCleanup(self.process)
