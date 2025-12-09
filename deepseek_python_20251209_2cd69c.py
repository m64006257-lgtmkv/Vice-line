import ctypes
import win32api
import win32process
import win32con
import psutil
import time
import struct
from ctypes import wintypes
import sys
import os

# تعريفات Windows API
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# تعريف الهياكل
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", wintypes.LPVOID),
        ("AllocationBase", wintypes.LPVOID),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD)
    ]

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", wintypes.LPVOID),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260)
    ]

class GTAVCMemoryManager:
    """مدير ذاكرة متقدم لـ GTA Vice City"""
    
    # أوفسيت الذاكرة الأساسية (سيتم تحديثها ديناميكياً)
    MEMORY_OFFSETS = {
        'base_address': 0x00400000,  # عنوان قاعدة gta-vc.exe
        'player_ped_ptr': 0x00B7CD98,  # مؤشر للاعب الرئيسي
        'camera_ptr': 0x00B6F028,  # مؤشر للكاميرا
        'entity_list': 0x00B74490,  # قائمة الكائنات
        'world_ptr': 0x00B79594,  # مؤشر للعالم
        'game_state': 0x00B7CB54,  # حالة اللعبة
        'fps_limit': 0x006385DC,  # حد الـ FPS
        'vehicles_array': 0x00B74494,  # مصفوفة المركبات
        'peds_array': 0x00B74490,  # مصفوفة المشاة
        'objects_array': 0x00B744A0,  # مصفوفة الكائنات
        'max_entities': 0x00000190,  # أقصى عدد للكائنات (400)
        'entity_size': 0x00000198,  # حجم كل كائن (408 بايت)
    }
    
    # أنواع الكائنات
    ENTITY_TYPES = {
        0: 'VEHICLE',
        1: 'PED',
        2: 'OBJECT',
        3: 'DUMMY'
    }
    
    def __init__(self, process_name="gta-vc.exe"):
        self.process_name = process_name
        self.process_id = None
        self.process_handle = None
        self.base_address = None
        self.modules = {}
        self.is_attached = False
        
    def attach_to_process(self):
        """الارتباط بعملية اللعبة"""
        try:
            # البحث عن ID العملية
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == self.process_name.lower():
                    self.process_id = proc.info['pid']
                    break
            
            if not self.process_id:
                raise Exception(f"Process {self.process_name} not found")
            
            # فتح مقبض للعملية
            self.process_handle = kernel32.OpenProcess(
                win32con.PROCESS_ALL_ACCESS,
                False,
                self.process_id
            )
            
            if not self.process_handle:
                raise Exception(f"Failed to open process {self.process_id}")
            
            # الحصول على وحدات العملية
            self._get_process_modules()
            
            # تحديث أوفسيت الذاكرة بناءً على الإصدار
            self._detect_game_version()
            
            self.is_attached = True
            print(f"✓ Attached to process {self.process_id} at 0x{self.base_address:08X}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to attach to process: {e}")
            return False
    
    def _get_process_modules(self):
        """الحصول على وحدات العملية المحملة"""
        snapshot = kernel32.CreateToolhelp32Snapshot(win32con.TH32CS_SNAPMODULE, self.process_id)
        
        if snapshot == win32con.INVALID_HANDLE_VALUE:
            return
        
        module_entry = MODULEENTRY32()
        module_entry.dwSize = ctypes.sizeof(MODULEENTRY32)
        
        if kernel32.Module32First(snapshot, ctypes.byref(module_entry)):
            while True:
                module_name = module_entry.szModule.decode('ascii', errors='ignore')
                self.modules[module_name] = {
                    'base': module_entry.modBaseAddr,
                    'size': module_entry.modBaseSize,
                    'path': module_entry.szExePath.decode('ascii', errors='ignore')
                }
                
                # تحديد قاعدة gta-vc.exe
                if module_name.lower() == 'gta-vc.exe':
                    self.base_address = module_entry.modBaseAddr
                    self.MEMORY_OFFSETS['base_address'] = self.base_address
                
                if not kernel32.Module32Next(snapshot, ctypes.byref(module_entry)):
                    break
        
        kernel32.CloseHandle(snapshot)
    
    def _detect_game_version(self):
        """كشف نسخة اللعبة وتحديث الأوفست"""
        if not self.base_address:
            return
        
        # قراءة توقيع النسخة من الذاكرة
        try:
            # قراءة أول 64 بايت من الملف التنفيذ
            exe_data = self.read_memory(self.base_address, 64)
            
            # تحليل التوقيع
            if b'\x4D\x5A' in exe_data:  # MZ header
                # GTA VC 1.0
                if b'\x90\x90\x90\x90' in exe_data[0x100:0x110]:
                    self.MEMORY_OFFSETS.update({
                        'player_ped_ptr': 0x00B7CD98,
                        'entity_list': 0x00B74490,
                        'vehicles_array': 0x00B74494,
                        'peds_array': 0x00B74490,
                    })
                    print("✓ Detected: GTA VC v1.0")
                # GTA VC Steam
                elif b'\xE8' in exe_data[0x200:0x210]:
                    self.MEMORY_OFFSETS.update({
                        'player_ped_ptr': 0x00C1D0F8,
                        'entity_list': 0x00C1C690,
                        'vehicles_array': 0x00C1C694,
                        'peds_array': 0x00C1C690,
                    })
                    print("✓ Detected: GTA VC Steam Edition")
        except:
            print("⚠ Could not detect game version, using default offsets")
    
    def read_memory(self, address, size):
        """قراءة من الذاكرة"""
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        
        result = kernel32.ReadProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        
        if result and bytes_read.value == size:
            return buffer.raw
        else:
            raise Exception(f"Failed to read memory at 0x{address:08X}")
    
    def write_memory(self, address, data):
        """الكتابة في الذاكرة"""
        buffer = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t()
        
        result = kernel32.WriteProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            len(data),
            ctypes.byref(bytes_written)
        )
        
        if result and bytes_written.value == len(data):
            return True
        else:
            raise Exception(f"Failed to write memory at 0x{address:08X}")
    
    def read_int(self, address):
        """قراءة عدد صحيح 4 بايت"""
        data = self.read_memory(address, 4)
        return struct.unpack('i', data)[0]
    
    def read_float(self, address):
        """قراءة عدد عشري 4 بايت"""
        data = self.read_memory(address, 4)
        return struct.unpack('f', data)[0]
    
    def read_vector3(self, address):
        """قراءة متجه ثلاثي (X, Y, Z)"""
        data = self.read_memory(address, 12)
        return struct.unpack('fff', data)
    
    def write_int(self, address, value):
        """كتابة عدد صحيح"""
        data = struct.pack('i', value)
        return self.write_memory(address, data)
    
    def write_float(self, address, value):
        """كتابة عدد عشري"""
        data = struct.pack('f', value)
        return self.write_memory(address, data)
    
    def write_vector3(self, address, x, y, z):
        """كتابة متجه ثلاثي"""
        data = struct.pack('fff', x, y, z)
        return self.write_memory(address, data)
    
    def get_player_position(self):
        """الحصول على موقع اللاعب"""
        player_ptr_addr = self.base_address + self.MEMORY_OFFSETS['player_ped_ptr']
        player_ptr = self.read_int(player_ptr_addr)
        
        if player_ptr:
            # موقع اللاعب في الكائن
            pos_offset = 0x14  # إزاحة الموقع في هيكل الكائن
            return self.read_vector3(player_ptr + pos_offset)
        return (0.0, 0.0, 0.0)
    
    def get_player_rotation(self):
        """الحصول على دوران اللاعب"""
        player_ptr_addr = self.base_address + self.MEMORY_OFFSETS['player_ped_ptr']
        player_ptr = self.read_int(player_ptr_addr)
        
        if player_ptr:
            # دوران اللاعب
            rot_offset = 0x20  # إزاحة الدوران
            return self.read_vector3(player_ptr + rot_offset)
        return (0.0, 0.0, 0.0)
    
    def get_player_vehicle(self):
        """الحصول على مركبة اللاعب"""
        player_ptr_addr = self.base_address + self.MEMORY_OFFSETS['player_ped_ptr']
        player_ptr = self.read_int(player_ptr_addr)
        
        if player_ptr:
            # مؤشر المركبة
            vehicle_offset = 0x58C
            vehicle_ptr = self.read_int(player_ptr + vehicle_offset)
            return vehicle_ptr
        return 0
    
    def get_vehicle_position(self, vehicle_ptr):
        """الحصول على موقع المركبة"""
        if vehicle_ptr:
            pos_offset = 0x14
            return self.read_vector3(vehicle_ptr + pos_offset)
        return (0.0, 0.0, 0.0)
    
    def find_free_entity_slot(self):
        """العثور على فتحة كائن فارغة"""
        entity_list_addr = self.base_address + self.MEMORY_OFFSETS['entity_list']
        max_entities = self.MEMORY_OFFSETS['max_entities']
        entity_size = self.MEMORY_OFFSETS['entity_size']
        
        for i in range(max_entities):
            entity_addr = entity_list_addr + (i * entity_size)
            
            # التحقق إذا كانت الفتحة فارغة
            entity_type = self.read_int(entity_addr)
            if entity_type == 0:  # فارغ
                return i, entity_addr
        
        return -1, 0
    
    def create_remote_player(self, player_id, position=(0, 0, 0)):
        """إنشاء لاعب عن بعد في الذاكرة"""
        slot, entity_addr = self.find_free_entity_slot()
        
        if slot == -1:
            raise Exception("No free entity slots available")
        
        # إنشاء كائن مشاة (NPC)
        entity_type = 1  # نوع المشاة
        self.write_int(entity_addr, entity_type)
        
        # تعيين موقع الكائن
        pos_offset = 0x14
        self.write_vector3(entity_addr + pos_offset, *position)
        
        # تعطيل الذكاء الاصطناعي
        ai_offset = 0x530
        self.write_int(entity_addr + ai_offset, 0)  # تعطيل AI
        
        # تعيين معرف اللاعب
        player_id_offset = 0x5C
        self.write_int(entity_addr + player_id_offset, player_id)
        
        # تمكين الكائن
        enabled_offset = 0x18
        self.write_int(entity_addr + enabled_offset, 1)
        
        print(f"✓ Created remote player at slot {slot}, address 0x{entity_addr:08X}")
        return slot, entity_addr
    
    def update_remote_player(self, entity_addr, position, rotation, animation=0):
        """تحديث لاعب عن بعد"""
        if entity_addr:
            # تحديث الموقع
            pos_offset = 0x14
            self.write_vector3(entity_addr + pos_offset, *position)
            
            # تحديث الدوران
            rot_offset = 0x20
            self.write_vector3(entity_addr + rot_offset, *rotation)
            
            # تحديث الحركة
            anim_offset = 0x5A0
            self.write_int(entity_addr + anim_offset, animation)
    
    def destroy_entity(self, entity_addr):
        """تدمير كائن من الذاكرة"""
        if entity_addr:
            # تعطيل الكائن
            enabled_offset = 0x18
            self.write_int(entity_addr + enabled_offset, 0)
            
            # إعادة تعيين النوع
            self.write_int(entity_addr, 0)
            
            print(f"✓ Destroyed entity at 0x{entity_addr:08X}")
    
    def scan_for_pattern(self, pattern, mask):
        """مسح الذاكرة للعثور على نمط معين"""
        # pattern example: b"\x90\x90\x90\x90\xE8"
        # mask example: "xxxx?"
        
        # هذه وظيفة متقدمة تحتوي على كود مسح حقيقي
        # سيتم تبسيطها هنا لأغراض التوضيح
        
        modules = self._get_executable_sections()
        found_addresses = []
        
        for module_name, module_info in modules.items():
            try:
                data = self.read_memory(module_info['base'], module_info['size'])
                
                # البحث عن النمط
                pos = 0
                while pos < len(data):
                    match = True
                    for i, (p, m) in enumerate(zip(pattern, mask)):
                        if m == 'x' and data[pos + i] != p:
                            match = False
                            break
                    
                    if match:
                        found_addr = module_info['base'] + pos
                        found_addresses.append(found_addr)
                    
                    pos += 1
                    
            except:
                continue
        
        return found_addresses
    
    def _get_executable_sections(self):
        """الحصول على أقسام الذاكرة القابلة للتنفيذ"""
        sections = {}
        
        for module_name, module_info in self.modules.items():
            sections[module_name] = {
                'base': module_info['base'],
                'size': module_info['size']
            }
        
        return sections
    
    def inject_dll(self, dll_path):
        """حقن DLL في عملية اللعبة"""
        # تحويل المسار إلى بايتات
        dll_path_bytes = dll_path.encode('utf-8') + b'\x00'
        
        # تخصيص ذاكرة في العملية للـ DLL
        alloc_addr = kernel32.VirtualAllocEx(
            self.process_handle,
            None,
            len(dll_path_bytes),
            win32con.MEM_COMMIT | win32con.MEM_RESERVE,
            win32con.PAGE_READWRITE
        )
        
        if not alloc_addr:
            raise Exception("Failed to allocate memory for DLL path")
        
        # كتابة مسار الـ DLL في الذاكرة المخصصة
        self.write_memory(alloc_addr, dll_path_bytes)
        
        # الحصول على عنوان LoadLibraryA
        kernel32_handle = kernel32.GetModuleHandleA(b"kernel32.dll")
        load_library_addr = kernel32.GetProcAddress(kernel32_handle, b"LoadLibraryA")
        
        # إنشاء thread بعيد
        thread_id = wintypes.DWORD()
        thread_handle = kernel32.CreateRemoteThread(
            self.process_handle,
            None,
            0,
            ctypes.cast(load_library_addr, ctypes.c_void_p),
            alloc_addr,
            0,
            ctypes.byref(thread_id)
        )
        
        if not thread_handle:
            # تحرير الذاكرة
            kernel32.VirtualFreeEx(
                self.process_handle,
                alloc_addr,
                0,
                win32con.MEM_RELEASE
            )
            raise Exception("Failed to create remote thread")
        
        # انتظار تحميل الـ DLL
        kernel32.WaitForSingleObject(thread_handle, 5000)
        
        # تنظيف
        kernel32.CloseHandle(thread_handle)
        kernel32.VirtualFreeEx(
            self.process_handle,
            alloc_addr,
            0,
            win32con.MEM_RELEASE
        )
        
        print(f"✓ Injected DLL: {dll_path}")
        return True
    
    def detach(self):
        """فك الارتباط بالعملية"""
        if self.process_handle:
            kernel32.CloseHandle(self.process_handle)
            self.process_handle = None
        
        self.is_attached = False
        print("✓ Detached from process")

