import ctypes
import sys
import os
import time
import threading
import json
from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import socket
import struct

# التحقق من نظام التشغيل
if sys.platform != "win32":
    print("This module requires Windows OS")
    sys.exit(1)

# محاولة استيراد مكتبات Windows
try:
    import psutil
except ImportError:
    print("Please install psutil: pip install psutil")
    sys.exit(1)

try:
    import win32api
    import win32con
    import win32process
except ImportError:
    print("Please install pywin32: pip install pywin32")
    sys.exit(1)

# تعريفات Windows
USER32 = ctypes.WinDLL('user32', use_last_error=True)
KERNEL32 = ctypes.WinDLL('kernel32', use_last_error=True)

# أنواع الحزم
class PacketType(IntEnum):
    CONNECT = 0x01
    DISCONNECT = 0x02
    POSITION = 0x03
    VEHICLE = 0x04
    SHOOT = 0x05
    CHAT = 0x06
    SYNC = 0x07
    PING = 0x08

@dataclass
class NetworkPacket:
    packet_type: int
    player_id: int
    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float]
    velocity: Tuple[float, float, float]
    animation: int
    health: int
    armor: int
    weapon: int
    vehicle_model: int
    timestamp: int
    
    def to_bytes(self):
        """تحويل الحزمة إلى بايتات"""
        return struct.pack(
            '<B I fff fff fff H B B B I',
            self.packet_type,
            self.player_id,
            self.position[0], self.position[1], self.position[2],
            self.rotation[0], self.rotation[1], self.rotation[2],
            self.velocity[0], self.velocity[1], self.velocity[2],
            self.animation,
            self.health,
            self.armor,
            self.weapon,
            self.timestamp
        )
    
    @classmethod
    def from_bytes(cls, data: bytes):
        """إنشاء حزمة من البايتات"""
        fmt = '<B I fff fff fff H B B B I'
        size = struct.calcsize(fmt)
        
        if len(data) < size:
            return None
        
        unpacked = struct.unpack(fmt, data[:size])
        return cls(
            packet_type=unpacked[0],
            player_id=unpacked[1],
            position=(unpacked[2], unpacked[3], unpacked[4]),
            rotation=(unpacked[5], unpacked[6], unpacked[7]),
            velocity=(unpacked[8], unpacked[9], unpacked[10]),
            animation=unpacked[11],
            health=unpacked[12],
            armor=unpacked[13],
            weapon=unpacked[14],
            vehicle_model=unpacked[15],
            timestamp=unpacked[16]
        )

# استيراد مدير الذاكرة من ملف منفصل
try:
    from MemoryInjector import GTAVCMemoryManager
except ImportError:
    print("Warning: MemoryInjector not found. Creating fallback...")
    
    # Fallback Memory Manager
    class GTAVCMemoryManager:
        def __init__(self):
            self.is_attached = False
            
        def attach_to_process(self):
            print("Fallback memory manager - no real functionality")
            return False
            
        def get_player_position(self):
            return (0.0, 0.0, 0.0)
            
        def get_player_rotation(self):
            return (0.0, 0.0, 0.0)
            
        def get_player_vehicle(self):
            return 0
            
        def create_remote_player(self, player_id, position):
            return 0, 0
            
        def update_remote_player(self, entity_addr, position, rotation, animation=0):
            pass
            
        def destroy_entity(self, entity_addr):
            pass
            
        def inject_dll(self, dll_path):
            return False
            
        def detach(self):
            pass

