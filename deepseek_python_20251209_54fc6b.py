import ctypes
import sys
import os
import threading
import time
import json
from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import socket
import struct

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
        
    def initialize(self, as_host=True):
        """تهيئة النظام"""
        print("🚀 Initializing GTA VC Multiplayer System...")
        
        self.is_host = as_host
        
        try:
            # 1. تهيئة نظام الذاكرة
            from MemoryInjector import GTAVCMemoryManager
            self.memory_manager = GTAVCMemoryManager()
            
            if not self.memory_manager.attach_to_process():
                raise Exception("Failed to attach to GTA VC process")
            
            # 2. حقن DLL متعددة اللاعبين
            dll_path = self._build_multiplayer_dll()
            if dll_path and os.path.exists(dll_path):
                self.memory_manager.inject_dll(dll_path)
            
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
    
    def _build_multiplayer_dll(self):
        """بناء DLL المالتيميديا"""
        try:
            # تحقق من وجود مترجم C++ (MinGW أو MSVC)
            compiler_paths = [
                r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat",
                r"C:\MinGW\bin\g++.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvarsall.bat"
            ]
            
            # إذا لم يكن هناك مترجم، استخدم DLL مسبق البناء
            dll_path = "MultiplayerCore.dll"
            
            if not os.path.exists(dll_path):
                print("⚠ MultiplayerCore.dll not found, creating stub...")
                self._create_stub_dll(dll_path)
            
            return dll_path
            
        except Exception as e:
            print(f"⚠ Could not build DLL: {e}")
            return None
    
    def _create_stub_dll(self, path):
        """إنشاء DLL تجريبي"""
        try:
            # كود DLL بسيط للاختبار
            stub_code = """#include <windows.h>

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID lpReserved) {
    return TRUE;
}

extern "C" __declspec(dllexport) void InitializeMultiplayer() {
    MessageBoxA(NULL, "Multiplayer DLL Loaded!", "GTA VC MP", MB_OK);
}
"""
            
            # حفظ الكود
            with open("stub.cpp", "w") as f:
                f.write(stub_code)
            
            # محاولة الترجمة
            os.system("g++ -shared -o MultiplayerCore.dll stub.cpp")
            
            return os.path.exists(path)
            
        except:
            return False
    
    def _initialize_network(self):
        """تهيئة نظام الشبكة"""
        import socket
        
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
    
    def _start_subsystems(self):
        """بدء الأنظمة الفرعية"""
        # خيط الشبكة
        self.network_thread = threading.Thread(
            target=self._network_loop,
            daemon=True
        )
        self.network_thread.start()
        
        # خيط المزامنة
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True
        )
        self.sync_thread.start()
        
        # خيط البث (للسيرفر فقط)
        if self.is_host:
            self.broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                daemon=True
            )
            self.broadcast_thread.start()
    
    def _network_loop(self):
        """حلقة معالجة الشبكة"""
        print("🌐 Starting network loop...")
        
        while self.running:
            try:
                if self.is_host:
                    # استقبال الحزم كسيرفر
                    try:
                        data, addr = self.server_socket.recvfrom(1024)
                        self._process_incoming_packet(data, addr)
                    except socket.timeout:
                        continue
                else:
                    # استقبال الحزم كعميل
                    try:
                        data, addr = self.client_socket.recvfrom(1024)
                        self._process_incoming_packet(data, addr)
                    except socket.timeout:
                        continue
                        
            except Exception as e:
                print(f"Network error: {e}")
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
                print(f"Sync error: {e}")
                time.sleep(1)
    
    def _broadcast_loop(self):
        """حلقة بث وجود السيرفر"""
        if not self.is_host:
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
                print(f"Broadcast error: {e}")
                time.sleep(1)
    
    def _get_local_player_data(self) -> Optional[Dict]:
        """الحصول على بيانات اللاعب المحلي"""
        try:
            if not self.memory_manager or not self.memory_manager.is_attached:
                return None
            
            # قراءة موقع اللاعب
            position = self.memory_manager.get_player_position()
            
            # قراءة دوران اللاعب
            rotation = self.memory_manager.get_player_rotation()
            
            # قراءة المركبة (إذا كان في واحدة)
            vehicle_ptr = self.memory_manager.get_player_vehicle()
            vehicle_model = 0
            if vehicle_ptr:
                # يمكن قراءة نموذج المركبة من الذاكرة
                vehicle_model = 400  # افتراضي
            
            return {
                'position': position,
                'rotation': rotation,
                'velocity': (0, 0, 0),  # سيتم حسابه من الحركة
                'animation': 0,  # سيتم قراءته من الذاكرة
                'health': 100,  # سيتم قراءته من الذاكرة
                'armor': 0,  # سيتم قراءته من الذاكرة
                'weapon': 0,  # سيتم قراءته من الذاكرة
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
                print(f"👤 Player {packet.player_id} connected from {addr}")
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
        if self.memory_manager and self.memory_manager.is_attached:
            try:
                slot, entity_addr = self.memory_manager.create_remote_player(
                    player_id=packet.player_id,
                    position=packet.position
                )
                
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
        
        # إذا كنت سيرفر، قم بإعادة البث للآخرين
        if self.is_host:
            self._broadcast_packet(packet, exclude_addr=addr)
    
    def _handle_player_disconnect(self, packet: NetworkPacket):
        """معالجة انفصال لاعب"""
        if packet.player_id in self.remote_players:
            if self.memory_manager and self.memory_manager.is_attached:
                entity_addr = self.remote_players[packet.player_id]['entity_addr']
                self.memory_manager.destroy_entity(entity_addr)
            
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
            if self.memory_manager and self.memory_manager.is_attached:
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
        pass
    
    def _handle_player_chat(self, packet: NetworkPacket):
        """معالجة رسالة دردشة"""
        # فك تشفير الرسالة
        print(f"💬 Player {packet.player_id}: [Chat message]")
    
    def _send_packet(self, packet: NetworkPacket):
        """إرسال حزمة"""
        try:
            if self.is_host:
                # السيرفر يبث للجميع
                for player_id, info in self.remote_players.items():
                    if 'address' in info:
                        self.server_socket.sendto(
                            packet.to_bytes(),
                            info['address']
                        )
            else:
                # العميل يرسل للسيرفر
                # (يتطلب معرفة عنوان السيرفر أولاً)
                pass
                
        except Exception as e:
            print(f"Error sending packet: {e}")
    
    def _broadcast_packet(self, packet: NetworkPacket, exclude_addr=None):
        """بث حزمة لجميع العملاء"""
        if not self.is_host:
            return
        
        for player_id, info in self.remote_players.items():
            if 'address' in info and info['address'] != exclude_addr:
                try:
                    self.server_socket.sendto(
                        packet.to_bytes(),
                        info['address']
                    )
                except:
                    pass
    
    def connect_to_server(self, server_ip: str, server_port: int = None):
        """الاتصال بسيرفر"""
        if self.is_host:
            print("⚠ You are the host, cannot connect to another server")
            return False
        
        if server_port is None:
            server_port = self.port
        
        try:
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
        pass
    
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
        
        # انتظار إنهاء الخيوط
        if self.network_thread and self.network_thread.is_alive():
            self.network_thread.join(timeout=2)
        
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=2)
        
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.broadcast_thread.join(timeout=2)
        
        # إرسال حزمة انفصال
        if len(self.remote_players) > 0:
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
            
            try:
                self._send_packet(disconnect_packet)
            except:
                pass
        
        # تنظيف الذاكرة
        if self.memory_manager:
            for player_id in list(self.remote_players.keys()):
                self._handle_player_disconnect(
                    NetworkPacket(
                        packet_type=PacketType.DISCONNECT.value,
                        player_id=player_id,
                        position=(0, 0, 0),
                        rotation=(0, 0, 0),
                        velocity=(0, 0, 0),
                        animation=0,
                        health=0,
                        armor=0,
                        weapon=0,
                        vehicle_model=0,
                        timestamp=0
                    )
                )
            
            self.memory_manager.detach()
        
        # إغلاق المقابس
        try:
            if hasattr(self, 'server_socket'):
                self.server_socket.close()
            if hasattr(self, 'client_socket'):
                self.client_socket.close()
        except:
            pass
        
        print("✅ GTA VC Multiplayer System shut down successfully")