# اختبار النظام
if __name__ == "__main__":
    # اختبار نظام إدارة الذاكرة
    mem = GTAVCMemoryManager()
    
    if mem.attach_to_process():
        try:
            # قراءة موقع اللاعب
            pos = mem.get_player_position()
            print(f"Player Position: X={pos[0]:.2f}, Y={pos[1]:.2f}, Z={pos[2]:.2f}")
            
            # قراءة دوران اللاعب
            rot = mem.get_player_rotation()
            print(f"Player Rotation: X={rot[0]:.2f}, Y={rot[1]:.2f}, Z={rot[2]:.2f}")
            
            # إنشاء لاعب تجريبي عن بعد
            try:
                slot, entity_addr = mem.create_remote_player(
                    player_id=1001,
                    position=(100.0, 200.0, 10.0)
                )
                
                # تحديث موقع اللاعب التجريبي
                time.sleep(1)
                mem.update_remote_player(
                    entity_addr=entity_addr,
                    position=(105.0, 205.0, 10.0),
                    rotation=(0.0, 0.0, 90.0)
                )
                
                time.sleep(2)
                
                # تدمير اللاعب التجريبي
                mem.destroy_entity(entity_addr)
                
            except Exception as e:
                print(f"Remote player test failed: {e}")
            
        finally:
            mem.detach()
    else:
        print("Make sure GTA Vice City is running!")