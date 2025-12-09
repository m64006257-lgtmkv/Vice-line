// MultiplayerCore_Enhanced.cpp
// نواة متعددة اللاعبين محسنة مع واجهة تحكم لـ Python

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>
#include <string>
#include <thread>
#include <atomic>
#include <mutex>
#include <map>
#include <fstream>

// استخدام JSON مبسط بدلاً من jsoncpp
#define USE_SIMPLE_JSON

#ifdef USE_SIMPLE_JSON
// تنفيذ JSON مبسط
#include <sstream>
#include <iomanip>

class SimpleJSON {
private:
    std::stringstream ss;
    bool firstItem = true;
    
public:
    SimpleJSON() {
        ss << "{";
    }
    
    void addString(const std::string& key, const std::string& value) {
        if (!firstItem) ss << ",";
        ss << "\"" << key << "\":\"" << value << "\"";
        firstItem = false;
    }
    
    void addInt(const std::string& key, int value) {
        if (!firstItem) ss << ",";
        ss << "\"" << key << "\":" << value;
        firstItem = false;
    }
    
    void addBool(const std::string& key, bool value) {
        if (!firstItem) ss << ",";
        ss << "\"" << key << "\":" << (value ? "true" : "false");
        firstItem = false;
    }
    
    void addObject(const std::string& key, const SimpleJSON& obj) {
        if (!firstItem) ss << ",";
        ss << "\"" << key << "\":" << obj.toString();
        firstItem = false;
    }
    
    std::string toString() const {
        return ss.str() + "}";
    }
    
    static SimpleJSON create() {
        return SimpleJSON();
    }
};
#else
// إذا كنت تريد استخدام jsoncpp، فقم بتثبيته أولاً
// #include <json/json.h>
#endif

#pragma comment(lib, "ws2_32.lib")
// #pragma comment(lib, "jsoncpp.lib") // إلغاء التعليق إذا كنت تستخدم jsoncpp

// ============================================
// تعريفات واجهة التحكم
// ============================================

#define CONTROL_PORT 52525  // منفذ التحكم المحلي
#define MAX_PACKET_SIZE 4096

// أنواع أوامر التحكم
enum ControlCommand {
    CMD_INIT = 1,
    CMD_SHUTDOWN = 2,
    CMD_UPDATE_CONFIG = 3,
    CMD_SEND_CHAT = 4,
    CMD_GET_STATUS = 5,
    CMD_CREATE_PLAYER = 6,
    CMD_REMOVE_PLAYER = 7,
    CMD_UPDATE_PLAYER = 8,
    CMD_READ_MEMORY = 9,
    CMD_WRITE_MEMORY = 10
};

// هيكل أوفسيت الذاكرة
struct MemoryOffset {
    std::string name;
    DWORD offset;
    DWORD size;
    DWORD value;
};

// هيكل إجابة التحكم
#pragma pack(push, 1)
struct ControlResponse {
    DWORD command;
    DWORD status;
    DWORD dataSize;
    BYTE data[MAX_PACKET_SIZE - 12];
};
#pragma pack(pop)

// ============================================
// فئة مدير الذاكرة المتكامل
// ============================================

class IntegratedMemoryManager {
private:
    HANDLE processHandle;
    DWORD processId;
    DWORD baseAddress;
    
    std::map<std::string, MemoryOffset> memoryOffsets;
    std::map<DWORD, DWORD> remotePlayers; // playerID -> entityAddress
    
    std::mutex memoryMutex;
    
public:
    IntegratedMemoryManager() : processHandle(NULL), processId(0), baseAddress(0) {
        LoadDefaultOffsets();
    }
    
    ~IntegratedMemoryManager() {
        Detach();
    }
    
