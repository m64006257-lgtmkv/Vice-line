// MultiplayerCore.cpp - نواة المالتيميديا لـ GTA VC
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdio.h>
#include <vector>
#include <string>
#include <thread>
#include <atomic>
#include <mutex>
#include <map>
#include <cmath>

#pragma comment(lib, "ws2_32.lib")

// تعريفات الذاكرة لـ GTA VC (أوفسيت ديناميكية)
struct MemoryOffsets {
    DWORD baseAddress;
    DWORD playerPedPtr;
    DWORD entityList;
    DWORD vehiclesArray;
    DWORD pedsArray;
    DWORD worldPtr;
    DWORD gameState;
    DWORD maxEntities;
    DWORD entitySize;
};

// هيكل الكائن في الذاكرة (مبسط)
#pragma pack(push, 1)
struct Entity {
    DWORD type;          // 0x00
    DWORD handle;        // 0x04
    DWORD flags;         // 0x08
    float positionX;     // 0x14
    float positionY;     // 0x18
    float positionZ;     // 0x1C
    float rotationX;     // 0x20
    float rotationY;     // 0x24
    float rotationZ;     // 0x28
    float speedX;        // 0x30
    float speedY;        // 0x34
    float speedZ;        // 0x38
    DWORD modelId;       // 0x50
    DWORD playerId;      // 0x5C
    DWORD animation;     // 0x5A0
    DWORD aiState;       // 0x530
    DWORD health;        // 0x540
    DWORD armor;         // 0x548
    BYTE  pedType;       // 0x590
    BYTE  inVehicle;     // 0x58C
    DWORD vehiclePtr;    // 0x590
};
#pragma pack(pop)

// بيانات الشبكة المضغوطة
#pragma pack(push, 1)
struct NetworkPacket {
    BYTE packetType;      // نوع الحزمة
    DWORD playerId;       // معرف اللاعب
    float positionX;      // الموقع X
    float positionY;      // الموقع Y
    float positionZ;      // الموقع Z
    float rotationX;      // الدوران X
    float rotationY;      // الدوران Y
    float rotationZ;      // الدوران Z
    float speedX;         // السرعة X
    float speedY;         // السرعة Y
    float speedZ;         // السرعة Z
    WORD animation;       // الحركة
    BYTE weapon;          // السلاح
    BYTE health;          // الصحة (0-100)
    BYTE armor;           // الدروع (0-100)
    BYTE vehicleModel;    // نموذج المركبة
    DWORD timestamp;      // الطابع الزمني
};
#pragma pack(pop)

// أنواع الحزم
enum PacketType {
    PACKET_CONNECT = 0x01,
    PACKET_DISCONNECT = 0x02,
    PACKET_POSITION = 0x03,
    PACKET_VEHICLE = 0x04,
    PACKET_SHOOT = 0x05,
    PACKET_CHAT = 0x06,
    PACKET_SYNC = 0x07
};

// فئة مدير الشبكة
class NetworkManager {
private:
    SOCKET serverSocket;
    SOCKET clientSocket;
    sockaddr_in serverAddr;
    std::thread networkThread;
    std::atomic<bool> running;
    std::map<DWORD, sockaddr_in> clients;
    std::mutex clientsMutex;
    
