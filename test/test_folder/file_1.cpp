#include <iostream>
#include <vector>

class Trade {
public:
    Trade(int id, double amount) : id(id), amount(amount) {}
    void print() const {
        std::cout << "Trade ID: " << id << ", Amount: " << amount << std::endl;
    }

private:
    int id;
    double amount;
};

int main() {
    Trade t(42, 1500.5);
    t.print();
    return 0;
}