    bool Attach(const char* processName) {
        // البحث عن نافذة GTA VC
        HWND hwnd = FindWindowA(NULL, "GTA: Vice City");
        if (!hwnd) {
            hwnd = FindWindowA(NULL, "Grand Theft Auto: Vice City");
            if (!hwnd) {
                printf("GTA Vice City window not found\n");
                return false;
            }
        }
        
        GetWindowThreadProcessId(hwnd, &processId);
        processHandle = OpenProcess(PROCESS_ALL_ACCESS, FALSE, processId);
        
        if (!processHandle) {
            printf("Failed to open process %d\n", processId);
            return false;
        }
        
        // الحصول على عنوان الأساس
        HMODULE modules[1024];
        DWORD needed;
        if (EnumProcessModules(processHandle, modules, sizeof(modules), &needed)) {
            baseAddress = (DWORD)modules[0];
            printf("Base address: 0x%08X\n", baseAddress);
        }
        
        // تحديث الأوفست بناءً على الإصدار
        DetectGameVersion();
        
        return true;
    }
    
    void Detach() {
        if (processHandle) {
            CloseHandle(processHandle);
            processHandle = NULL;
        }
    }
    
    void LoadDefaultOffsets() {
        // أوفسيت الذاكرة الافتراضية
        memoryOffsets["player_ped_ptr"] = { "player_ped_ptr", 0x00B7CD98, 4, 0 };
        memoryOffsets["entity_list"] = { "entity_list", 0x00B74490, 4, 0 };
        memoryOffsets["camera_ptr"] = { "camera_ptr", 0x00B6F028, 4, 0 };
        memoryOffsets["game_state"] = { "game_state", 0x00B7CB54, 4, 0 };
        memoryOffsets["world_ptr"] = { "world_ptr", 0x00B79594, 4, 0 };
        memoryOffsets["max_entities"] = { "max_entities", 0x00000190, 4, 400 };
        memoryOffsets["entity_size"] = { "entity_size", 0x00000198, 4, 408 };
    }
    
    void DetectGameVersion() {
        if (!baseAddress) return;
        
        // قراءة توقيع الذاكرة لتحديد الإصدار
        BYTE signature[64];
        SIZE_T bytesRead;
        
        if (ReadProcessMemory(processHandle, (LPCVOID)baseAddress, signature, 64, &bytesRead) && bytesRead == 64) {
            // التحقق من الإصدارات المختلفة
            // GTA VC 1.0 - تحقق بسيط
            if (signature[0] == 0x4D && signature[1] == 0x5A) {  // MZ header
                // يمكن إضافة كشف أكثر دقة هنا
                printf("Detected GTA VC executable\n");
            }
        }
    }
    
    DWORD ReadMemory(DWORD address, DWORD size, BYTE* buffer) {
        if (!processHandle || !buffer || size == 0) return 0;
        
        SIZE_T bytesRead = 0;
        if (ReadProcessMemory(processHandle, (LPCVOID)address, buffer, size, &bytesRead)) {
            return (DWORD)bytesRead;
        }
        return 0;
    }
    
    DWORD WriteMemory(DWORD address, DWORD size, BYTE* buffer) {
        if (!processHandle || !buffer || size == 0) return 0;
        
        SIZE_T bytesWritten = 0;
        if (WriteProcessMemory(processHandle, (LPVOID)address, buffer, size, &bytesWritten)) {
            return (DWORD)bytesWritten;
        }
        return 0;
    }
    
    DWORD GetOffsetAddress(const std::string& offsetName) {
        auto it = memoryOffsets.find(offsetName);
        if (it != memoryOffsets.end()) {
            return baseAddress + it->second.offset;
        }
        return 0;
    }
    
    DWORD FindFreeEntitySlot() {
        DWORD entityList = GetOffsetAddress("entity_list");
        if (!entityList) return 0;
        
        DWORD maxEntities = memoryOffsets["max_entities"].value;
        DWORD entitySize = memoryOffsets["entity_size"].value;
        
        for (DWORD i = 0; i < maxEntities; i++) {
            DWORD entityAddr = entityList + (i * entitySize);
            DWORD entityType = 0;
            ReadMemory(entityAddr, 4, (BYTE*)&entityType);
            
            if (entityType == 0) {
                return entityAddr;
            }
        }
        
        return 0;
    }
    