    int port;
    bool isServer;
    
public:
    NetworkManager(int port = 5192, bool isServer = true) 
        : port(port), isServer(isServer), running(false) {
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            printf("WSAStartup failed\n");
        }
    }
    
    ~NetworkManager() {
        stop();
        WSACleanup();
    }
    
    bool start() {
        if (isServer) {
            return startServer();
        } else {
            return startClient();
        }
    }
    
    bool startServer() {
        serverSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (serverSocket == INVALID_SOCKET) {
            printf("Failed to create server socket\n");
            return false;
        }
        
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(port);
        serverAddr.sin_addr.s_addr = htonl(INADDR_ANY);
        
        if (bind(serverSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
            printf("Failed to bind server socket\n");
            closesocket(serverSocket);
            return false;
        }
        
        // تعيين خيار البث
        BOOL broadcast = TRUE;
        setsockopt(serverSocket, SOL_SOCKET, SO_BROADCAST, 
                  (char*)&broadcast, sizeof(broadcast));
        
        running = true;
        networkThread = std::thread(&NetworkManager::serverThread, this);
        
        printf("Server started on port %d\n", port);
        return true;
    }
    
    bool startClient() {
        clientSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (clientSocket == INVALID_SOCKET) {
            printf("Failed to create client socket\n");
            return false;
        }
        
        // تمكين البث
        BOOL broadcast = TRUE;
        setsockopt(clientSocket, SOL_SOCKET, SO_BROADCAST, 
                  (char*)&broadcast, sizeof(broadcast));
        
        running = true;
        networkThread = std::thread(&NetworkManager::clientThread, this);
        
        printf("Client network started\n");
        return true;
    }
    
    void stop() {
        running = false;
        if (networkThread.joinable()) {
            networkThread.join();
        }
        
        if (serverSocket != INVALID_SOCKET) {
            closesocket(serverSocket);
            serverSocket = INVALID_SOCKET;
        }
        
        if (clientSocket != INVALID_SOCKET) {
            closesocket(clientSocket);
            clientSocket = INVALID_SOCKET;
        }
        
        printf("Network manager stopped\n");
    }
    
    void serverThread() {
        char buffer[sizeof(NetworkPacket)];
        sockaddr_in clientAddr;
        int addrLen = sizeof(clientAddr);
        
        while (running) {
            int bytesReceived = recvfrom(serverSocket, buffer, sizeof(buffer), 0,
                                        (sockaddr*)&clientAddr, &addrLen);
            
            if (bytesReceived > 0) {
                if (bytesReceived == sizeof(NetworkPacket)) {
                    NetworkPacket* packet = (NetworkPacket*)buffer;
                    processPacket(packet, clientAddr);
                }
            }
        }
    }
    
    void clientThread() {
        // دور العميل في الاستماع للبث
        sockaddr_in listenAddr;
        listenAddr.sin_family = AF_INET;
        listenAddr.sin_port = htons(port);
        listenAddr.sin_addr.s_addr = htonl(INADDR_ANY);
        
        SOCKET listenSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (listenSocket == INVALID_SOCKET) {
            printf("Failed to create listen socket\n");
            return;
        }
        
        if (bind(listenSocket, (sockaddr*)&listenAddr, sizeof(listenAddr)) == SOCKET_ERROR) {
            printf("Failed to bind listen socket\n");
            closesocket(listenSocket);
            return;
        }
        
        char buffer[sizeof(NetworkPacket)];
        sockaddr_in serverAddr;
        int addrLen = sizeof(serverAddr);
        
        while (running) {
            int bytesReceived = recvfrom(listenSocket, buffer, sizeof(buffer), 0,
                                        (sockaddr*)&serverAddr, &addrLen);
            
            if (bytesReceived == sizeof(NetworkPacket)) {
                NetworkPacket* packet = (NetworkPacket*)buffer;
                if (packet->packetType == PACKET_CONNECT) {
                    // اكتشاف سيرفر
                    char ipStr[INET_ADDRSTRLEN];
                    inet_ntop(AF_INET, &serverAddr.sin_addr, ipStr, INET_ADDRSTRLEN);
                    
                    // الاتصال بالسيرفر
                    connectToServer(ipStr, ntohs(serverAddr.sin_port));
                }
            }
        }
        
        closesocket(listenSocket);
    }
    
    void processPacket(NetworkPacket* packet, sockaddr_in& clientAddr) {
        std::lock_guard<std::mutex> lock(clientsMutex);
        
        switch (packet->packetType) {
            case PACKET_CONNECT:
                clients[packet->playerId] = clientAddr;
                printf("Player %d connected from %s:%d\n", 
                       packet->playerId, 
                       inet_ntoa(clientAddr.sin_addr), 
                       ntohs(clientAddr.sin_port));
                broadcastPacket(packet, clientAddr);
                break;
                
            case PACKET_DISCONNECT:
                clients.erase(packet->playerId);
                printf("Player %d disconnected\n", packet->playerId);
                broadcastPacket(packet, clientAddr);
                break;
                
            case PACKET_POSITION:
                broadcastPacket(packet, clientAddr);
                break;
                
            default:
                broadcastPacket(packet, clientAddr);
                break;
        }
    }
    
    void broadcastPacket(NetworkPacket* packet, sockaddr_in& excludeAddr) {
        for (auto& client : clients) {
            if (memcmp(&client.second, &excludeAddr, sizeof(sockaddr_in)) != 0) {
                sendto(serverSocket, (char*)packet, sizeof(NetworkPacket), 0,
                      (sockaddr*)&client.second, sizeof(sockaddr_in));
            }
        }
    }
    
    bool connectToServer(const char* ip, int port) {
        sockaddr_in serverAddr;
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(port);
        inet_pton(AF_INET, ip, &serverAddr.sin_addr);
        
        // إرسال حزمة الاتصال
        NetworkPacket connectPacket;
        ZeroMemory(&connectPacket, sizeof(connectPacket));
        connectPacket.packetType = PACKET_CONNECT;
        connectPacket.playerId = GetCurrentProcessId(); // معرف فريد
        
        sendto(clientSocket, (char*)&connectPacket, sizeof(connectPacket), 0,
              (sockaddr*)&serverAddr, sizeof(serverAddr));
        
        printf("Connected to server %s:%d\n", ip, port);
        return true;
    }
    
    bool sendPacket(NetworkPacket* packet) {
        if (isServer) {
            // السيرفر يبث للجميع
            for (auto& client : clients) {
                sendto(serverSocket, (char*)packet, sizeof(NetworkPacket), 0,
                      (sockaddr*)&client.second, sizeof(sockaddr_in));
            }
        } else {
            // العميل يرسل للسيرفر
            // (يجب معرفة عنوان السيرفر أولاً)
        }
        return true;
    }
    
    size_t getClientCount() const {
        return clients.size();
    }
};

