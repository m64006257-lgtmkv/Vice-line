import ctypes
import sys
import os
import time
from ctypes import wintypes

# التحقق من نظام التشغيل
if sys.platform != "win32":
    print("This module requires Windows OS")
    sys.exit(1)

# محاولة استيراد psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    print("⚠ psutil not installed. Some features will be limited.")
    PSUTIL_AVAILABLE = False

# تعريفات Windows API
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

class AdvancedInjector:
    """نظام حقن متقدم لتحميل DLL في GTA VC"""
    
    DLL_PATH = "MultiplayerCore.dll"
    
    @staticmethod
    def find_gta_process() -> tuple:
        """العثور على عملية GTA Vice City"""
        if not PSUTIL_AVAILABLE:
            print("❌ psutil is required for process finding")
            return None, None
        
        gta_names = ["gta-vc.exe", "gta_vc.exe", "vicecity.exe", "GTAVC.exe"]
        
        for proc in psutil.process_iter(['pid', 'name']):
            proc_name = proc.info['name'].lower()
            for gta_name in gta_names:
                if gta_name.lower() in proc_name:
                    return proc.info['pid'], proc.info['name']
        
        return None, None
    
    @staticmethod
    def inject_dll(process_id: int, dll_path: str) -> bool:
        """حقن DLL في العملية المحددة"""
        try:
            # فتح مقبض العملية
            # PROCESS_ALL_ACCESS = 0x1F0FFF
            process_handle = kernel32.OpenProcess(
                0x1F0FFF,  # PROCESS_ALL_ACCESS
                False,
                process_id
            )
            
            if not process_handle:
                print(f"❌ Failed to open process {process_id}")
                return False
            
            # تحويل المسار إلى بايتات
            dll_path_bytes = dll_path.encode('utf-8') + b'\x00'
            dll_path_len = len(dll_path_bytes)
            
            # تخصيص ذاكرة في العملية للـ DLL
            # MEM_COMMIT = 0x1000, PAGE_READWRITE = 0x04
            alloc_addr = kernel32.VirtualAllocEx(
                process_handle,
                None,
                dll_path_len,
                0x1000,  # MEM_COMMIT
                0x04     # PAGE_READWRITE
            )
            
            if not alloc_addr:
                kernel32.CloseHandle(process_handle)
                print("❌ Failed to allocate memory in target process")
                return False
            
            # كتابة مسار الـ DLL في الذاكرة المخصصة
            bytes_written = wintypes.SIZE_T()
            kernel32.WriteProcessMemory(
                process_handle,
                alloc_addr,
                dll_path_bytes,
                dll_path_len,
                ctypes.byref(bytes_written)
            )
            
            if bytes_written.value != dll_path_len:
                kernel32.VirtualFreeEx(process_handle, alloc_addr, 0, 0x8000)  # MEM_RELEASE
                kernel32.CloseHandle(process_handle)
                print("❌ Failed to write DLL path to target process")
                return False
            
            # الحصول على عنوان LoadLibraryA
            kernel32_handle = kernel32.GetModuleHandleA(b"kernel32.dll")
            load_library_addr = kernel32.GetProcAddress(kernel32_handle, b"LoadLibraryA")
            
            # إنشاء thread بعيد لتحميل الـ DLL
            thread_id = wintypes.DWORD()
            thread_handle = kernel32.CreateRemoteThread(
                process_handle,
                None,
                0,
                load_library_addr,
                alloc_addr,
                0,
                ctypes.byref(thread_id)
            )
            
            if not thread_handle:
                kernel32.VirtualFreeEx(process_handle, alloc_addr, 0, 0x8000)
                kernel32.CloseHandle(process_handle)
                print("❌ Failed to create remote thread")
                return False
            
            # انتظار تحميل الـ DLL
            kernel32.WaitForSingleObject(thread_handle, 5000)
            
            # التحقق من نجاح الحقن
            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeThread(thread_handle, ctypes.byref(exit_code))
            
            # تنظيف
            kernel32.CloseHandle(thread_handle)
            kernel32.VirtualFreeEx(process_handle, alloc_addr, 0, 0x8000)
            kernel32.CloseHandle(process_handle)
            
            if exit_code.value == 0:
                print("❌ DLL failed to load (exit code 0)")
                return False
            
            print(f"✅ Successfully injected DLL into process {process_id}")
            print(f"   DLL Handle: 0x{exit_code.value:08X}")
            return True
            
        except Exception as e:
            print(f"❌ Injection error: {e}")
            return False
    
    @staticmethod
    def eject_dll(process_id: int, dll_handle: int) -> bool:
        """إخراج DLL من العملية"""
        try:
            process_handle = kernel32.OpenProcess(0x1F0FFF, False, process_id)
            if not process_handle:
                return False
            
            # الحصول على عنوان FreeLibrary
            kernel32_handle = kernel32.GetModuleHandleA(b"kernel32.dll")
            free_library_addr = kernel32.GetProcAddress(kernel32_handle, b"FreeLibrary")
            
            # إنشاء thread بعيد لتحرير الـ DLL
            thread_id = wintypes.DWORD()
            thread_handle = kernel32.CreateRemoteThread(
                process_handle,
                None,
                0,
                free_library_addr,
                dll_handle,
                0,
                ctypes.byref(thread_id)
            )
            
            if not thread_handle:
                kernel32.CloseHandle(process_handle)
                return False
            
            # انتظار إخراج الـ DLL
            kernel32.WaitForSingleObject(thread_handle, 5000)
            
            # تنظيف
            kernel32.CloseHandle(thread_handle)
            kernel32.CloseHandle(process_handle)
            
            print(f"✅ Successfully ejected DLL from process {process_id}")
            return True
            
        except Exception as e:
            print(f"❌ Ejection error: {e}")
            return False
    
    @staticmethod
    def create_suspended_process(exe_path: str) -> tuple:
        """إنشاء عملية معلقة (لتطبيقات متقدمة)"""
        try:
            startup_info = wintypes.STARTUPINFO()
            process_info = wintypes.PROCESS_INFORMATION()
            
            startup_info.cb = ctypes.sizeof(wintypes.STARTUPINFO)
            
            success = kernel32.CreateProcessW(
                exe_path,
                None,
                None,
                None,
                False,
                0x00000004,  # CREATE_SUSPENDED
                None,
                None,
                ctypes.byref(startup_info),
                ctypes.byref(process_info)
            )
            
            if success:
                return process_info.dwProcessId, process_info.hProcess, process_info.hThread
            return None, None, None
        except Exception as e:
            print(f"Create suspended process error: {e}")
            return None, None, None
    
    @staticmethod
    def hijack_thread(process_id: int) -> bool:
        """اختطاف thread موجود لتنفيذ كود مخصص"""
        try:
            process_handle = kernel32.OpenProcess(0x1F0FFF, False, process_id)
            if not process_handle:
                return False
            
            # TH32CS_SNAPTHREAD = 0x00000004
            snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
            
            class THREADENTRY32(ctypes.Structure):
                _fields_ = [
                    ("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD),
                    ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.DWORD),
                    ("tpDeltaPri", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD)
                ]
            
            thread_entry = THREADENTRY32()
            thread_entry.dwSize = ctypes.sizeof(THREADENTRY32)
            
            # Thread32First
            if kernel32.Thread32First(snapshot, ctypes.byref(thread_entry)):
                target_thread_id = None
                while True:
                    if thread_entry.th32OwnerProcessID == process_id:
                        target_thread_id = thread_entry.th32ThreadID
                        break
                    
                    if not kernel32.Thread32Next(snapshot, ctypes.byref(thread_entry)):
                        break
            
            kernel32.CloseHandle(snapshot)
            
            if target_thread_id:
                # THREAD_ALL_ACCESS = 0x1F03FF
                thread_handle = kernel32.OpenThread(0x1F03FF, False, target_thread_id)
                if thread_handle:
                    kernel32.CloseHandle(thread_handle)
                    return True
            
            return False
            
        except Exception as e:
            print(f"Thread hijack error: {e}")
            return False

