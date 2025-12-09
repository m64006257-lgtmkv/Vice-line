import os
import sys
import json
import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# التحقق من نظام التشغيل
if sys.platform != "win32":
    print("This system requires Windows OS")
    sys.exit(1)

# محاولة استيراد المكونات مع بدائل
try:
    from AdvancedInjector import AdvancedInjector
    ADVANCED_INJECTOR_AVAILABLE = True
except ImportError:
    print("⚠ AdvancedInjector not found, using fallback")
    ADVANCED_INJECTOR_AVAILABLE = False
    
    class AdvancedInjector:
        @staticmethod
        def find_gta_process():
            return None, None
        @staticmethod
        def inject_dll(pid, dll_path):
            return False

try:
    from CPP_Controller import CPPController
    CPP_CONTROLLER_AVAILABLE = True
except ImportError:
    print("⚠ CPP_Controller not found, using fallback")
    CPP_CONTROLLER_AVAILABLE = False
    
    class CPPController:
        def __init__(self, port=52525):
            self.port = port
            self.connected = False
        def connect(self):
            return False
        def disconnect(self):
            pass
        def initialize_core(self):
            return False
        def shutdown_core(self):
            return False
        def get_status(self):
            return None
        def create_remote_player(self, player_id, x, y, z):
            return None
        def update_remote_player(self, player_id, position, rotation):
            return False
        def get_local_player_position(self):
            return None

try:
    from MemoryInjector import GTAVCMemoryManager
    MEMORY_INJECTOR_AVAILABLE = True
except ImportError:
    print("⚠ MemoryInjector not found, using fallback")
    MEMORY_INJECTOR_AVAILABLE = False
    
    class GTAVCMemoryManager:
        def __init__(self):
            self.is_attached = False
        def attach_to_process(self):
            return False
        def get_player_position(self):
            return (0.0, 0.0, 0.0)
        def get_player_rotation(self):
            return (0.0, 0.0, 0.0)
        def detach(self):
            pass

class SystemMode(Enum):
    STANDALONE = "standalone"      # Python فقط
    HYBRID = "hybrid"              # Python + C++ (موصى به)
    CPP_ONLY = "cpp_only"          # C++ فقط

@dataclass
class PlayerInfo:
    id: int
    name: str
    entity_address: int
    position: Tuple[float, float, float]
    last_update: float
    is_local: bool = False