// فئة إدارة الكائنات
class EntityManager {
private:
    MemoryOffsets offsets;
    HANDLE processHandle;
    DWORD processId;
    DWORD baseAddress;
    
    std::map<DWORD, DWORD> remotePlayers; // playerId -> entityAddress
    std::mutex entitiesMutex;
    
public:
    EntityManager() : processHandle(NULL), processId(0), baseAddress(0) {
        // تحديد الأوفست تلقائياً
        detectOffsets();
    }
    
    bool attachToProcess(const char* processName) {
        // البحث عن العملية
        HWND hwnd = FindWindowA(NULL, "GTA: Vice City");
        if (!hwnd) {
            printf("GTA Vice City window not found\n");
            return false;
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
            offsets.baseAddress = baseAddress;
            printf("Process attached. Base address: 0x%08X\n", baseAddress);
        }
        
        return true;
    }
    
    void detectOffsets() {
        // محاولة كشف النسخة وتحديد الأوفست
        offsets.playerPedPtr = 0x00B7CD98;
        offsets.entityList = 0x00B74490;
        offsets.vehiclesArray = 0x00B74494;
        offsets.pedsArray = 0x00B74490;
        offsets.maxEntities = 400;
        offsets.entitySize = 0x198;
    }
    
    Entity readEntity(DWORD address) {
        Entity entity;
        SIZE_T bytesRead;
        if (ReadProcessMemory(processHandle, (LPCVOID)address, &entity, sizeof(Entity), &bytesRead)) {
            return entity;
        }
        return Entity{0};
    }
    
    bool writeEntity(DWORD address, const Entity& entity) {
        SIZE_T bytesWritten;
        return WriteProcessMemory(processHandle, (LPVOID)address, &entity, sizeof(Entity), &bytesWritten);
    }
    
    DWORD findFreeEntitySlot() {
        DWORD entityList = baseAddress + offsets.entityList;
        
        for (DWORD i = 0; i < offsets.maxEntities; i++) {
            DWORD entityAddr = entityList + (i * offsets.entitySize);
            Entity entity = readEntity(entityAddr);
            
            if (entity.type == 0) { // فتحة فارغة
                return entityAddr;
            }
        }
        
        return 0;
    }
    