# واجهة مستخدم للنظام
class MultiplayerGUI:
    """واجهة رسومية للنظام"""
    
    def __init__(self):
        self.system = GTAMultiplayerSystem()
        self.root = None
        self.connected = False
        
    def run(self):
        """تشغيل الواجهة"""
        import tkinter as tk
        from tkinter import ttk, scrolledtext
        
        self.root = tk.Tk()
        self.root.title("GTA VC Multiplayer System")
        self.root.geometry("800x600")
        self.root.configure(bg="#2c3e50")
        
        # إنشاء الواجهة
        self._create_gui()
        
        # بدء التحديث
        self._update_loop()
        
        # معالجة الإغلاق
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.root.mainloop()
    
    def _create_gui(self):
        """إنشاء واجهة المستخدم"""
        import tkinter as tk
        from tkinter import ttk
        
        # الإطار العلوي
        top_frame = tk.Frame(self.root, bg="#34495e", height=80)
        top_frame.pack(fill="x")
        top_frame.pack_propagate(False)
        
        tk.Label(top_frame,
                text="🎮 GTA Vice City Multiplayer System",
                font=("Arial", 20, "bold"),
                fg="white",
                bg="#34495e").pack(pady=20)
        
        # الإطار الرئيسي
        main_frame = tk.Frame(self.root, bg="#2c3e50", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        
        # قسم التحكم
        control_frame = tk.LabelFrame(main_frame,
                                     text="Multiplayer Controls",
                                     font=("Arial", 12, "bold"),
                                     fg="white",
                                     bg="#34495e",
                                     relief="ridge")
        control_frame.pack(fill="x", pady=(0, 20))
        
        # أزرار الوضع
        mode_frame = tk.Frame(control_frame, bg="#34495e", padx=20, pady=20)
        mode_frame.pack()
        
        tk.Button(mode_frame,
                 text="🚀 HOST SERVER",
                 command=self.host_server,
                 font=("Arial", 12, "bold"),
                 bg="#27ae60",
                 fg="white",
                 width=20,
                 height=2).pack(side="left", padx=10)
        
        tk.Button(mode_frame,
                 text="🔗 JOIN SERVER",
                 command=self.join_server,
                 font=("Arial", 12, "bold"),
                 bg="#3498db",
                 fg="white",
                 width=20,
                 height=2).pack(side="left", padx=10)
        
        # قسم الاتصال
        connect_frame = tk.LabelFrame(main_frame,
                                     text="Connection",
                                     font=("Arial", 12, "bold"),
                                     fg="white",
                                     bg="#34495e",
                                     relief="ridge")
        connect_frame.pack(fill="x", pady=(0, 20))
        
        connect_inner = tk.Frame(connect_frame, bg="#34495e", padx=20, pady=20)
        connect_inner.pack()
        
        tk.Label(connect_inner,
                text="Server IP:",
                font=("Arial", 11),
                fg="white",
                bg="#34495e").grid(row=0, column=0, sticky="w", pady=5)
        
        self.ip_entry = tk.Entry(connect_inner, width=30, font=("Arial", 11))
        self.ip_entry.insert(0, "192.168.1.100")
        self.ip_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(connect_inner,
                text="Port:",
                font=("Arial", 11),
                fg="white",
                bg="#34495e").grid(row=0, column=2, sticky="w", pady=5)
        
        self.port_entry = tk.Entry(connect_inner, width=10, font=("Arial", 11))
        self.port_entry.insert(0, "5192")
        self.port_entry.grid(row=0, column=3, padx=10, pady=5)
        
        # حالة النظام
        status_frame = tk.LabelFrame(main_frame,
                                    text="System Status",
                                    font=("Arial", 12, "bold"),
                                    fg="white",
                                    bg="#34495e",
                                    relief="ridge")
        status_frame.pack(fill="x", pady=(0, 20))
        
        self.status_text = scrolledtext.ScrolledText(status_frame,
                                                    height=8,
                                                    bg="#1a1a1a",
                                                    fg="#2ecc71",
                                                    font=("Courier", 9))
        self.status_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.status_text.config(state="disabled")
        
        # معلومات اللاعبين
        players_frame = tk.LabelFrame(main_frame,
                                     text="Connected Players",
                                     font=("Arial", 12, "bold"),
                                     fg="white",
                                     bg="#34495e",
                                     relief="ridge")
        players_frame.pack(fill="both", expand=True)
        
        self.players_tree = ttk.Treeview(players_frame,
                                        columns=('id', 'type', 'position', 'ping'),
                                        show='headings',
                                        height=5)
        
        self.players_tree.heading('id', text='Player ID')
        self.players_tree.heading('type', text='Type')
        self.players_tree.heading('position', text='Position')
        self.players_tree.heading('ping', text='Ping')
        
        self.players_tree.column('id', width=100)
        self.players_tree.column('type', width=100)
        self.players_tree.column('position', width=200)
        self.players_tree.column('ping', width=80)
        
        scrollbar = ttk.Scrollbar(players_frame,
                                 orient="vertical",
                                 command=self.players_tree.yview)
        self.players_tree.configure(yscrollcommand=scrollbar.set)
        
        self.players_tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
    def _update_loop(self):
        """حلقة تحديث الواجهة"""
        if self.connected:
            self.update_player_list()
        
        self.root.after(1000, self._update_loop)
    
    def host_server(self):
        """بدء سيرفر"""
        try:
            self.log_message("Starting server...")
            
            if self.system.initialize(as_host=True):
                self.connected = True
                self.log_message("✅ Server started successfully!")
                self.log_message(f"📡 Listening on port {self.system.port}")
                self.log_message("👤 Waiting for players to connect...")
            else:
                self.log_message("❌ Failed to start server")
                
        except Exception as e:
            self.log_message(f"❌ Error starting server: {e}")
    
    def join_server(self):
        """الانضمام إلى سيرفر"""
        try:
            ip = self.ip_entry.get().strip()
            port = int(self.port_entry.get().strip())
            
            self.log_message(f"Connecting to {ip}:{port}...")
            
            if self.system.initialize(as_host=False):
                if self.system.connect_to_server(ip, port):
                    self.connected = True
                    self.log_message("✅ Connected to server!")
                else:
                    self.log_message("❌ Failed to connect to server")
                    self.system.shutdown()
            else:
                self.log_message("❌ Failed to initialize client")
                
        except Exception as e:
            self.log_message(f"❌ Error connecting: {e}")
    
    def update_player_list(self):
        """تحديث قائمة اللاعبين"""
        if not self.connected:
            return
        
        # مسح القائمة
        for item in self.players_tree.get_children():
            self.players_tree.delete(item)
        
        # إضافة اللاعبين
        players = self.system.get_player_list()
        for player in players:
            player_type = "Host" if player.get('is_host', False) else "Player"
            if player.get('is_local', False):
                player_type += " (You)"
            
            position = player.get('position', (0, 0, 0))
            pos_str = f"X: {position[0]:.1f}, Y: {position[1]:.1f}"
            
            self.players_tree.insert('', 'end', values=(
                player['id'],
                player_type,
                pos_str,
                "0ms"
            ))
    
    def log_message(self, message):
        """تسجيل رسالة في السجل"""
        self.status_text.config(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert("end", f"[{timestamp}] {message}\n")
        self.status_text.config(state="disabled")
        self.status_text.see("end")
    
    def on_closing(self):
        """عند إغلاق النافذة"""
        if self.connected:
            self.system.shutdown()
        self.root.destroy()

# التشغيل الرئيسي
if __name__ == "__main__":
    # تحقق من صلاحيات المسؤول
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
    
    if not is_admin:
        print("⚠ Warning: Running without administrator privileges")
        print("Some features may not work correctly.")
        print()
    
    print("=" * 60)
    print("GTA Vice City Multiplayer System")
    print("Complete Multiplayer Solution for GTA VC")
    print("=" * 60)
    print()
    
    # اختر طريقة التشغيل
    print("Select mode:")
    print("1. GUI Interface (Recommended)")
    print("2. Command Line Interface")
    print("3. Auto Host (Start server automatically)")
    print("4. Auto Join (Connect to server automatically)")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        # واجهة رسومية
        gui = MultiplayerGUI()
        gui.run()
        
    elif choice == "2":
        # واجهة سطر الأوامر
        print()
        print("Command Line Interface")
        print("-" * 30)
        print()
        
        mode = input("Host or Join? (h/j): ").lower().strip()
        
        if mode == "h":
            print("Starting as host...")
            system = GTAMultiplayerSystem()
            if system.initialize(as_host=True):
                print("✅ Server started!")
                print("Press Ctrl+C to stop")
                
                try:
                    while True:
                        time.sleep(1)
                        players = system.get_player_list()
                        print(f"\rPlayers online: {len(players) - 1}", end="")
                except KeyboardInterrupt:
                    print("\n\nShutting down...")
                    system.shutdown()
            else:
                print("❌ Failed to start server")
                
        elif mode == "j":
            ip = input("Server IP: ").strip()
            port = input("Port (5192): ").strip() or "5192"
            
            print(f"Connecting to {ip}:{port}...")
            system = GTAMultiplayerSystem()
            
            if system.initialize(as_host=False):
                if system.connect_to_server(ip, int(port)):
                    print("✅ Connected to server!")
                    print("Press Ctrl+C to disconnect")
                    
                    try:
                        while True:
                            time.sleep(1)
                            players = system.get_player_list()
                            print(f"\rPlayers online: {len(players)}", end="")
                    except KeyboardInterrupt:
                        print("\n\nDisconnecting...")
                        system.shutdown()
                else:
                    print("❌ Failed to connect to server")
                    system.shutdown()
            else:
                print("❌ Failed to initialize client")
    
    elif choice == "3":
        # بدء سيرفر تلقائي
        print("Starting auto host...")
        system = GTAMultiplayerSystem()
        
        if system.initialize(as_host=True):
            print("✅ Auto host started!")
            print("Server is running in background")
            print("Players can now connect to your game")
            print()
            print("Press Enter to stop...")
            input()
            system.shutdown()
        else:
            print("❌ Failed to start auto host")
    
    elif choice == "4":
        # انضمام تلقائي
        print("Starting auto join...")
        
        # البحث عن سيرفرات على الشبكة
        print("Scanning for servers on local network...")
        
        # محاولة الاتصال بالسيرفرات المحلية
        system = GTAMultiplayerSystem()
        
        if system.initialize(as_host=False):
            # محاولة الاتصال بعناوين IP محلية شائعة
            for i in range(1, 255):
                ip = f"192.168.1.{i}"
                print(f"Trying {ip}...", end="\r")
                
                if system.connect_to_server(ip, 5192):
                    print(f"\n✅ Connected to server at {ip}!")
                    
                    try:
                        while True:
                            time.sleep(1)
                            players = system.get_player_list()
                            print(f"\rPlayers online: {len(players)}", end="")
                    except KeyboardInterrupt:
                        print("\n\nDisconnecting...")
                        system.shutdown()
                        break
                    
                    break
            
            system.shutdown()
        else:
            print("❌ Failed to initialize client")
    
    else:
        print("Invalid choice")