    DWORD CreateRemotePlayer(DWORD playerId, float x, float y, float z) {
        std::lock_guard<std::mutex> lock(memoryMutex);
        
        DWORD entityAddr = FindFreeEntitySlot();
        if (!entityAddr) {
            printf("No free entity slots available\n");
            return 0;
        }
        
        // هيكل مبسط للكائن
        struct Entity {
            DWORD type;
            float posX, posY, posZ;
            float rotX, rotY, rotZ;
            DWORD playerId;
            DWORD aiState;
        };
        
        Entity entity = {0};
        entity.type = 1; // مشاة
        entity.playerId = playerId;
        entity.posX = x;
        entity.posY = y;
        entity.posZ = z;
        entity.aiState = 0; // تعطيل الذكاء الاصطناعي
        
        if (WriteMemory(entityAddr, sizeof(Entity), (BYTE*)&entity) > 0) {
            remotePlayers[playerId] = entityAddr;
            printf("Created remote player %d at 0x%08X\n", playerId, entityAddr);
            return entityAddr;
        }
        
        return 0;
    }
    
    void UpdateRemotePlayer(DWORD playerId, float x, float y, float z, 
                           float rx, float ry, float rz) {
        std::lock_guard<std::mutex> lock(memoryMutex);
        
        auto it = remotePlayers.find(playerId);
        if (it != remotePlayers.end()) {
            float position[3] = { x, y, z };
            float rotation[3] = { rx, ry, rz };
            
            WriteMemory(it->second + 0x14, 12, (BYTE*)position); // الموقع
            WriteMemory(it->second + 0x20, 12, (BYTE*)rotation); // الدوران
        }
    }
    
    void RemoveRemotePlayer(DWORD playerId) {
        std::lock_guard<std::mutex> lock(memoryMutex);
        
        auto it = remotePlayers.find(playerId);
        if (it != remotePlayers.end()) {
            DWORD zero = 0;
            WriteMemory(it->second, 4, (BYTE*)&zero); // إعادة النوع إلى 0
            remotePlayers.erase(it);
            printf("Removed remote player %d\n", playerId);
        }
    }
    
    int GetPlayerCount() const {
        return (int)remotePlayers.size();
    }
    
    std::string GetPlayerPositionJSON(DWORD playerId) {
        auto it = remotePlayers.find(playerId);
        if (it != remotePlayers.end()) {
            float position[3];
            if (ReadMemory(it->second + 0x14, 12, (BYTE*)position) > 0) {
                SimpleJSON json = SimpleJSON::create();
                json.addFloat("x", position[0]);
                json.addFloat("y", position[1]);
                json.addFloat("z", position[2]);
                return json.toString();
            }
        }
        return "{}";
    }
    
    std::string GetAllOffsetsJSON() {
        SimpleJSON json = SimpleJSON::create();
        for (const auto& offset : memoryOffsets) {
            SimpleJSON offsetJson = SimpleJSON::create();
            offsetJson.addInt("offset", offset.second.offset);
            offsetJson.addInt("size", offset.second.size);
            offsetJson.addInt("value", offset.second.value);
            json.addObject(offset.first.c_str(), offsetJson);
        }
        return json.toString();
    }
    
    // دالة مساعدة لإضافة float إلى JSON
    void addFloat(const std::string& key, float value) {
        std::stringstream ss;
        ss << std::fixed << std::setprecision(2) << value;
        addString(key, ss.str());
    }
};

// ============================================
// فئة خادم التحكم المحلي
// ============================================

class ControlServer {
private:
    SOCKET controlSocket;
    std::thread serverThread;
    std::atomic<bool> running;
    
    IntegratedMemoryManager* memoryManager;
    
public:
    ControlServer(IntegratedMemoryManager* memMgr) 
        : controlSocket(INVALID_SOCKET), running(false), memoryManager(memMgr) {}
    
    ~ControlServer() {
        Stop();
    }
    
    bool Start() {
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            printf("WSAStartup failed\n");
            return false;
        }
        
        controlSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (controlSocket == INVALID_SOCKET) {
            printf("Failed to create socket\n");
            return false;
        }
        