class GTAMultiplayerSystem:
    """النظام المتكامل للعبة جماعية في GTA VC"""
    
    def __init__(self):
        self.is_host = False
        self.running = False
        self.local_player_id = os.getpid()
        self.remote_players = {}
        
        # أنظمة فرعية
        self.memory_manager = None
        self.network_manager = None
        self.entity_manager = None
        
        # خيوط العمل
        self.network_thread = None
        self.sync_thread = None
        self.broadcast_thread = None
        
        # إعدادات
        self.sync_rate = 20  # 20Hz
        self.broadcast_rate = 5  # 5Hz
        self.port = 5192
        self.broadcast_port = 9999
        
        # مقابس الشبكة
        self.server_socket = None
        self.client_socket = None
        
    def initialize(self, as_host=True):
        """تهيئة النظام"""
        print("🚀 Initializing GTA VC Multiplayer System...")
        
        self.is_host = as_host
        
        try:
            # 1. تهيئة نظام الذاكرة
            self.memory_manager = GTAVCMemoryManager()
            
            if not self.memory_manager.attach_to_process():
                print("⚠ Could not attach to GTA VC process, continuing in simulation mode")
            
            # 2. محاولة حقن DLL (اختياري)
            dll_path = self._get_dll_path()
            if dll_path and os.path.exists(dll_path) and self.memory_manager.is_attached:
                try:
                    self.memory_manager.inject_dll(dll_path)
                except Exception as e:
                    print(f"⚠ DLL injection skipped: {e}")
            
            # 3. تهيئة الشبكة
            self._initialize_network()
            
            # 4. بدء الأنظمة
            self.running = True
            self._start_subsystems()
            
            print("✅ GTA VC Multiplayer System initialized successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            self.shutdown()
            return False
    
    def _get_dll_path(self):
        """الحصول على مسار DLL"""
        possible_paths = [
            "MultiplayerCore.dll",
            os.path.join(os.getcwd(), "MultiplayerCore.dll"),
            os.path.join(os.path.dirname(__file__), "MultiplayerCore.dll")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _initialize_network(self):
        """تهيئة نظام الشبكة"""
        try:
            if self.is_host:
                # إنشاء سيرفر
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                
                # ربط بالمنفذ
                self.server_socket.bind(('0.0.0.0', self.port))
                self.server_socket.settimeout(0.1)
                
                print(f"📡 Server listening on port {self.port}")
            else:
                # إنشاء عميل
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                self.client_socket.settimeout(0.1)
                
                print("📡 Client network initialized")
                
        except Exception as e:
            print(f"❌ Network initialization failed: {e}")
            raise
    
    def _start_subsystems(self):
        """بدء الأنظمة الفرعية"""
        # خيط الشبكة
        self.network_thread = threading.Thread(
            target=self._network_loop,
            daemon=True,
            name="NetworkThread"
        )
        self.network_thread.start()
        
        # خيط المزامنة
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="SyncThread"
        )
        self.sync_thread.start()
        
        # خيط البث (للسيرفر فقط)
        if self.is_host:
            self.broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                daemon=True,
                name="BroadcastThread"
            )
            self.broadcast_thread.start()
    
    def _network_loop(self):
        """حلقة معالجة الشبكة"""
        print("🌐 Starting network loop...")
        
        while self.running:
            try:
                if self.is_host and self.server_socket:
                    # استقبال الحزم كسيرفر
                    try:
                        data, addr = self.server_socket.recvfrom(1024)
                        self._process_incoming_packet(data, addr)
                    except socket.timeout:
                        continue
                    except OSError as e:
                        if self.running:
                            print(f"Network error (server): {e}")
                        break
                elif not self.is_host and self.client_socket:
                    # استقبال الحزم كعميل
                    try:
                        data, addr = self.client_socket.recvfrom(1024)
                        self._process_incoming_packet(data, addr)
                    except socket.timeout:
                        continue
                    except OSError as e:
                        if self.running:
                            print(f"Network error (client): {e}")
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"Network loop error: {e}")
                    time.sleep(1)
    
    def _sync_loop(self):
        """حلقة مزامنة بيانات اللاعب"""
        print("🔄 Starting sync loop...")
        
        sync_interval = 1.0 / self.sync_rate
        
        while self.running:
            try:
                # الحصول على بيانات اللاعب المحلي
                player_data = self._get_local_player_data()
                
                if player_data:
                    # إنشاء حزمة
                    packet = NetworkPacket(
                        packet_type=PacketType.POSITION.value,
                        player_id=self.local_player_id,
                        position=player_data['position'],
                        rotation=player_data['rotation'],
                        velocity=player_data['velocity'],
                        animation=player_data['animation'],
                        health=player_data['health'],
                        armor=player_data['armor'],
                        weapon=player_data['weapon'],
                        vehicle_model=player_data['vehicle_model'],
                        timestamp=int(time.time() * 1000)
                    )
                    
                    # إرسال الحزمة
                    self._send_packet(packet)
                
                # انتظار للمعدل المطلوب
                time.sleep(sync_interval)
                
            except Exception as e:
                if self.running:
                    print(f"Sync error: {e}")
                    time.sleep(1)
    
    def _broadcast_loop(self):
        """حلقة بث وجود السيرفر"""
        if not self.is_host or not self.server_socket:
            return
        
        print("📢 Starting broadcast loop...")
        
        broadcast_interval = 1.0 / self.broadcast_rate
        
        while self.running:
            try:
                # إنشاء حزمة بث
                packet = NetworkPacket(
                    packet_type=PacketType.CONNECT.value,
                    player_id=self.local_player_id,
                    position=(0, 0, 0),
                    rotation=(0, 0, 0),
                    velocity=(0, 0, 0),
                    animation=0,
                    health=100,
                    armor=0,
                    weapon=0,
                    vehicle_model=0,
                    timestamp=int(time.time() * 1000)
                )
                
                # البث على الشبكة المحلية
                broadcast_addr = ('255.255.255.255', self.broadcast_port)
                self.server_socket.sendto(packet.to_bytes(), broadcast_addr)
                
                time.sleep(broadcast_interval)
                
            except Exception as e:
                if self.running:
                    print(f"Broadcast error: {e}")
                    time.sleep(1)
    
    def _get_local_player_data(self) -> Optional[Dict]:
        """الحصول على بيانات اللاعب المحلي"""
        try:
            if not self.memory_manager:
                return None
            
            # قراءة موقع اللاعب
            position = self.memory_manager.get_player_position()
            
            # قراءة دوران اللاعب
            rotation = self.memory_manager.get_player_rotation()
            
            # قراءة المركبة (إذا كان في واحدة)
            vehicle_ptr = self.memory_manager.get_player_vehicle()
            vehicle_model = 0
            if vehicle_ptr:
                vehicle_model = 400  # افتراضي
            
            return {
                'position': position,
                'rotation': rotation,
                'velocity': (0, 0, 0),
                'animation': 0,
                'health': 100,
                'armor': 0,
                'weapon': 0,
                'vehicle_model': vehicle_model
            }
            
        except Exception as e:
            print(f"Error reading player data: {e}")
            return None
    
    def _process_incoming_packet(self, data: bytes, addr: tuple):
        """معالجة الحزمة الواردة"""
        try:
            packet = NetworkPacket.from_bytes(data)
            if not packet:
                return
            
            # تجاهل الحزم الخاصة بي
            if packet.player_id == self.local_player_id:
                return
            
            # معالجة حسب نوع الحزمة
            if packet.packet_type == PacketType.CONNECT.value:
                print(f"👤 Player {packet.player_id} connected from {addr[0]}:{addr[1]}")
                self._handle_player_connect(packet, addr)
                
            elif packet.packet_type == PacketType.DISCONNECT.value:
                print(f"👤 Player {packet.player_id} disconnected")
                self._handle_player_disconnect(packet)
                
            elif packet.packet_type == PacketType.POSITION.value:
                self._handle_player_position(packet)
                
            elif packet.packet_type == PacketType.VEHICLE.value:
                self._handle_player_vehicle(packet)
                
            elif packet.packet_type == PacketType.CHAT.value:
                self._handle_player_chat(packet)
            
        except Exception as e:
            print(f"Error processing packet: {e}")
    
    def _handle_player_connect(self, packet: NetworkPacket, addr: tuple):
        """معالجة اتصال لاعب جديد"""
        # إنلاعب عن بعد في الذاكرة
        if self.memory_manager and hasattr(self.memory_manager, 'is_attached') and self.memory_manager.is_attached:
            try:
                slot, entity_addr = self.memory_manager.create_remote_player(
                    player_id=packet.player_id,
                    position=packet.position
                )
                
                if entity_addr:
                    self.remote_players[packet.player_id] = {
                        'slot': slot,
                        'entity_addr': entity_addr,
                        'address': addr,
                        'last_update': time.time(),
                        'position': packet.position,
                        'rotation': packet.rotation
                    }
                    
                    print(f"✅ Created remote player {packet.player_id} at slot {slot}")
                
            except Exception as e:
                print(f"Failed to create remote player: {e}")
        else:
            # حفظ المعلومات بدون إنشاء في الذاكرة
            self.remote_players[packet.player_id] = {
                'slot': -1,
                'entity_addr': 0,
                'address': addr,
                'last_update': time.time(),
                'position': packet.position,
                'rotation': packet.rotation
            }
            print(f"📝 Registered remote player {packet.player_id} (memory not attached)")
        
        # إذا كنت سيرفر، قم بإعادة البث للآخرين
        if self.is_host:
            self._broadcast_packet(packet, exclude_addr=addr)
    
    def _handle_player_disconnect(self, packet: NetworkPacket):
        """معالجة انفصال لاعب"""
        if packet.player_id in self.remote_players:
            player_info = self.remote_players[packet.player_id]
            
            # تدمير الكائن في الذاكرة إذا كان موجوداً
            if self.memory_manager and player_info.get('entity_addr', 0) != 0:
                try:
                    self.memory_manager.destroy_entity(player_info['entity_addr'])
                except Exception as e:
                    print(f"Warning: Failed to destroy entity: {e}")
            
            del self.remote_players[packet.player_id]
            print(f"✅ Removed remote player {packet.player_id}")
    
    def _handle_player_position(self, packet: NetworkPacket):
        """معالجة تحديث موقع لاعب"""
        if packet.player_id in self.remote_players:
            player_info = self.remote_players[packet.player_id]
            player_info['last_update'] = time.time()
            player_info['position'] = packet.position
            player_info['rotation'] = packet.rotation
            
            # تحديث الكائن في الذاكرة
            if self.memory_manager and player_info.get('entity_addr', 0) != 0:
                try:
                    self.memory_manager.update_remote_player(
                        entity_addr=player_info['entity_addr'],
                        position=packet.position,
                        rotation=packet.rotation,
                        animation=packet.animation
                    )
                except Exception as e:
                    print(f"Failed to update remote player: {e}")
            
            # إذا كنت سيرفر، قم بإعادة البث للآخرين
            if self.is_host:
                self._broadcast_packet(packet)
    
    def _handle_player_vehicle(self, packet: NetworkPacket):
        """معالجة تحديث مركبة لاعب"""
        # سيتم تنفيذ هذا لاحقاً
        print(f"Vehicle update from player {packet.player_id}")
    
    def _handle_player_chat(self, packet: NetworkPacket):
        """معالجة رسالة دردشة"""
        # فك تشفير الرسالة
        print(f"💬 Player {packet.player_id}: [Chat message]")
    
    def _send_packet(self, packet: NetworkPacket):
        """إرسال حزمة"""
        try:
            if self.is_host and self.server_socket:
                # السيرفر يبث للجميع
                for player_id, info in self.remote_players.items():
                    if 'address' in info:
                        try:
                            self.server_socket.sendto(
                                packet.to_bytes(),
                                info['address']
                            )
                        except Exception as e:
                            print(f"Failed to send to player {player_id}: {e}")
            elif not self.is_host and self.client_socket and self.current_server:
                # العميل يرسل للسيرفر
                try:
                    self.client_socket.sendto(
                        packet.to_bytes(),
                        self.current_server
                    )
                except Exception as e:
                    print(f"Failed to send to server: {e}")
                    
        except Exception as e:
            print(f"Error sending packet: {e}")
    
    def _broadcast_packet(self, packet: NetworkPacket, exclude_addr=None):
        """بث حزمة لجميع العملاء"""
        if not self.is_host or not self.server_socket:
            return
        
        for player_id, info in self.remote_players.items():
            if 'address' in info and info['address'] != exclude_addr:
                try:
                    self.server_socket.sendto(
                        packet.to_bytes(),
                        info['address']
                    )
                except Exception as e:
                    print(f"Failed to broadcast to player {player_id}: {e}")
    
    def connect_to_server(self, server_ip: str, server_port: int = None):
        """الاتصال بسيرفر"""
        if self.is_host:
            print("⚠ You are the host, cannot connect to another server")
            return False
        
        if server_port is None:
            server_port = self.port
        
        try:
            # حفظ معلومات السيرفر
            self.current_server = (server_ip, server_port)
            
            # إنشاء حزمة اتصال
            packet = NetworkPacket(
                packet_type=PacketType.CONNECT.value,
                player_id=self.local_player_id,
                position=(0, 0, 0),
                rotation=(0, 0, 0),
                velocity=(0, 0, 0),
                animation=0,
                health=100,
                armor=0,
                weapon=0,
                vehicle_model=0,
                timestamp=int(time.time() * 1000)
            )
            
            # إرسال طلب الاتصال
            if self.client_socket:
                self.client_socket.sendto(
                    packet.to_bytes(),
                    (server_ip, server_port)
                )
            
            print(f"🔗 Connecting to server {server_ip}:{server_port}...")
            return True
            
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def send_chat_message(self, message: str):
        """إرسال رسالة دردشة"""
        # سيتم تنفيذ هذا لاحقاً
        print(f"Sending chat: {message}")
    
    def get_player_list(self) -> List[Dict]:
        """الحصول على قائمة اللاعبين"""
        players = []
        
        # اللاعب المحلي
        players.append({
            'id': self.local_player_id,
            'is_local': True,
            'is_host': self.is_host
        })
        
        # اللاعبين عن بعد
        for player_id, info in self.remote_players.items():
            players.append({
                'id': player_id,
                'is_local': False,
                'position': info.get('position', (0, 0, 0)),
                'last_update': info.get('last_update', 0)
            })
        
        return players
    
    def shutdown(self):
        """إيقاف النظام"""
        print("🛑 Shutting down GTA VC Multiplayer System...")
        
        self.running = False
        
        # إرسال حزمة انفصال
        if len(self.remote_players) > 0:
            try:
                disconnect_packet = NetworkPacket(
                    packet_type=PacketType.DISCONNECT.value,
                    player_id=self.local_player_id,
                    position=(0, 0, 0),
                    rotation=(0, 0, 0),
                    velocity=(0, 0, 0),
                    animation=0,
                    health=0,
                    armor=0,
                    weapon=0,
                    vehicle_model=0,
                    timestamp=int(time.time() * 1000)
                )
                
                self._send_packet(disconnect_packet)
            except:
                pass
        
        # تنظيف الذاكرة
        if self.memory_manager:
            for player_id in list(self.remote_players.keys()):
                try:
                    info = self.remote_players[player_id]
                    if info.get('entity_addr', 0) != 0:
                        self.memory_manager.destroy_entity(info['entity_addr'])
                except:
                    pass
            
            self.memory_manager.detach()
        
        # إغلاق المقابس
        try:
            if self.server_socket:
                self.server_socket.close()
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        
        # انتظار إنهاء الخيوط
        threads_to_wait = []
        if self.network_thread and self.network_thread.is_alive():
            threads_to_wait.append(self.network_thread)
        if self.sync_thread and self.sync_thread.is_alive():
            threads_to_wait.append(self.sync_thread)
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            threads_to_wait.append(self.broadcast_thread)
        
        for thread in threads_to_wait:
            thread.join(timeout=2)
        
        print("✅ GTA VC Multiplayer System shut down successfully")