# اختبار النظام
if __name__ == "__main__":
    injector = AdvancedInjector()
    
    print("🔍 Looking for GTA Vice City process...")
    pid, name = injector.find_gta_process()
    
    if pid:
        print(f"✅ Found {name} (PID: {pid})")
        
        # التحقق من وجود الـ DLL
        dll_path = os.path.join(os.getcwd(), "MultiplayerCore.dll")
        if os.path.exists(dll_path):
            print(f"📦 Found DLL: {dll_path}")
            
            # الحقن
            if injector.inject_dll(pid, dll_path):
                print("🎉 Injection successful! You can now run the controller.")
                
                # انتظار قليل ثم الاتصال
                time.sleep(2)
                
                # محاولة الاتصال بالتحكم
                try:
                    from CPP_Controller import CPPController
                    controller = CPPController()
                    
                    if controller.connect():
                        if controller.initialize_core():
                            print("🚀 C++ core initialized and ready!")
                            controller.disconnect()
                except ImportError:
                    print("⚠ CPP_Controller not found, skipping controller test")
                except Exception as e:
                    print(f"⚠ Controller test failed: {e}")
            else:
                print("❌ Injection failed")
        else:
            print(f"❌ DLL not found at: {dll_path}")
            print("Please compile MultiplayerCore.dll first!")
    else:
        print("❌ GTA Vice City not found. Please run the game first!")