        sockaddr_in serverAddr;
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(CONTROL_PORT);
        serverAddr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        
        if (bind(controlSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
            printf("Failed to bind socket\n");
            closesocket(controlSocket);
            WSACleanup();
            return false;
        }
        
        if (listen(controlSocket, 5) == SOCKET_ERROR) {
            printf("Failed to listen on socket\n");
            closesocket(controlSocket);
            WSACleanup();
            return false;
        }
        
        printf("Control server started on port %d\n", CONTROL_PORT);
        
        running = true;
        serverThread = std::thread(&ControlServer::ServerLoop, this);
        
        return true;
    }
    
    void Stop() {
        running = false;
        
        if (controlSocket != INVALID_SOCKET) {
            closesocket(controlSocket);
            controlSocket = INVALID_SOCKET;
        }
        
        if (serverThread.joinable()) {
            serverThread.join();
        }
        
        WSACleanup();
        printf("Control server stopped\n");
    }
    
    void ServerLoop() {
        while (running) {
            sockaddr_in clientAddr;
            int addrLen = sizeof(clientAddr);
            
            SOCKET clientSocket = accept(controlSocket, (sockaddr*)&clientAddr, &addrLen);
            if (clientSocket == INVALID_SOCKET) {
                continue;
            }
            
            // معالجة الاتصال في خيط منفصل
            std::thread clientThread(&ControlServer::HandleClient, this, clientSocket);
            clientThread.detach();
        }
    }
    
    void HandleClient(SOCKET clientSocket) {
        char buffer[MAX_PACKET_SIZE];
        int bytesReceived;
        
        while ((bytesReceived = recv(clientSocket, buffer, MAX_PACKET_SIZE, 0)) > 0) {
            ControlResponse response = ProcessCommand(buffer, bytesReceived);
            send(clientSocket, (char*)&response, 12 + response.dataSize, 0);
        }
        
        closesocket(clientSocket);
    }
    
    ControlResponse ProcessCommand(char* buffer, int size) {
        ControlResponse response = {0};
        
        if (size < 4) {
            response.status = 0xFFFFFFFF; // خطأ
            return response;
        }
        
        DWORD command = *(DWORD*)buffer;
        response.command = command;
        
        switch (command) {
            case CMD_INIT: {
                // تهيئة النظام
                if (memoryManager->Attach("gta-vc.exe")) {
                    response.status = 0x00000001; // نجاح
                    const char* msg = "Memory manager initialized";
                    strcpy_s((char*)response.data, sizeof(response.data), msg);
                    response.dataSize = (DWORD)strlen(msg) + 1;
                } else {
                    response.status = 0x00000000; // فشل
                    const char* msg = "Failed to attach to GTA VC";
                    strcpy_s((char*)response.data, sizeof(response.data), msg);
                    response.dataSize = (DWORD)strlen(msg) + 1;
                }
                break;
            }
            
            case CMD_GET_STATUS: {
                // الحصول على حالة النظام
                SimpleJSON status = SimpleJSON::create();
                status.addBool("attached", true);
                status.addInt("player_count", memoryManager->GetPlayerCount());
                status.addString("offsets", memoryManager->GetAllOffsetsJSON());
                
                std::string jsonStr = status.toString();
                strcpy_s((char*)response.data, sizeof(response.data), jsonStr.c_str());
                response.dataSize = (DWORD)jsonStr.length() + 1;
                response.status = 0x00000001;
                break;
            }
            
            case CMD_READ_MEMORY: {
                // قراءة الذاكرة
                if (size >= 12) {
                    DWORD address = *(DWORD*)(buffer + 4);
                    DWORD readSize = *(DWORD*)(buffer + 8);
                    
                    if (readSize > 0 && readSize <= MAX_PACKET_SIZE - 12) {
                        DWORD bytesRead = memoryManager->ReadMemory(
                            address, readSize, response.data);
                        
                        response.dataSize = bytesRead;
                        response.status = bytesRead > 0 ? 0x00000001 : 0x00000000;
                    }
                }
                break;
            }
            
            case CMD_WRITE_MEMORY: {
                // كتابة في الذاكرة
                if (size >= 12) {
                    DWORD address = *(DWORD*)(buffer + 4);
                    DWORD writeSize = *(DWORD*)(buffer + 8);
                    
                    if (writeSize > 0 && writeSize <= size - 12) {
                        DWORD bytesWritten = memoryManager->WriteMemory(
                            address, writeSize, (BYTE*)(buffer + 12));
                        
                        response.dataSize = 0;
                        response.status = bytesWritten > 0 ? 0x00000001 : 0x00000000;
                    }
                }
                break;
            }
            
            case CMD_CREATE_PLAYER: {
                // إنشاء لاعب جديد
                if (size >= 24) {
                    DWORD playerId = *(DWORD*)(buffer + 4);
                    float x = *(float*)(buffer + 8);
                    float y = *(float*)(buffer + 12);
                    float z = *(float*)(buffer + 16);
                    
                    DWORD entityAddr = memoryManager->CreateRemotePlayer(playerId, x, y, z);
                    
                    *(DWORD*)response.data = entityAddr;
                    response.dataSize = 4;
                    response.status = entityAddr > 0 ? 0x00000001 : 0x00000000;
                }
                break;
            }
            
            case CMD_UPDATE_PLAYER: {
                // تحديث لاعب
                if (size >= 32) {
                    DWORD playerId = *(DWORD*)(buffer + 4);
                    float x = *(float*)(buffer + 8);
                    float y = *(float*)(buffer + 12);
                    float z = *(float*)(buffer + 16);
                    float rx = *(float*)(buffer + 20);
                    float ry = *(float*)(buffer + 24);
                    float rz = *(float*)(buffer + 28);
                    
                    memoryManager->UpdateRemotePlayer(playerId, x, y, z, rx, ry, rz);
                    response.status = 0x00000001;
                }
                break;
            }
            
            default:
                response.status = 0xFFFFFFFF; // أمر غير معروف
                const char* msg = "Unknown command";
                strcpy_s((char*)response.data, sizeof(response.data), msg);
                response.dataSize = (DWORD)strlen(msg) + 1;
                break;
        }
        
        return response;
    }
};

