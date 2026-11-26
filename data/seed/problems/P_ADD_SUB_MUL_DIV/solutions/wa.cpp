// Uses 32-bit int: overflows on the large tests, so it must NOT get AC (expected PARTIAL).
#include <bits/stdc++.h>
using namespace std;

int main() {
    int a, b;
    cin >> a >> b;
    cout << a + b << "\n" << a - b << "\n" << a * b << "\n" << a / b << "\n";
    return 0;
}
