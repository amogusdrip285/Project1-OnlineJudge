#include <cstddef>
#include <vector>

int main() {
    constexpr std::size_t bytes = 512ULL * 1024ULL * 1024ULL;
    std::vector<char> buf(bytes, 1);
    return buf[0] == 0 ? 1 : 0;
}