    DWORD createRemotePlayer(DWORD playerId, float x, float y, float z) {
        std::lock_guard<std::mutex> lock(entitiesMutex);
        
        DWORD entityAddr = findFreeEntitySlot();
        if (!entityAddr) {
            printf("No free entity slots available\n");
            return 0;
        }
        
        Entity entity = {0};
        entity.type = 1; // مشاة
        entity.playerId = playerId;
        entity.positionX = x;
        entity.positionY = y;
        entity.positionZ = z;
        entity.health = 100;
        entity.aiState = 0; // تعطيل الذكاء الاصطناعي
        entity.pedType = 6; // نوع المدني
        
        if (writeEntity(entityAddr, entity)) {
            remotePlayers[playerId] = entityAddr;
            printf("Created remote player %d at 0x%08X\n", playerId, entityAddr);
            return entityAddr;
        }
        
        return 0;
    }
    
    void updateRemotePlayer(DWORD playerId, NetworkPacket* packet) {
        std::lock_guard<std::mutex> lock(entitiesMutex);
        
        auto it = remotePlayers.find(playerId);
        if (it != remotePlayers.end()) {
            Entity entity = readEntity(it->second);
            
            // تحديث الموقع
            entity.positionX = packet->positionX;
            entity.positionY = packet->positionY;
            entity.positionZ = packet->positionZ;
            
            // تحديث الدوران
            entity.rotationX = packet->rotationX;
            entity.rotationY = packet->rotationY;
            entity.rotationZ = packet->rotationZ;
            
            // تحديث السرعة
            entity.speedX = packet->speedX;
            entity.speedY = packet->speedY;
            entity.speedZ = packet->speedZ;
            
            // تحديث الحركة
            entity.animation = packet->animation;
            
            // تحديث الصحة والدروع
            entity.health = packet->health;
            entity.armor = packet->armor;
            
            writeEntity(it->second, entity);
        }
    }
    
    void destroyRemotePlayer(DWORD playerId) {
        std::lock_guard<std::mutex> lock(entitiesMutex);
        
        auto it = remotePlayers.find(playerId);
        if (it != remotePlayers.end()) {
            Entity entity = {0};
            writeEntity(it->second, entity);
            remotePlayers.erase(it);
            printf("Destroyed remote player %d\n", playerId);
        }
    }
    
    void getLocalPlayerData(NetworkPacket* packet) {
        DWORD playerPtr = baseAddress + offsets.playerPedPtr;
        DWORD playerAddr;
        SIZE_T bytesRead;
        
        if (ReadProcessMemory(processHandle, (LPCVOID)playerPtr, &playerAddr, sizeof(DWORD), &bytesRead) && playerAddr) {
            Entity player = readEntity(playerAddr);
            
            packet->positionX = player.positionX;
            packet->positionY = player.positionY;
            packet->positionZ = player.positionZ;
            
            packet->rotationX = player.rotationX;
            packet->rotationY = player.rotationY;
            packet->rotationZ = player.rotationZ;
            
            packet->speedX = player.speedX;
            packet->speedY = player.speedY;
            packet->speedZ = player.speedZ;
            
            packet->health = (BYTE)player.health;
            packet->armor = (BYTE)player.armor;
            packet->animation = (WORD)player.animation;
        }
    }
    
    void cleanup() {
        for (auto& player : remotePlayers) {
            destroyRemotePlayer(player.first);
        }
        
        if (processHandle) {
            CloseHandle(processHandle);
            processHandle = NULL;
        }
        
        printf("Entity manager cleaned up\n");
    }
    
    size_t getPlayerCount() const {
        return remotePlayers.size();
    }
};

// النظام الرئيسي
class MultiplayerCore {
private:
    NetworkManager* network;
    EntityManager* entities;
    std::thread syncThread;
    std::atomic<bool> running;
    
    DWORD localPlayerId;
    bool isHost;
    
public:
    MultiplayerCore(bool isHost = true) 
        : isHost(isHost), running(false), localPlayerId(GetCurrentProcessId()) {
        network = new NetworkManager(5192, isHost);
        entities = new EntityManager();
    }
    