class UnifiedMultiplayerSystem:
    """النظام الموحد: Python + C++"""
    
    def __init__(self, mode: SystemMode = SystemMode.HYBRID):
        self.mode = mode
        self.is_host = False
        self.running = False
        
        # المكونات
        self.injector = AdvancedInjector() if ADVANCED_INJECTOR_AVAILABLE else None
        self.cpp_controller = None
        self.memory_manager = None
        
        # حالة النظام
        self.players: Dict[int, PlayerInfo] = {}
        self.local_player_id = os.getpid()
        self.game_pid = None
        
        # خيوط العمل
        self.cpp_thread = None
        self.sync_thread = None
        self.network_thread = None
        
        # إعدادات
        self.sync_rate = 20  # Hz
        self.network_port = 5192
        self.control_port = 52525
        
        print(f"🚀 Initializing Unified Multiplayer System ({mode.value})")
    
    def initialize(self, as_host: bool = True) -> bool:
        """تهيئة النظام"""
        print("🔧 Initializing system components...")
        
        self.is_host = as_host
        
        try:
            # الخطوة 1: العثور على لعبة GTA VC
            print("🔍 Looking for GTA Vice City...")
            if self.injector:
                self.game_pid, game_name = self.injector.find_gta_process()
            else:
                # محاولة البحث يدوياً
                import psutil
                for proc in psutil.process_iter(['pid', 'name']):
                    name = proc.info['name'].lower()
                    if 'gta' in name or 'vice' in name or 'vc' in name:
                        self.game_pid = proc.info['pid']
                        game_name = proc.info['name']
                        break
                else:
                    self.game_pid = None
                    game_name = None
            
            if not self.game_pid:
                print("❌ GTA Vice City not running!")
                return False
            
            print(f"✅ Found {game_name} (PID: {self.game_pid})")
            
            # الخطوة 2: اختيار وضع التشغيل
            if self.mode == SystemMode.HYBRID or self.mode == SystemMode.CPP_ONLY:
                if not self._initialize_cpp_core():
                    if self.mode == SystemMode.CPP_ONLY:
                        print("❌ C++ core required but failed to initialize!")
                        return False
                    else:
                        print("⚠ Falling back to Python-only mode")
                        self.mode = SystemMode.STANDALONE
            
            # الخطوة 3: تهيئة مدير الذاكرة
            if self.mode == SystemMode.STANDALONE or self.mode == SystemMode.HYBRID:
                if not self._initialize_memory_manager():
                    print("⚠ Memory manager initialization failed, continuing without it")
            
            # الخطوة 4: بدء الأنظمة
            self._start_subsystems()
            
            print("✅ System initialized successfully!")
            print(f"   Mode: {self.mode.value}")
            print(f"   Role: {'Host' if self.is_host else 'Client'}")
            
            self.running = True
            return True
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            self.shutdown()
            return False
    
    def _initialize_cpp_core(self) -> bool:
        """تهيئة نواة C++"""
        print("🔧 Initializing C++ core...")
        
        if not CPP_CONTROLLER_AVAILABLE:
            print("❌ C++ controller not available")
            return False
        
        # التحقق من وجود الـ DLL
        dll_path = os.path.join(os.getcwd(), "MultiplayerCore.dll")
        if not os.path.exists(dll_path):
            print(f"❌ C++ DLL not found: {dll_path}")
            return False
        
        # حقن الـ DLL
        print(f"📦 Injecting {os.path.basename(dll_path)}...")
        if self.injector and not self.injector.inject_dll(self.game_pid, dll_path):
            print("❌ Failed to inject C++ DLL")
            return False
        
        # انتظار تحميل الـ DLL
        time.sleep(2)
        
        # الاتصال بخادم التحكم
        self.cpp_controller = CPPController(self.control_port)
        
        if not self.cpp_controller.connect():
            print("❌ Failed to connect to C++ control server")
            return False
        
        # تهيئة النواة
        if not self.cpp_controller.initialize_core():
            print("❌ Failed to initialize C++ core")
            return False
        
        # الحصول على حالة النظام
        status = self.cpp_controller.get_status()
        if status:
            print(f"📊 C++ Core Status: {json.dumps(status, indent=2)}")
        
        print("✅ C++ core initialized")
        return True
    
    def _initialize_memory_manager(self) -> bool:
        """تهيئة مدير الذاكرة Python"""
        print("🔧 Initializing Python memory manager...")
        
        if not MEMORY_INJECTOR_AVAILABLE:
            print("❌ Memory injector not available")
            return False
        
        self.memory_manager = GTAVCMemoryManager()
        
        if not self.memory_manager.attach_to_process():
            print("❌ Failed to attach to GTA VC process")
            return False
        
        # قراءة موقع اللاعب للتأكد من الاتصال
        position = self.memory_manager.get_player_position()
        if position:
            print(f"📍 Local player position: {position}")
        
        print("✅ Python memory manager initialized")
        return True
    
    def _start_subsystems(self):
        """بدء الأنظمة الفرعية"""
        print("🚀 Starting subsystems...")
        
        # بدء خيط التزامن
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="SyncThread"
        )
        self.sync_thread.start()
        
        print("✅ Subsystems started")
    
    def _sync_loop(self):
        """حلقة مزامنة البيانات"""
        print("🔄 Starting sync loop...")
        
        sync_interval = 1.0 / self.sync_rate
        
        while self.running:
            try:
                # تحديث بيانات اللاعب المحلي
                self._update_local_player()
                
                # مزامنة مع اللاعبين الآخرين
                self._sync_with_remote_players()
                
                # انتظار للمعدل المطلوب
                time.sleep(sync_interval)
                
            except Exception as e:
                print(f"Sync error: {e}")
                time.sleep(1)
    
    def _update_local_player(self):
        """تحديث بيانات اللاعب المحلي"""
        player_data = self._get_local_player_data()
        
        if player_data:
            # تخزين بيانات اللاعب المحلي
            if self.local_player_id not in self.players:
                self.players[self.local_player_id] = PlayerInfo(
                    id=self.local_player_id,
                    name="Local Player",
                    entity_address=0,
                    position=player_data['position'],
                    last_update=time.time(),
                    is_local=True
                )
            else:
                self.players[self.local_player_id].position = player_data['position']
                self.players[self.local_player_id].last_update = time.time()
    
    def _get_local_player_data(self) -> Optional[Dict]:
        """الحصول على بيانات اللاعب المحلي"""
        try:
            if self.mode == SystemMode.CPP_ONLY and self.cpp_controller:
                # استخدام C++ للحصول على البيانات
                position = self.cpp_controller.get_local_player_position()
                if position:
                    return {
                        'position': position,
                        'rotation': (0, 0, 0),
                        'velocity': (0, 0, 0),
                        'health': 100,
                        'armor': 0
                    }
            
            elif self.mode == SystemMode.STANDALONE and self.memory_manager:
                # استخدام Python للحصول على البيانات
                position = self.memory_manager.get_player_position()
                rotation = self.memory_manager.get_player_rotation()
                
                return {
                    'position': position,
                    'rotation': rotation,
                    'velocity': (0, 0, 0),
                    'health': 100,
                    'armor': 0
                }
            
            elif self.mode == SystemMode.HYBRID:
                # استخدام كلا النظامين
                if self.cpp_controller:
                    position = self.cpp_controller.get_local_player_position()
                    if position:
                        return {
                            'position': position,
                            'rotation': (0, 0, 0),
                            'velocity': (0, 0, 0),
                            'health': 100,
                            'armor': 0
                        }
                
                # fallback إلى Python
                if self.memory_manager:
                    position = self.memory_manager.get_player_position()
                    rotation = self.memory_manager.get_player_rotation()
                    
                    return {
                        'position': position,
                        'rotation': rotation,
                        'velocity': (0, 0, 0),
                        'health': 100,
                        'armor': 0
                    }
                    
        except Exception as e:
            print(f"Error getting local player data: {e}")
        
        return None
    
    def _sync_with_remote_players(self):
        """المزامنة مع اللاعبين الآخرين"""
        # هذه وظيفة ستتم مزامنتها مع الشبكة
        pass
    
    def create_remote_player(self, player_id: int, name: str, 
                           position: Tuple[float, float, float]) -> bool:
        """إنشاء لاعب عن بعد"""
        print(f"👤 Creating remote player {name} (ID: {player_id})...")
        
        try:
            if self.mode == SystemMode.CPP_ONLY or self.mode == SystemMode.HYBRID:
                if self.cpp_controller and self.cpp_controller.connected:
                    # استخدام C++ لإنشاء اللاعب
                    entity_addr = self.cpp_controller.create_remote_player(
                        player_id,
                        position[0],
                        position[1],
                        position[2]
                    )
                    
                    if entity_addr:
                        self.players[player_id] = PlayerInfo(
                            id=player_id,
                            name=name,
                            entity_address=entity_addr,
                            position=position,
                            last_update=time.time()
                        )
                        return True
            
            if self.mode == SystemMode.STANDALONE or self.mode == SystemMode.HYBRID:
                if self.memory_manager and hasattr(self.memory_manager, 'is_attached') and self.memory_manager.is_attached:
                    # استخدام Python لإنشاء اللاعب
                    try:
                        slot, entity_addr = self.memory_manager.create_remote_player(
                            player_id=player_id,
                            position=position
                        )
                        
                        if entity_addr:
                            self.players[player_id] = PlayerInfo(
                                id=player_id,
                                name=name,
                                entity_address=entity_addr,
                                position=position,
                                last_update=time.time()
                            )
                            return True
                    except AttributeError:
                        # قد لا يكون لديه create_remote_player
                        pass
            
            # وضع المحاكاة بدون ذاكرة حقيقية
            self.players[player_id] = PlayerInfo(
                id=player_id,
                name=name,
                entity_address=0,
                position=position,
                last_update=time.time()
            )
            return True
            
        except Exception as e:
            print(f"Error creating remote player: {e}")
            return False
    
    def update_player_position(self, player_id: int, 
                             position: Tuple[float, float, float],
                             rotation: Tuple[float, float, float]) -> bool:
        """تحديث موقع لاعب"""
        if player_id not in self.players:
            return False
        
        try:
            player = self.players[player_id]
            
            # تحديث في C++
            if self.cpp_controller and self.cpp_controller.connected:
                self.cpp_controller.update_remote_player(
                    player_id,
                    position,
                    rotation
                )
            
            # تحديث في Python
            if self.memory_manager and hasattr(self.memory_manager, 'is_attached') and self.memory_manager.is_attached:
                try:
                    self.memory_manager.update_remote_player(
                        player.entity_address,
                        position,
                        rotation,
                        0  # animation
                    )
                except AttributeError:
                    pass
            
            # تحديث البيانات المحلية
            player.position = position
            player.last_update = time.time()
            
            return True
            
        except Exception as e:
            print(f"Error updating player position: {e}")
            return False
    
    def get_player_list(self) -> List[Dict]:
        """الحصول على قائمة اللاعبين"""
        players_list = []
        
        for player in self.players.values():
            players_list.append({
                'id': player.id,
                'name': player.name,
                'position': player.position,
                'is_local': player.is_local,
                'last_update': player.last_update
            })
        
        return players_list
    
    def shutdown(self):
        """إيقاف النظام"""
        print("🛑 Shutting down system...")
        
        self.running = False
        
        # انتظار إنهاء الخيوط
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=2)
        
        # إيقاف نواة C++
        if self.cpp_controller:
            try:
                self.cpp_controller.shutdown_core()
                self.cpp_controller.disconnect()
            except:
                pass
        
        # فك ارتباط مدير الذاكرة
        if self.memory_manager:
            try:
                self.memory_manager.detach()
            except:
                pass
        
        print("✅ System shutdown complete")
    
    def benchmark(self) -> Dict:
        """اختبار أداء النظام"""
        print("📊 Running benchmark...")
        
        results = {
            'mode': self.mode.value,
            'timestamp': time.time(),
            'tests': {}
        }
        
        try:
            # اختبار سرعة القراءة
            start_time = time.time()
            read_count = 10  # تقليل العدد للسرعة
            
            for i in range(read_count):
                if self.memory_manager:
                    self.memory_manager.get_player_position()
            
            read_time = time.time() - start_time
            if read_time > 0:
                results['tests']['python_read_speed'] = {
                    'ops': read_count,
                    'time': read_time,
                    'ops_per_sec': read_count / read_time
                }
            
            print(f"📈 Benchmark results: {json.dumps(results, indent=2)}")
            
        except Exception as e:
            print(f"Benchmark error: {e}")
        
        return results

