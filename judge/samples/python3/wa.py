import sys


def main() -> None:
    data = sys.stdin.read().split()
    if len(data) >= 2:
        print(int(data[0]) + int(data[1]) + 1)


if __name__ == "__main__":
    main()