    ~MultiplayerCore() {
        stop();
        delete network;
        delete entities;
    }
    
    bool initialize() {
        if (!entities->attachToProcess("gta-vc.exe")) {
            printf("Failed to attach to GTA VC process\n");
            return false;
        }
        
        if (!network->start()) {
            printf("Failed to start network\n");
            return false;
        }
        
        running = true;
        syncThread = std::thread(&MultiplayerCore::syncLoop, this);
        
        printf("Multiplayer core initialized\n");
        return true;
    }
    
    void stop() {
        running = false;
        if (syncThread.joinable()) {
            syncThread.join();
        }
        
        network->stop();
        entities->cleanup();
        
        printf("Multiplayer core stopped\n");
    }
    
    void syncLoop() {
        NetworkPacket packet;
        ZeroMemory(&packet, sizeof(packet));
        packet.playerId = localPlayerId;
        
        while (running) {
            // الحصول على بيانات اللاعب المحلي
            entities->getLocalPlayerData(&packet);
            packet.packetType = PACKET_POSITION;
            packet.timestamp = GetTickCount();
            
            // إرسال البيانات
            network->sendPacket(&packet);
            
            // انتظار للتحكم في معدل الإرسال (20Hz = 50ms)
            Sleep(50);
        }
    }
    
    // دالة لمعالجة الحزم الواردة
    void processIncomingPacket(NetworkPacket* packet) {
        if (packet->playerId == localPlayerId) {
            return; // تجاهل الحزم الخاصة بي
        }
        
        switch (packet->packetType) {
            case PACKET_CONNECT:
                // إنشاء لاعب جديد
                entities->createRemotePlayer(
                    packet->playerId,
                    packet->positionX,
                    packet->positionY,
                    packet->positionZ
                );
                break;
                
            case PACKET_POSITION:
                // تحديث موقع اللاعب
                entities->updateRemotePlayer(packet->playerId, packet);
                break;
                
            case PACKET_DISCONNECT:
                // إزالة لاعب
                entities->destroyRemotePlayer(packet->playerId);
                break;
        }
    }
    
    size_t getPlayerCount() const {
        return entities->getPlayerCount();
    }
    
    bool isRunning() const {
        return running;
    }
};

// المتغيرات العالمية
static MultiplayerCore* g_multiplayerCore = nullptr;

// نقطة دخول الـ DLL
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
        case DLL_PROCESS_ATTACH:
            // إنشاء النظام عند تحميل الـ DLL
            g_multiplayerCore = new MultiplayerCore(true); // true = host
            if (!g_multiplayerCore->initialize()) {
                delete g_multiplayerCore;
                g_multiplayerCore = nullptr;
            }
            break;
            
        case DLL_PROCESS_DETACH:
            // تنظيف النظام عند إلغاء تحميل الـ DLL
            if (g_multiplayerCore) {
                g_multiplayerCore->stop();
                delete g_multiplayerCore;
                g_multiplayerCore = nullptr;
            }
            break;
            
        case DLL_THREAD_ATTACH:
        case DLL_THREAD_DETACH:
            break;
    }
    
    return TRUE;
}

// دوال تصدير للاستدعاء من الخارج
extern "C" __declspec(dllexport) BOOL InitializeMultiplayer(bool isHost) {
    if (g_multiplayerCore) {
        g_multiplayerCore->stop();
        delete g_multiplayerCore;
    }
    
    g_multiplayerCore = new MultiplayerCore(isHost);
    return g_multiplayerCore->initialize();
}

extern "C" __declspec(dllexport) void ShutdownMultiplayer() {
    if (g_multiplayerCore) {
        g_multiplayerCore->stop();
        delete g_multiplayerCore;
        g_multiplayerCore = nullptr;
    }
}

extern "C" __declspec(dllexport) BOOL IsMultiplayerActive() {
    return g_multiplayerCore != nullptr && g_multiplayerCore->isRunning();
}

extern "C" __declspec(dllexport) DWORD GetPlayerCount() {
    if (g_multiplayerCore) {
        return (DWORD)g_multiplayerCore->getPlayerCount();
    }
    return 0;
}