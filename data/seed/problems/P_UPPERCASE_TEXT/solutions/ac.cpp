#include <bits/stdc++.h>
using namespace std;

int main() {
    string line;
    while (getline(cin, line)) {
        for (char &c : line) c = toupper(static_cast<unsigned char>(c));
        cout << line << "\n";
    }
    return 0;
}
