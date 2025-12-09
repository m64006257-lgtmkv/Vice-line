import socket
import struct
import json
import time
from enum import IntEnum
from typing import Tuple, Optional, Dict, Any

# تعريفات الأوامر
class ControlCommand(IntEnum):
    CMD_INIT = 1
    CMD_SHUTDOWN = 2
    CMD_UPDATE_CONFIG = 3
    CMD_SEND_CHAT = 4
    CMD_GET_STATUS = 5
    CMD_CREATE_PLAYER = 6
    CMD_REMOVE_PLAYER = 7
    CMD_UPDATE_PLAYER = 8
    CMD_READ_MEMORY = 9
    CMD_WRITE_MEMORY = 10

class CPPController:
    """متحكم في نواة C++ المحقونة"""
    
    def __init__(self, port=52525):
        self.port = port
        self.socket = None
        self.connected = False
        self.memory_cache = {}
        
    def connect(self) -> bool:
        """الاتصال بخادم التحكم في C++"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect(('127.0.0.1', self.port))
            self.connected = True
            print(f"✅ Connected to C++ core on port {self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to C++ core: {e}")
            return False
    
    def disconnect(self):
        """قطع الاتصال"""
        if self.socket:
            self.socket.close()
            self.socket = None
        self.connected = False
    
    def _send_command(self, command: ControlCommand, data: bytes = b'') -> Tuple[bool, bytes]:
        """إرسال أمر واستقبال الرد"""
        if not self.connected and not self.connect():
            return False, b''
        
        try:
            # بناء الحزمة: 4 بايت للأمر + البيانات
            packet = struct.pack('<I', command.value) + data
            
            # الإرسال
            self.socket.sendall(packet)
            
            # استقبال الرد
            header = self._recv_exact(12)  # 12 بايت للرأس
            if len(header) < 12:
                return False, b''
            
            # فك الرأس
            response_cmd, status, data_size = struct.unpack('<III', header)
            
            # استقبال البيانات إذا كانت موجودة
            response_data = b''
            if data_size > 0:
                response_data = self._recv_exact(data_size)
            
            return (status == 1, response_data)
            
        except Exception as e:
            print(f"Command error: {e}")
            self.connected = False
            return False, b''
    
    def _recv_exact(self, size: int) -> bytes:
        """استقبال عدد محدد من البايتات"""
        data = b''
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        return data
    
    def initialize_core(self) -> bool:
        """تهيئة نواة C++"""
        success, response = self._send_command(ControlCommand.CMD_INIT)
        if success:
            print("✅ C++ core initialized")
        return success
    
    def shutdown_core(self) -> bool:
        """إيقاف نواة C++"""
        success, _ = self._send_command(ControlCommand.CMD_SHUTDOWN)
        if success:
            print("✅ C++ core shutdown")
        return success
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """الحصول على حالة النظام"""
        success, response = self._send_command(ControlCommand.CMD_GET_STATUS)
        if success and response:
            try:
                return json.loads(response.decode('utf-8'))
            except:
                pass
        return None
    
    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """قراءة من الذاكرة"""
        # بناء البيانات: العنوان + الحجم
        data = struct.pack('<II', address, size)
        success, response = self._send_command(ControlCommand.CMD_READ_MEMORY, data)
        
        if success:
            return response
        return None
    
    def read_memory_int(self, address: int) -> Optional[int]:
        """قراءة عدد صحيح من الذاكرة"""
        data = self.read_memory(address, 4)
        if data and len(data) >= 4:
            return struct.unpack('<i', data)[0]
        return None
    
    def read_memory_float(self, address: int) -> Optional[float]:
        """قراءة عدد عشري من الذاكرة"""
        data = self.read_memory(address, 4)
        if data and len(data) >= 4:
            return struct.unpack('<f', data)[0]
        return None
    
    def read_memory_vector3(self, address: int) -> Optional[Tuple[float, float, float]]:
        """قراءة متجه ثلاثي من الذاكرة"""
        data = self.read_memory(address, 12)
        if data and len(data) >= 12:
            return struct.unpack('<fff', data)
        return None
    
    def write_memory(self, address: int, data: bytes) -> bool:
        """كتابة في الذاكرة"""
        # بناء البيانات: العنوان + حجم البيانات + البيانات
        header = struct.pack('<II', address, len(data))
        success, _ = self._send_command(ControlCommand.CMD_WRITE_MEMORY, header + data)
        return success
    
    def write_memory_int(self, address: int, value: int) -> bool:
        """كتابة عدد صحيح في الذاكرة"""
        data = struct.pack('<i', value)
        return self.write_memory(address, data)
    
    def write_memory_float(self, address: int, value: float) -> bool:
        """كتابة عدد عشري في الذاكرة"""
        data = struct.pack('<f', value)
        return self.write_memory(address, data)
    
    def write_memory_vector3(self, address: int, x: float, y: float, z: float) -> bool:
        """كتابة متجه ثلاثي في الذاكرة"""
        data = struct.pack('<fff', x, y, z)
        return self.write_memory(address, data)
    
    def create_remote_player(self, player_id: int, x: float, y: float, z: float) -> Optional[int]:
        """إنشاء لاعب عن بعد"""
        data = struct.pack('<Ifff', player_id, x, y, z)
        success, response = self._send_command(ControlCommand.CMD_CREATE_PLAYER, data)
        
        if success and len(response) >= 4:
            entity_addr = struct.unpack('<I', response[:4])[0]
            print(f"✅ Created remote player {player_id} at 0x{entity_addr:08X}")
            return entity_addr
        
        return None
    
    def update_remote_player(self, player_id: int, 
                           position: Tuple[float, float, float],
                           rotation: Tuple[float, float, float]) -> bool:
        """تحديث لاعب عن بعد"""
        x, y, z = position
        rx, ry, rz = rotation
        
        data = struct.pack('<Iffffff', player_id, x, y, z, rx, ry, rz)
        success, _ = self._send_command(ControlCommand.CMD_UPDATE_PLAYER, data)
        
        if success:
            print(f"✅ Updated player {player_id} position")
        
        return success
    
    def get_player_position(self, entity_address: int) -> Optional[Tuple[float, float, float]]:
        """الحصول على موقع لاعب"""
        return self.read_memory_vector3(entity_address + 0x14)
    
    def get_local_player_position(self) -> Optional[Tuple[float, float, float]]:
        """الحصول على موقع اللاعب المحلي"""
        # قراءة مؤشر اللاعب أولاً
        player_ptr = self.read_memory_int(0x00400000 + 0xB7CD98)  # أوفسيت افتراضي
        if player_ptr:
            return self.get_player_position(player_ptr)
        return None
    
    def scan_for_pattern(self, pattern: bytes, mask: str) -> list:
        """مسح الذاكرة للعثور على نمط"""
        # هذا كود متقدم للمسح - يمكن تطويره
        found_addresses = []
        
        # قراءة أقسام الذاكرة
        # هذه وظيفة متقدمة تحتاج إلى تحسين
        return found_addresses
    
    def hotpatch_function(self, address: int, new_code: bytes) -> bool:
        """تعديل دالة في الذاكرة (Hotpatch)"""
        try:
            # حفظ التعليمات الأصلية
            original_size = len(new_code)
            original_bytes = self.read_memory(address, original_size)
            
            if not original_bytes:
                return False
            
            # تعديل صلاحيات الذاكرة
            old_protect = self.change_memory_protection(address, original_size, 0x40)  # PAGE_EXECUTE_READWRITE
            
            # كتابة الكود الجديد
            success = self.write_memory(address, new_code)
            
            # استعادة الصلاحيات
            self.change_memory_protection(address, original_size, old_protect)
            
            return success
            
        except Exception as e:
            print(f"Hotpatch error: {e}")
            return False
    
    def change_memory_protection(self, address: int, size: int, new_protect: int) -> int:
        """تغيير صلاحيات الذاكرة"""
        # هذه وظيفة متقدمة تحتاج إلى دعم في C++
        # سيتم تنفيذها في النسخة القادمة
        return 0
    
    def dump_memory_region(self, start: int, size: int, filename: str) -> bool:
        """تفريغ منطقة من الذاكرة إلى ملف"""
        try:
            data = self.read_memory(start, size)
            if data:
                with open(filename, 'wb') as f:
                    f.write(data)
                print(f"✅ Dumped memory 0x{start:08X}-0x{start+size:08X} to {filename}")
                return True
        except Exception as e:
            print(f"Memory dump error: {e}")
        return False

# اختبار النظام
if __name__ == "__main__":
    controller = CPPController()
    
    if controller.connect():
        # تهيئة النواة
        if controller.initialize_core():
            # الحصول على حالة النظام
            status = controller.get_status()
            if status:
                print(f"System status: {json.dumps(status, indent=2)}")
            
            # اختبار قراءة الذاكرة
            test_addr = 0x00400000  # عنوان قاعدة GTA VC
            test_data = controller.read_memory(test_addr, 64)
            if test_data:
                print(f"Read {len(test_data)} bytes from 0x{test_addr:08X}")
            
            # إنشاء لاعب تجريبي
            entity_addr = controller.create_remote_player(
                player_id=1001,
                x=100.0,
                y=200.0,
                z=10.0
            )
            
            if entity_addr:
                # تحديث موقع اللاعب التجريبي
                time.sleep(1)
                controller.update_remote_player(
                    player_id=1001,
                    position=(105.0, 205.0, 10.0),
                    rotation=(0.0, 0.0, 90.0)
                )
                
                # قراءة موقع اللاعب
                pos = controller.get_player_position(entity_addr)
                if pos:
                    print(f"Player position: X={pos[0]:.2f}, Y={pos[1]:.2f}, Z={pos[2]:.2f}")
            
            # إيقاف النواة
            controller.shutdown_core()
        
        controller.disconnect()
    else:
        print("Make sure GTA VC is running and C++ core is injected!")