// ============================================
// المتغيرات العامة
// ============================================

IntegratedMemoryManager* g_memoryManager = nullptr;
ControlServer* g_controlServer = nullptr;

// ============================================
// دوال التصدير
// ============================================

extern "C" __declspec(dllexport) BOOL APIENTRY InitializeCore() {
    // تهيئة مدير الذاكرة
    g_memoryManager = new IntegratedMemoryManager();
    
    // تهيئة خادم التحكم
    g_controlServer = new ControlServer(g_memoryManager);
    
    if (!g_controlServer->Start()) {
        delete g_controlServer;
        delete g_memoryManager;
        g_controlServer = nullptr;
        g_memoryManager = nullptr;
        return FALSE;
    }
    
    return TRUE;
}

extern "C" __declspec(dllexport) BOOL APIENTRY ShutdownCore() {
    if (g_controlServer) {
        g_controlServer->Stop();
        delete g_controlServer;
        g_controlServer = nullptr;
    }
    
    if (g_memoryManager) {
        delete g_memoryManager;
        g_memoryManager = nullptr;
    }
    
    return TRUE;
}

extern "C" __declspec(dllexport) DWORD GetControlPort() {
    return CONTROL_PORT;
}

extern "C" __declspec(dllexport) BOOL IsCoreInitialized() {
    return (g_memoryManager != nullptr && g_controlServer != nullptr);
}

// ============================================
// نقطة دخول DLL
// ============================================

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID lpReserved) {
    switch (reason) {
        case DLL_PROCESS_ATTACH:
            // يمكننا بدء التهيئة تلقائياً أو الانتظار لأمر من Python
            // InitializeCore(); // أو الانتظار لأمر صريح
            break;
            
        case DLL_PROCESS_DETACH:
            ShutdownCore();
            break;
            
        case DLL_THREAD_ATTACH:
        case DLL_THREAD_DETACH:
            break;
    }
    return TRUE;
}