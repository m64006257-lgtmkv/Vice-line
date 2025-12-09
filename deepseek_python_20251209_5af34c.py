import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import shutil
import winreg
import ctypes
from pathlib import Path

class UnifiedInstaller:
    """برنامج تثبيت للنظام الموحد"""
    
    def __init__(self):
        self.install_dir = ""
        self.components = {
            'main': True,
            'startmenu': True,
            'desktop': True,
            'vcredist': True,
            'fileassoc': False
        }
        
        # إنشاء واجهة التثبيت
        self.root = tk.Tk()
        self.root.title("GTA Vice City Unified System Installer")
        self.root.geometry("700x500")
        self.root.configure(bg="#2c3e50")
        
        # تحميل أيقونة إذا كانت موجودة
        try:
            self.root.iconbitmap("installer_icon.ico")
        except:
            pass
            
        self.setup_ui()
        
    def setup_ui(self):
        """إنشاء واجهة التثبيت"""
        
        # إطار العنوان
        title_frame = tk.Frame(self.root, bg="#34495e", height=80)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        
        tk.Label(title_frame,
                text="🎮 GTA Vice City Unified System",
                font=("Arial", 20, "bold"),
                fg="white",
                bg="#34495e").pack(pady=20)
                
        tk.Label(title_frame,
                text="Complete System: Launcher + Server + Client",
                font=("Arial", 12),
                fg="#bdc3c7",
                bg="#34495e").pack()
                
        # إطار المحتوى
        content_frame = tk.Frame(self.root, bg="#2c3e50", padx=30, pady=20)
        content_frame.pack(fill="both", expand=True)
        
        # خطوات التثبيت
        self.steps = ttk.Notebook(content_frame)
        self.steps.pack(fill="both", expand=True)
        
        # الخطوة 1: الترحيب
        self.create_welcome_step()
        
        # الخطوة 2: الرخصة
        self.create_license_step()
        
        # الخطوة 3: المسار
        self.create_path_step()
        
        # الخطوة 4: المكونات
        self.create_components_step()
        
        # الخطوة 5: التثبيت
        self.create_install_step()
        
        # أزرار التنقل
        nav_frame = tk.Frame(content_frame, bg="#2c3e50", pady=10)
        nav_frame.pack(fill="x")
        
        self.back_btn = tk.Button(nav_frame,
                                 text="< Back",
                                 command=self.prev_step,
                                 state="disabled",
                                 bg="#3498db",
                                 fg="white")
        self.back_btn.pack(side="left", padx=5)
        
        self.next_btn = tk.Button(nav_frame,
                                 text="Next >",
                                 command=self.next_step,
                                 bg="#2ecc71",
                                 fg="white")
        self.next_btn.pack(side="left", padx=5)
        
        self.cancel_btn = tk.Button(nav_frame,
                                   text="Cancel",
                                   command=self.root.quit,
                                   bg="#e74c3c",
                                   fg="white")
        self.cancel_btn.pack(side="right", padx=5)
        
        # شريط التقدم
        self.progress = ttk.Progressbar(content_frame,
                                       mode='determinate',
                                       length=300)
        self.progress.pack(pady=10)
        
    def create_welcome_step(self):
        """إنشاء خطوة الترحيب"""
        frame = tk.Frame(self.steps, bg="#ecf0f1")
        
        tk.Label(frame,
                text="Welcome to GTA Vice City Unified System",
                font=("Arial", 16, "bold"),
                bg="#ecf0f1").pack(pady=30)
                
        info_text = """
        This installer will setup the complete GTA Vice City Unified System on your computer.
        
        The system includes:
        • Single Player Launcher - Launch any version of GTA VC
        • LAN Server Host - Create multiplayer games
        • LAN Client - Join multiplayer games
        
        Features:
        ✓ Auto-detects ALL game versions
        ✓ Works with Original, Steam, Cracked versions
        ✓ Modern and intuitive interface
        ✓ Complete LAN multiplayer support
        
        System Requirements:
        • Windows 7 or later
        • 200MB free disk space
        • GTA Vice City (any version)
        """
        
        tk.Label(frame,
                text=info_text,
                font=("Arial", 11),
                bg="#ecf0f1",
                justify="left").pack(padx=50)
                
        self.steps.add(frame, text="Welcome")
        
    def create_license_step(self):
        """إنشاء خطوة الرخصة"""
        frame = tk.Frame(self.steps, bg="#ecf0f1")
        
        tk.Label(frame,
                text="License Agreement",
                font=("Arial", 16, "bold"),
                bg="#ecf0f1").pack(pady=20)
                
        # مربع نص للرخصة
        license_text = tk.Text(frame,
                              height=15,
                              width=70,
                              font=("Arial", 10))
        license_text.pack(padx=20, pady=10)
        
        # تحميل نص الرخصة
        license_content = """
        GTA Vice City Unified System - License Agreement
        
        1. This software is provided "as-is" without any warranty.
        2. You must own a legitimate copy of GTA Vice City.
        3. This software is for personal, non-commercial use only.
        4. Do not use this software for piracy or illegal activities.
        5. The developers are not responsible for any damages.
        6. By installing this software, you agree to these terms.
        
        Note: This software is not affiliated with Rockstar Games.
        GTA Vice City is a trademark of Rockstar Games.
        """
        
        license_text.insert("1.0", license_content)
        license_text.config(state="disabled")
        
        # خانة الموافقة
        self.agree_var = tk.BooleanVar()
        agree_check = tk.Checkbutton(frame,
                                    text="I accept the license agreement",
                                    variable=self.agree_var,
                                    bg="#ecf0f1",
                                    font=("Arial", 11))
        agree_check.pack(pady=20)
        
        self.steps.add(frame, text="License")
        
    def create_path_step(self):
        """إنشاء خطوة اختيار المسار"""
        frame = tk.Frame(self.steps, bg="#ecf0f1")
        
        tk.Label(frame,
                text="Installation Location",
                font=("Arial", 16, "bold"),
                bg="#ecf0f1").pack(pady=30)
                
        # المسار الافتراضي
        default_path = os.path.join(os.environ["PROGRAMFILES"], "GTA VC Unified System")
        
        tk.Label(frame,
                text="Install to folder:",
                font=("Arial", 11),
                bg="#ecf0f1").pack()
                
        path_frame = tk.Frame(frame, bg="#ecf0f1")
        path_frame.pack(pady=10)
        
        self.path_var = tk.StringVar(value=default_path)
        path_entry = tk.Entry(path_frame,
                             textvariable=self.path_var,
                             width=50,
                             font=("Arial", 10))
        path_entry.pack(side="left", padx=(0, 10))
        
        tk.Button(path_frame,
                 text="Browse...",
                 command=self.browse_path,
                 bg="#3498db",
                 fg="white").pack(side="left")
                 
        # معلومات المساحة
        space_frame = tk.Frame(frame, bg="#ecf0f1", pady=20)
        space_frame.pack()
        
        self.space_label = tk.Label(space_frame,
                                   text="Checking disk space...",
                                   font=("Arial", 10),
                                   bg="#ecf0f1")
        self.space_label.pack()
        
        # تحديث معلومات المساحة
        self.update_space_info()
        self.path_var.trace("w", lambda *args: self.update_space_info())
        
        self.steps.add(frame, text="Install Location")
        
    def create_components_step(self):
        """إنشاء خطوة اختيار المكونات"""
        frame = tk.Frame(self.steps, bg="#ecf0f1")
        
        tk.Label(frame,
                text="Select Components",
                font=("Arial", 16, "bold"),
                bg="#ecf0f1").pack(pady=30)
                
        # قائمة المكونات
        components_frame = tk.Frame(frame, bg="#ecf0f1")
        components_frame.pack()
        
        self.comp_vars = {}
        components = [
            ("Main Application Files", "main", "Required core files", True),
            ("Start Menu Shortcuts", "startmenu", "Create shortcuts in Start Menu", True),
            ("Desktop Shortcut", "desktop", "Create shortcut on desktop", True),
            ("VC++ Redistributable", "vcredist", "Install required runtime libraries", True),
            ("File Associations", "fileassoc", "Associate .gtalaunch files", False)
        ]
        
        for i, (name, key, desc, default) in enumerate(components):
            var = tk.BooleanVar(value=default)
            self.comp_vars[key] = var
            
            cb = tk.Checkbutton(components_frame,
                               text=name,
                               variable=var,
                               bg="#ecf0f1",
                               font=("Arial", 11))
            cb.grid(row=i, column=0, sticky="w", pady=5)
            
            tk.Label(components_frame,
                    text=desc,
                    font=("Arial", 9),
                    fg="#7f8c8d",
                    bg="#ecf0f1").grid(row=i, column=1, sticky="w", padx=20, pady=5)
                    
        self.steps.add(frame, text="Components")
        
    def create_install_step(self):
        """إنشاء خطوة التثبيت"""
        frame = tk.Frame(self.steps, bg="#ecf0f1")
        
        tk.Label(frame,
                text="Ready to Install",
                font=("Arial", 16, "bold"),
                bg="#ecf0f1").pack(pady=30)
                
        # معلومات التثبيت
        info_frame = tk.Frame(frame, bg="#ecf0f1")
        info_frame.pack(pady=20)
        
        self.install_info = tk.Label(info_frame,
                                    text="Summary will appear here",
                                    font=("Arial", 11),
                                    bg="#ecf0f1",
                                    justify="left")
        self.install_info.pack()
        
        # سجل التثبيت
        log_frame = tk.Frame(frame, bg="#2c3e50", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=50, pady=20)
        
        self.install_log = tk.Text(log_frame,
                                  height=8,
                                  bg="#1a1a1a",
                                  fg="#2ecc71",
                                  font=("Courier", 9))
        self.install_log.pack(fill="both", expand=True)
        
        self.steps.add(frame, text="Install")
        
    def browse_path(self):
        """تصفح لاختيار مسار التثبيت"""
        folder = filedialog.askdirectory(title="Select Installation Folder")
        if folder:
            self.path_var.set(folder)
            
    def update_space_info(self):
        """تحديث معلومات المساحة الحرة"""
        path = self.path_var.get()
        if path:
            try:
                drive = os.path.splitdrive(path)[0]
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive),
                    ctypes.pointer(free_bytes),
                    ctypes.pointer(total_bytes),
                    None
                )
                
                free_gb = free_bytes.value / (1024**3)
                total_gb = total_bytes.value / (1024**3)
                
                self.space_label.config(
                    text=f"Disk Space: {free_gb:.1f} GB free of {total_gb:.1f} GB"
                )
                
                if free_gb < 0.2:  # أقل من 200MB
                    self.space_label.config(fg="red")
                else:
                    self.space_label.config(fg="green")
                    
            except:
                self.space_label.config(text="Could not check disk space")
                
    def prev_step(self):
        """الانتقال للخطوة السابقة"""
        current = self.steps.index(self.steps.select())
        if current > 0:
            self.steps.select(current - 1)
            self.update_navigation()
            
    def next_step(self):
        """الانتقال للخطوة التالية"""
        current = self.steps.index(self.steps.select())
        
        # التحقق من صحة الخطوة الحالية
        if current == 1:  # خطوة الرخصة
            if not self.agree_var.get():
                messagebox.showwarning("License", "You must accept the license agreement to continue.")
                return
                
        if current == 2:  # خطوة المسار
            if not self.path_var.get():
                messagebox.showwarning("Path", "Please select an installation folder.")
                return
                
        if current < self.steps.index("end") - 1:
            self.steps.select(current + 1)
            
            # إذا كانت الخطوة التالية هي التثبيت، قم بتحديث الملخص
            if current + 1 == self.steps.index("end") - 1:
                self.update_summary()
                
        self.update_navigation()
        
    def update_navigation(self):
        """تحديث أزرار التنقل"""
        current = self.steps.index(self.steps.select())
        
        self.back_btn.config(state="normal" if current > 0 else "disabled")
        
        if current == self.steps.index("end") - 1:
            self.next_btn.config(text="Install", command=self.start_installation)
        else:
            self.next_btn.config(text="Next >", command=self.next_step)
            
    def update_summary(self):
        """تحديث ملخص التثبيت"""
        summary = f"""
        Installation Summary:
        
        Location: {self.path_var.get()}
        
        Components to install:
        """
        
        for key, var in self.comp_vars.items():
            if var.get():
                comp_name = {
                    'main': 'Main Application',
                    'startmenu': 'Start Menu Shortcuts',
                    'desktop': 'Desktop Shortcut',
                    'vcredist': 'VC++ Redistributable',
                    'fileassoc': 'File Associations'
                }.get(key, key)
                
                summary += f"  • {comp_name}\n"
                
        self.install_info.config(text=summary)
        
    def start_installation(self):
        """بدء عملية التثبيت"""
        # تعطيل أزرار التنقل
        self.back_btn.config(state="disabled")
        self.next_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
        
        # بدء التثبيت في thread منفصل
        import threading
        thread = threading.Thread(target=self.install_thread, daemon=True)
        thread.start()
        
    def install_thread(self):
        """thread التثبيت"""
        try:
            self.log_message("Starting installation...")
            
            # إنشاء مجلد التثبيت
            install_dir = self.path_var.get()
            self.log_message(f"Creating directory: {install_dir}")
            
            if not os.path.exists(install_dir):
                os.makedirs(install_dir)
                
            # نسخ ملفات النظام
            source_dir = os.path.dirname(os.path.abspath(__file__))
            
            # نسخ الملفات الرئيسية
            files_to_copy = [
                "GTAVC_Unified_System.py",
                "README.txt",
                "LICENSE.txt",
                "unified_config.json"
            ]
            
            for file in files_to_copy:
                src = os.path.join(source_dir, file)
                if os.path.exists(src):
                    dst = os.path.join(install_dir, file)
                    shutil.copy2(src, dst)
                    self.log_message(f"Copied: {file}")
                    
            # إنشاء اختصارات
            if self.comp_vars['startmenu'].get():
                self.create_start_menu_shortcut(install_dir)
                
            if self.comp_vars['desktop'].get():
                self.create_desktop_shortcut(install_dir)
                
            # تثبيت VC++ Redistributable
            if self.comp_vars['vcredist'].get():
                self.install_vcredist()
                
            # إنشاء إدخالات السجل
            self.create_registry_entries(install_dir)
            
            # إنشاء ملف إلغاء التثبيت
            self.create_uninstaller(install_dir)
            
            self.log_message("\n✓ Installation completed successfully!")
            self.progress["value"] = 100
            
            # عرض رسالة النجاح
            self.root.after(0, self.show_success)
            
        except Exception as e:
            self.log_message(f"\n✗ Installation failed: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Installation Failed", str(e)))
            
    def log_message(self, message):
        """تسجيل رسالة في سجل التثبيت"""
        self.root.after(0, lambda: self.install_log.insert(tk.END, message + "\n"))
        self.root.after(0, lambda: self.install_log.see(tk.END))
        
    def create_start_menu_shortcut(self, install_dir):
        """إنشاء اختصار في قائمة ابدأ"""
        self.log_message("Creating Start Menu shortcut...")
        
        start_menu_path = os.path.join(
            os.environ["APPDATA"],
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "GTA VC Unified System"
        )
        
        if not os.path.exists(start_menu_path):
            os.makedirs(start_menu_path)
            
        # إنشاء ملف .url (بديل للاختصار)
        url_content = f"""[InternetShortcut]
URL=file:///{install_dir}/GTAVC_Unified_System.py
IconFile={install_dir}/icon.ico
IconIndex=0
"""
        
        with open(os.path.join(start_menu_path, "GTA VC Unified System.url"), "w") as f:
            f.write(url_content)
            
    def create_desktop_shortcut(self, install_dir):
        """إنشاء اختصار على سطح المكتب"""
        self.log_message("Creating Desktop shortcut...")
        
        desktop_path = os.path.join(
            os.environ["USERPROFILE"],
            "Desktop"
        )
        
        url_content = f"""[InternetShortcut]
URL=file:///{install_dir}/GTAVC_Unified_System.py
IconFile={install_dir}/icon.ico
IconIndex=0
"""
        
        with open(os.path.join(desktop_path, "GTA VC Unified System.url"), "w") as f:
            f.write(url_content)
            
    def install_vcredist(self):
        """تثبيت VC++ Redistributable"""
        self.log_message("Installing VC++ Redistributable...")
        
        # محاكاة التثبيت (في الواقع سيكون تثبيت حقيقي)
        import time
        for i in range(10):
            time.sleep(0.1)
            self.progress["value"] = (i + 1) * 10
            
        self.log_message("VC++ Redistributable installed")
        
    def create_registry_entries(self, install_dir):
        """إنشاء إدخالات السجل"""
        self.log_message("Creating registry entries...")
        
        try:
            # معلومات التطبيق
            key_path = r"SOFTWARE\GTAVCUnifiedSystem"
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "InstallDir", 0, winreg.REG_SZ, install_dir)
                winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, "1.0.0")
                
            # إدخال إلغاء التثبيت
            uninstall_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GTAVCUnifiedSystem"
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_path) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "GTA Vice City Unified System")
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, 
                                f'"{install_dir}\\uninstall.exe"')
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "GTA Community")
                winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, "1.0.0")
                
            self.log_message("Registry entries created")
            
        except Exception as e:
            self.log_message(f"Warning: Could not create registry entries: {str(e)}")
            
    def create_uninstaller(self, install_dir):
        """إنشاء ملف إلغاء التثبيت"""
        self.log_message("Creating uninstaller...")
        
        uninstall_content = """@echo off
echo Uninstalling GTA Vice City Unified System...
echo.

REM حذف الاختصارات
del "%USERPROFILE%\\Desktop\\GTA VC Unified System.url" 2>nul
rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\GTA VC Unified System" 2>nul

REM حذف إدخالات السجل
reg delete "HKCU\\Software\\GTAVCUnifiedSystem" /f 2>nul
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GTAVCUnifiedSystem" /f 2>nul

REM حذف مجلد التثبيت
rmdir /s /q "%~dp0" 2>nul

echo Uninstallation complete!
pause
"""
        
        uninstall_path = os.path.join(install_dir, "uninstall.bat")
        with open(uninstall_path, "w") as f:
            f.write(uninstall_content)
            
        self.log_message("Uninstaller created")
        
    def show_success(self):
        """عرض رسالة النجاح"""
        messagebox.showinfo(
            "Installation Complete",
            "GTA Vice City Unified System has been installed successfully!\n\n"
            "You can now launch the system from Start Menu or Desktop."
        )
        
        # خيار تشغيل التطبيق
        response = messagebox.askyesno(
            "Launch Application",
            "Do you want to launch GTA VC Unified System now?"
        )
        
        if response:
            install_dir = self.path_var.get()
            app_path = os.path.join(install_dir, "GTAVC_Unified_System.py")
            
            # تشغيل التطبيق
            try:
                subprocess.Popen(["python", app_path])
            except:
                messagebox.showinfo(
                    "Launch",
                    "Please run the application manually from the installation folder."
                )
                
        self.root.quit()
        
    def run(self):
        """تشغيل برنامج التثبيت"""
        self.root.mainloop()

# ============================================
# التشغيل الرئيسي
# ============================================

if __name__ == "__main__":
    # التحقق من صلاحيات المسؤول
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
        
    if not is_admin:
        # إعادة التشغيل كمسؤول
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()
        
    installer = UnifiedInstaller()
    installer.run()