def main():
    """واجهة سطر الأوامر الرئيسية"""
    print("=" * 60)
    print("GTA Vice City Unified Multiplayer System")
    print("Python ↔ C++ Bridge System")
    print("=" * 60)
    print()
    
    # التحقق من صلاحيات المسؤول
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("⚠ Warning: Running without administrator privileges")
            print("Some features may not work correctly.")
            print()
    except:
        print("⚠ Could not check administrator privileges")
        print()
    
    # اختيار وضع التشغيل
    print("Select system mode:")
    print("1. Hybrid (Python + C++) - Recommended")
    print("2. C++ Only (High Performance)")
    print("3. Python Only (Compatibility)")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        mode = SystemMode.HYBRID
    elif choice == "2":
        mode = SystemMode.CPP_ONLY
    elif choice == "3":
        mode = SystemMode.STANDALONE
    else:
        print("Invalid choice, using Hybrid mode")
        mode = SystemMode.HYBRID
    
    # اختيار الدور
    print()
    print("Select role:")
    print("1. Host (Create game)")
    print("2. Client (Join game)")
    print()
    
    role_choice = input("Enter choice (1-2): ").strip()
    is_host = (role_choice == "1")
    
    # إنشاء النظام
    system = UnifiedMultiplayerSystem(mode)
    
    # التهيئة
    if system.initialize(is_host):
        print()
        print("✅ System ready!")
        print("   Press Enter to view commands...")
        input()
        
        # قائمة الأوامر
        while True:
            print()
            print("Commands:")
            print("  1. List players")
            print("  2. Create test player")
            print("  3. Update test player")
            print("  4. Run benchmark")
            print("  5. Show system info")
            print("  6. Exit")
            print()
            
            cmd = input("Enter command: ").strip()
            
            if cmd == "1":
                players = system.get_player_list()
                print(f"Players ({len(players)}):")
                for player in players:
                    print(f"  {player['name']} (ID: {player['id']})")
                    print(f"    Position: {player['position']}")
                    print(f"    Local: {player['is_local']}")
            
            elif cmd == "2":
                # إنشاء لاعب تجريبي
                success = system.create_remote_player(
                    player_id=9999,
                    name="Test Player",
                    position=(100.0, 200.0, 10.0)
                )
                print(f"Create test player: {'Success' if success else 'Failed'}")
            
            elif cmd == "3":
                # تحديث لاعب تجريبي
                success = system.update_player_position(
                    player_id=9999,
                    position=(105.0, 205.0, 10.0),
                    rotation=(0.0, 0.0, 90.0)
                )
                print(f"Update test player: {'Success' if success else 'Failed'}")
            
            elif cmd == "4":
                # تشغيل اختبار الأداء
                system.benchmark()
            
            elif cmd == "5":
                # عرض معلومات النظام
                print(f"Mode: {system.mode.value}")
                print(f"Role: {'Host' if system.is_host else 'Client'}")
                print(f"Running: {system.running}")
                print(f"Game PID: {system.game_pid}")
                print(f"Player count: {len(system.players)}")
            
            elif cmd == "6":
                # خروج
                break
            
            else:
                print("Invalid command")
        
        # إيقاف النظام
        system.shutdown()
    
    else:
        print("❌ Failed to initialize system")
        print("Check that GTA Vice City is running")

if __name__ == "__main__":
    main()