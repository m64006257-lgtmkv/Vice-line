import os
import sys
import json
import socket
import threading
import time
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import configparser
import ctypes
from pathlib import Path

# التحقق من نظام التشغيل
if sys.platform != "win32":
    print("This system requires Windows OS")
    sys.exit(1)

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    print("⚠ winreg module not available")
    WINREG_AVAILABLE = False

class UnifiedGTASystem:
    """النظام الموحد الكامل: لانشر + سيرفر + عميل"""
    
    def __init__(self):
        self.mode = "launcher"  # launcher, server, client
        self.game_path = ""
        self.game_version = ""
        self.server_running = False
        self.client_connected = False
        
        # إعدادات الشبكة
        self.server_port = 5192
        self.broadcast_port = 9999
        self.tcp_port = 5555
        
        # متغيرات السيرفر
        self.server_socket = None
        self.clients = []
        self.player_count = 0
        
        # متغيرات العميل
        self.client_socket = None
        self.current_server = None
        
        # إنشاء واجهة المستخدم
        self.root = tk.Tk()
        self.root.title("GTA Vice City Unified System")
        self.root.geometry("900x700")
        self.root.configure(bg="#1a1a1a")
        
        # تحميل الإعدادات
        self.load_config()
        
        # إنشاء واجهة المستخدم
        self.setup_ui()
        
    def setup_ui(self):
        """إنشاء الواجهة الموحدة"""
        
        # شريط العنوان المخصص
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        
        # شعار واسم التطبيق
        title_label = tk.Label(title_frame, 
                              text="🎮 GTA Vice City Unified System",
                              font=("Arial", 20, "bold"),
                              fg="#ecf0f1",
                              bg="#2c3e50")
        title_label.pack(side="left", padx=20)
        
        # شريط الحالة
        self.status_label = tk.Label(title_frame,
                                    text="Ready",
                                    font=("Arial", 10),
                                    fg="#bdc3c7",
                                    bg="#2c3e50")
        self.status_label.pack(side="right", padx=20)
        
        # الإطار الرئيسي
        main_frame = tk.Frame(self.root, bg="#1a1a1a")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # الجانب الأيسر: اختيار الوضع
        left_panel = tk.LabelFrame(main_frame,
                                  text="System Mode",
                                  font=("Arial", 12, "bold"),
                                  fg="#ecf0f1",
                                  bg="#2c3e50",
                                  relief="ridge",
                                  borderwidth=2)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        
        # أزرار اختيار الوضع
        mode_frame = tk.Frame(left_panel, bg="#2c3e50", padx=10, pady=20)
        mode_frame.pack()
        
        # زر اللانشر
        self.launcher_btn = tk.Button(mode_frame,
                                     text="🎮 SINGLE PLAYER\nLaunch Game",
                                     command=lambda: self.set_mode("launcher"),
                                     font=("Arial", 11, "bold"),
                                     bg="#27ae60",
                                     fg="white",
                                     width=20,
                                     height=3,
                                     cursor="hand2")
        self.launcher_btn.grid(row=0, column=0, pady=10)
        
        # زر المضيف (السيرفر)
        self.server_btn = tk.Button(mode_frame,
                                   text="🚀 HOST SERVER\nCreate LAN Game",
                                   command=lambda: self.set_mode("server"),
                                   font=("Arial", 11, "bold"),
                                   bg="#3498db",
                                   fg="white",
                                   width=20,
                                   height=3,
                                   cursor="hand2")
        self.server_btn.grid(row=1, column=0, pady=10)
        
        # زر العميل
        self.client_btn = tk.Button(mode_frame,
                                   text="🔗 JOIN SERVER\nConnect to LAN",
                                   command=lambda: self.set_mode("client"),
                                   font=("Arial", 11, "bold"),
                                   bg="#9b59b6",
                                   fg="white",
                                   width=20,
                                   height=3,
                                   cursor="hand2")
        self.client_btn.grid(row=2, column=0, pady=10)
        
        # معلومات النظام
        info_frame = tk.Frame(left_panel, bg="#34495e", padx=10, pady=10)
        info_frame.pack(fill="x", pady=20)
        
        self.system_info = tk.Label(info_frame,
                                   text="System: Ready\nMode: Launcher",
                                   font=("Arial", 9),
                                   fg="#ecf0f1",
                                   bg="#34495e",
                                   justify="left")
        self.system_info.pack()
        
        # الجانب الأيمن: لوحة التحكم الديناميكية
        self.control_panel = tk.Frame(main_frame, bg="#2c3e50")
        self.control_panel.pack(side="right", fill="both", expand=True)
        
        # عرض وضع اللانشر افتراضياً
        self.show_launcher_panel()
        
        # شريط التقدم في الأسفل
        self.progress_bar = ttk.Progressbar(self.root,
                                          mode='indeterminate',
                                          length=300)
        self.progress_bar.pack(side="bottom", fill="x", padx=20, pady=10)
        
    def set_mode(self, mode):
        """تغيير وضع النظام"""
        self.mode = mode
        
        # تحديث أزرار الوضع
        colors = {
            "launcher": "#27ae60",
            "server": "#3498db", 
            "client": "#9b59b6"
        }
        
        self.launcher_btn.config(bg="#2c3e50" if mode != "launcher" else colors["launcher"])
        self.server_btn.config(bg="#2c3e50" if mode != "server" else colors["server"])
        self.client_btn.config(bg="#2c3e50" if mode != "client" else colors["client"])
        
        # تحديث لوحة التحكم
        self.clear_control_panel()
        
        if mode == "launcher":
            self.show_launcher_panel()
            self.status_label.config(text="Mode: Single Player Launcher")
        elif mode == "server":
            self.show_server_panel()
            self.status_label.config(text="Mode: LAN Server Host")
        elif mode == "client":
            self.show_client_panel()
            self.status_label.config(text="Mode: LAN Client")
            
        self.update_system_info()
        
    def clear_control_panel(self):
        """مسح لوحة التحكم"""
        for widget in self.control_panel.winfo_children():
            widget.destroy()
            
    def show_launcher_panel(self):
        """عرض لوحة اللانشر"""
        panel = tk.LabelFrame(self.control_panel,
                             text="Single Player Launcher",
                             font=("Arial", 14, "bold"),
                             fg="#ecf0f1",
                             bg="#2c3e50",
                             relief="ridge",
                             borderwidth=2)
        panel.pack(fill="both", expand=True, padx=10, pady=10)
        
        # اكتشاف اللعبة
        game_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        game_frame.pack(fill="x", pady=10)
        
        tk.Label(game_frame,
                text="Game Detection:",
                font=("Arial", 12, "bold"),
                fg="white",
                bg="#34495e").grid(row=0, column=0, sticky="w", pady=5)
        
        self.game_path_var = tk.StringVar(value=self.game_path)
        path_entry = tk.Entry(game_frame,
                            textvariable=self.game_path_var,
                            width=50,
                            font=("Arial", 10))
        path_entry.grid(row=1, column=0, pady=5, padx=(0, 10))
        
        tk.Button(game_frame,
                 text="Browse",
                 command=self.browse_game,
                 bg="#3498db",
                 fg="white").grid(row=1, column=1, padx=5)
        
        tk.Button(game_frame,
                 text="Auto Detect",
                 command=self.auto_detect_game,
                 bg="#2ecc71",
                 fg="white").grid(row=1, column=2, padx=5)
        
        # إعدادات التشغيل
        settings_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        settings_frame.pack(fill="x", pady=10)
        
        tk.Label(settings_frame,
                text="Launch Settings:",
                font=("Arial", 12, "bold"),
                fg="white",
                bg="#34495e").grid(row=0, column=0, sticky="w", pady=10)
        
        # وضع النافذة
        tk.Label(settings_frame,
                text="Window Mode:",
                fg="white",
                bg="#34495e").grid(row=1, column=0, sticky="w", padx=5)
        
        self.window_mode = tk.StringVar(value="windowed")
        window_combo = ttk.Combobox(settings_frame,
                                   textvariable=self.window_mode,
                                   values=["windowed", "fullscreen", "borderless"],
                                   width=15,
                                   state="readonly")
        window_combo.grid(row=1, column=1, padx=10)
        
        # الدقة
        tk.Label(settings_frame,
                text="Resolution:",
                fg="white",
                bg="#34495e").grid(row=2, column=0, sticky="w", padx=5, pady=10)
        
        self.resolution = tk.StringVar(value="1024x768")
        res_combo = ttk.Combobox(settings_frame,
                                textvariable=self.resolution,
                                values=["640x480", "800x600", "1024x768", "1280x720", "1366x768", "1920x1080"],
                                width=12,
                                state="readonly")
        res_combo.grid(row=2, column=1, padx=10, pady=10)
        
        # زر التشغيل
        launch_frame = tk.Frame(panel, bg="#2c3e50", pady=30)
        launch_frame.pack()
        
        tk.Button(launch_frame,
                 text="🚀 LAUNCH GAME",
                 command=self.launch_game,
                 font=("Arial", 16, "bold"),
                 bg="#e74c3c",
                 fg="white",
                 padx=30,
                 pady=15,
                 cursor="hand2").pack()
        
    def show_server_panel(self):
        """عرض لوحة السيرفر"""
        panel = tk.LabelFrame(self.control_panel,
                             text="LAN Server Host",
                             font=("Arial", 14, "bold"),
                             fg="#ecf0f1",
                             bg="#2c3e50",
                             relief="ridge",
                             borderwidth=2)
        panel.pack(fill="both", expand=True, padx=10, pady=10)
        
        # إعدادات السيرفر
        settings_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        settings_frame.pack(fill="x", pady=10)
        
        tk.Label(settings_frame,
                text="Server Settings:",
                font=("Arial", 12, "bold"),
                fg="white",
                bg="#34495e").grid(row=0, column=0, sticky="w", pady=10, columnspan=2)
        
        # اسم السيرفر
        tk.Label(settings_frame,
                text="Server Name:",
                fg="white",
                bg="#34495e").grid(row=1, column=0, sticky="w", padx=5)
        
        self.server_name = tk.StringVar(value="GTA VC LAN Server")
        tk.Entry(settings_frame,
                textvariable=self.server_name,
                width=30).grid(row=1, column=1, pady=5)
        
        # كلمة السر
        tk.Label(settings_frame,
                text="Password:",
                fg="white",
                bg="#34495e").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        
        self.server_password = tk.StringVar()
        tk.Entry(settings_frame,
                textvariable=self.server_password,
                show="*",
                width=30).grid(row=2, column=1, pady=5)
        
        # عدد اللاعبين
        tk.Label(settings_frame,
                text="Max Players:",
                fg="white",
                bg="#34495e").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        self.max_players = tk.StringVar(value="16")
        ttk.Spinbox(settings_frame,
                   from_=2,
                   to=32,
                   textvariable=self.max_players,
                   width=10).grid(row=3, column=1, pady=5)
        
        # حالة السيرفر
        status_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        status_frame.pack(fill="x", pady=10)
        
        self.server_status = tk.Label(status_frame,
                                     text="Status: Stopped",
                                     font=("Arial", 12),
                                     fg="#e74c3c",
                                     bg="#34495e")
        self.server_status.pack(anchor="w")
        
        self.players_label = tk.Label(status_frame,
                                     text="Players: 0/0",
                                     font=("Arial", 12),
                                     fg="#3498db",
                                     bg="#34495e")
        self.players_label.pack(anchor="w")
        
        # أزرار التحكم
        control_frame = tk.Frame(panel, bg="#2c3e50", pady=20)
        control_frame.pack()
        
        self.start_server_btn = tk.Button(control_frame,
                                         text="▶ START SERVER",
                                         command=self.start_server,
                                         font=("Arial", 14, "bold"),
                                         bg="#27ae60",
                                         fg="white",
                                         padx=20,
                                         pady=10,
                                         cursor="hand2")
        self.start_server_btn.pack(side="left", padx=10)
        
        self.stop_server_btn = tk.Button(control_frame,
                                        text="■ STOP SERVER",
                                        command=self.stop_server,
                                        font=("Arial", 14, "bold"),
                                        bg="#e74c3c",
                                        fg="white",
                                        padx=20,
                                        pady=10,
                                        cursor="hand2",
                                        state="disabled")
        self.stop_server_btn.pack(side="left", padx=10)
        
        # سجل السيرفر
        log_frame = tk.Frame(panel, bg="#1a1a1a", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, pady=10)
        
        self.server_log = scrolledtext.ScrolledText(log_frame,
                                                   height=8,
                                                   bg="#1a1a1a",
                                                   fg="#2ecc71",
                                                   font=("Courier", 9))
        self.server_log.pack(fill="both", expand=True)
        
    def show_client_panel(self):
        """عرض لوحة العميل"""
        panel = tk.LabelFrame(self.control_panel,
                             text="LAN Client",
                             font=("Arial", 14, "bold"),
                             fg="#ecf0f1",
                             bg="#2c3e50",
                             relief="ridge",
                             borderwidth=2)
        panel.pack(fill="both", expand=True, padx=10, pady=10)
        
        # البحث عن السيرفرات
        search_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        search_frame.pack(fill="x", pady=10)
        
        tk.Label(search_frame,
                text="Server Discovery:",
                font=("Arial", 12, "bold"),
                fg="white",
                bg="#34495e").grid(row=0, column=0, sticky="w", pady=10, columnspan=2)
        
        tk.Button(search_frame,
                 text="🔍 Search Servers",
                 command=self.search_servers,
                 bg="#3498db",
                 fg="white").grid(row=1, column=0, padx=5)
        
        tk.Button(search_frame,
                 text="🔄 Refresh",
                 command=self.refresh_servers,
                 bg="#2ecc71",
                 fg="white").grid(row=1, column=1, padx=5)
        
        # قائمة السيرفرات
        list_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        list_frame.pack(fill="x", pady=10)
        
        # إنشاء Treeview للسيرفرات
        columns = ('name', 'ip', 'players', 'ping')
        self.servers_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=6)
        
        self.servers_tree.heading('name', text='Server Name')
        self.servers_tree.heading('ip', text='IP Address')
        self.servers_tree.heading('players', text='Players')
        self.servers_tree.heading('ping', text='Ping')
        
        self.servers_tree.column('name', width=200)
        self.servers_tree.column('ip', width=150)
        self.servers_tree.column('players', width=80)
        self.servers_tree.column('ping', width=80)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.servers_tree.yview)
        self.servers_tree.configure(yscrollcommand=scrollbar.set)
        
        self.servers_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # الاتصال المباشر
        direct_frame = tk.Frame(panel, bg="#34495e", padx=20, pady=20)
        direct_frame.pack(fill="x", pady=10)
        
        tk.Label(direct_frame,
                text="Direct Connect:",
                font=("Arial", 12, "bold"),
                fg="white",
                bg="#34495e").grid(row=0, column=0, sticky="w", pady=10, columnspan=3)
        
        tk.Label(direct_frame,
                text="IP:",
                fg="white",
                bg="#34495e").grid(row=1, column=0, sticky="w", padx=5)
        
        self.direct_ip = tk.StringVar(value="192.168.1.100")
        tk.Entry(direct_frame,
                textvariable=self.direct_ip,
                width=20).grid(row=1, column=1, padx=5)
        
        tk.Label(direct_frame,
                text="Port:",
                fg="white",
                bg="#34495e").grid(row=1, column=2, sticky="w", padx=5)
        
        self.direct_port = tk.StringVar(value="5192")
        tk.Entry(direct_frame,
                textvariable=self.direct_port,
                width=10).grid(row=1, column=3, padx=5)
        
        # أزرار الاتصال
        connect_frame = tk.Frame(panel, bg="#2c3e50", pady=20)
        connect_frame.pack()
        
        tk.Button(connect_frame,
                 text="🔗 CONNECT",
                 command=self.connect_to_server,
                 font=("Arial", 12, "bold"),
                 bg="#9b59b6",
                 fg="white",
                 padx=20,
                 pady=10,
                 cursor="hand2").pack(side="left", padx=10)
        
        tk.Button(connect_frame,
                 text="🎮 LAUNCH & JOIN",
                 command=self.launch_and_join,
                 font=("Arial", 12, "bold"),
                 bg="#e67e22",
                 fg="white",
                 padx=20,
                 pady=10,
                 cursor="hand2").pack(side="left", padx=10)
        
    def browse_game(self):
        """تصفح للعثور على اللعبة"""
        folder = filedialog.askdirectory(title="Select GTA Vice City Installation Folder")
        if folder:
            self.game_path_var.set(folder)
            self.game_path = folder
            self.save_config()
            
    def auto_detect_game(self):
        """اكتشاف تلقائي للعبة"""
        self.status_label.config(text="Scanning for GTA Vice City...")
        self.progress_bar.start()
        
        # محاكاة البحث (في الواقع سيتم البحث في السجل والمسارات)
        detected = self.detect_game_installation()
        
        self.progress_bar.stop()
        if detected:
            self.status_label.config(text="Game detected!")
            messagebox.showinfo("Success", f"GTA Vice City detected at:\n{self.game_path}")
        else:
            self.status_label.config(text="Game not found")
            messagebox.showwarning("Not Found", "Could not auto-detect GTA Vice City. Please browse manually.")
            
    def detect_game_installation(self):
        """اكتشاف تثبيت اللعبة"""
        if not WINREG_AVAILABLE:
            print("⚠ Windows registry access not available")
            return False
            
        # البحث في السجل
        try:
            # Original retail
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Rockstar Games\GTA Vice City")
            path, _ = winreg.QueryValueEx(key, "InstallFolder")
            winreg.CloseKey(key)
            
            if os.path.exists(path):
                self.game_path = path
                self.game_path_var.set(path)
                self.game_version = "Original Retail"
                return True
        except:
            pass
        
        try:
            # Steam version
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 12120")
            path, _ = winreg.QueryValueEx(key, "InstallLocation")
            winreg.CloseKey(key)
            
            steam_path = os.path.join(path, "steamapps", "common", "Grand Theft Auto Vice City")
            if os.path.exists(steam_path):
                self.game_path = steam_path
                self.game_path_var.set(steam_path)
                self.game_version = "Steam Version"
                return True
        except:
            pass
        
        # البحث في المسارات الشائعة
        common_paths = [
            "C:\\Program Files\\Rockstar Games\\GTA Vice City",
            "C:\\Program Files (x86)\\Rockstar Games\\GTA Vice City",
            "D:\\Games\\GTA Vice City",
            "E:\\Games\\GTA Vice City",
            os.path.join(os.path.expanduser("~"), "Desktop", "GTA Vice City")
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                # التحقق من وجود ملف التنفيذ
                exe_files = ["gta-vc.exe", "gta_vc.exe", "vicecity.exe"]
                for exe in exe_files:
                    exe_path = os.path.join(path, exe)
                    if os.path.exists(exe_path):
                        self.game_path = path
                        self.game_path_var.set(path)
                        self.game_version = "Detected in Common Path"
                        return True
        
        return False
    
    def launch_game(self):
        """تشغيل اللعبة"""
        if not self.game_path:
            messagebox.showwarning("Error", "Please select or detect GTA Vice City installation first.")
            return
            
        # البحث عن ملف التنفيذ
        exe_files = ["gta-vc.exe", "gta_vc.exe", "vicecity.exe", "GTAVC.exe"]
        exe_path = None
        
        for exe in exe_files:
            test_path = os.path.join(self.game_path, exe)
            if os.path.exists(test_path):
                exe_path = test_path
                break
                
        if not exe_path:
            messagebox.showerror("Error", "Could not find GTA Vice City executable.")
            return
            
        try:
            # بناء أوامر التشغيل
            cmd = [exe_path]
            
            # إضافة معاملات
            if self.window_mode.get() == "windowed":
                cmd.append("-window")
            elif self.window_mode.get() == "borderless":
                cmd.extend(["-window", "-noborder"])
                
            # الدقة
            if self.resolution.get():
                try:
                    width, height = self.resolution.get().split('x')
                    cmd.extend(["-width", width, "-height", height])
                except:
                    pass
                    
            # تغيير المسار إلى مجلد اللعبة
            game_dir = os.path.dirname(exe_path)
            original_dir = os.getcwd()
            os.chdir(game_dir)
            
            # تشغيل اللعبة
            process = subprocess.Popen(cmd, shell=True)
            
            # العودة للمسار الأصلي
            os.chdir(original_dir)
            
            self.status_label.config(text="Game launched successfully!")
            messagebox.showinfo("Success", "GTA Vice City is launching...")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch game:\n{str(e)}")
            
    def start_server(self):
        """بدء سيرفر LAN"""
        try:
            # إنشاء سيرفر UDP للبث
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            self.server_running = True
            
            # بدء thread للبث
            server_thread = threading.Thread(target=self.broadcast_server, daemon=True)
            server_thread.start()
            
            # تحديث الواجهة
            self.start_server_btn.config(state="disabled")
            self.stop_server_btn.config(state="normal")
            self.server_status.config(text="Status: Running", fg="#2ecc71")
            
            self.log_server_message("Server started successfully")
            self.log_server_message(f"Server Name: {self.server_name.get()}")
            self.log_server_message("Broadcasting on LAN...")
            
        except Exception as e:
            messagebox.showerror("Server Error", f"Failed to start server:\n{str(e)}")
            
    def stop_server(self):
        """إيقاف السيرفر"""
        self.server_running = False
        
        if self.server_socket:
            self.server_socket.close()
            
        self.start_server_btn.config(state="normal")
        self.stop_server_btn.config(state="disabled")
        self.server_status.config(text="Status: Stopped", fg="#e74c3c")
        
        self.log_server_message("Server stopped")
        
    def broadcast_server(self):
        """بث معلومات السيرفر على الشبكة"""
        local_ip = self.get_local_ip()
        
        while self.server_running:
            try:
                server_info = {
                    'type': 'GTALAN_SERVER',
                    'name': self.server_name.get(),
                    'ip': local_ip,
                    'port': self.server_port,
                    'players': self.player_count,
                    'max_players': int(self.max_players.get()),
                    'password': bool(self.server_password.get())
                }
                
                message = json.dumps(server_info).encode('utf-8')
                
                # البث على الشبكة المحلية
                broadcast_addr = self.get_broadcast_address(local_ip)
                if self.server_socket:
                    self.server_socket.sendto(message, (broadcast_addr, self.broadcast_port))
                
                time.sleep(5)  # البث كل 5 ثواني
                
            except Exception as e:
                if self.server_running:
                    self.log_server_message(f"Broadcast error: {str(e)}")
                break
                
    def search_servers(self):
        """البحث عن السيرفرات على الشبكة"""
        self.status_label.config(text="Searching for servers...")
        
        # محاكاة البحث (في الواقع سيكون بحث حقيقي)
        self.servers_tree.delete(*self.servers_tree.get_children())
        
        # إضافة سيرفرات وهمية للعرض
        sample_servers = [
            ("GTA VC LAN #1", "192.168.1.100", "4/16", "25ms"),
            ("Friends Server", "192.168.1.101", "2/8", "15ms"),
            ("Public Server", "192.168.1.102", "12/32", "45ms")
        ]
        
        for i, server in enumerate(sample_servers):
            self.servers_tree.insert('', 'end', iid=str(i), values=server)
            
        self.status_label.config(text=f"Found {len(sample_servers)} servers")
        
    def refresh_servers(self):
        """تحديث قائمة السيرفرات"""
        self.search_servers()
        
    def connect_to_server(self):
        """الاتصال بالسيرفر المحدد"""
        selected = self.servers_tree.selection()
        if selected:
            item = self.servers_tree.item(selected[0])
            values = item['values']
            
            ip = values[1]  # عنوان IP
            messagebox.showinfo("Connect", f"Connecting to {values[0]} at {ip}")
            self.status_label.config(text=f"Connecting to {values[0]}...")
            
        elif self.direct_ip.get():
            ip = self.direct_ip.get()
            port = self.direct_port.get()
            messagebox.showinfo("Direct Connect", f"Connecting to {ip}:{port}")
            self.status_label.config(text=f"Connecting to {ip}:{port}...")
            
        else:
            messagebox.showwarning("Warning", "Please select a server or enter IP address")
            
    def launch_and_join(self):
        """تشغيل اللعبة والانضمام للسيرفر"""
        if not self.game_path:
            messagebox.showwarning("Error", "Please select GTA Vice City installation first.")
            return
            
        # اتصال بالسيرفر أولاً
        self.connect_to_server()
        
        # ثم تشغيل اللعبة
        self.launch_game()
        
    def log_server_message(self, message):
        """تسجيل رسالة في سجل السيرفر"""
        timestamp = time.strftime("%H:%M:%S")
        self.server_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.server_log.see(tk.END)
        
    def get_local_ip(self):
        """الحصول على IP المحلي"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
            
    def get_broadcast_address(self, ip_address):
        """حساب عنوان البث"""
        try:
            ip_parts = ip_address.split('.')
            if len(ip_parts) == 4:
                return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
        except:
            pass
        return "255.255.255.255"
        
    def update_system_info(self):
        """تحديث معلومات النظام"""
        info_text = f"System: {self.mode.upper()}\n"
        if self.game_path:
            info_text += f"Game: {self.game_version if self.game_version else 'Found'}\n"
        else:
            info_text += "Game: Not detected\n"
        info_text += f"IP: {self.get_local_ip()}"
        
        self.system_info.config(text=info_text)
        
    def load_config(self):
        """تحميل الإعدادات"""
        config_file = "unified_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.game_path = config.get('game_path', '')
                    self.game_version = config.get('game_version', '')
            except:
                pass
                
    def save_config(self):
        """حفظ الإعدادات"""
        config = {
            'game_path': self.game_path,
            'game_version': self.game_version,
            'mode': self.mode
        }
        
        try:
            with open("unified_config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except:
            pass
            
    def run(self):
        """تشغيل النظام"""
        self.root.mainloop()

# ============================================
# التشغيل الرئيسي
# ============================================

if __name__ == "__main__":
    app = UnifiedGTASystem()
    app.run()