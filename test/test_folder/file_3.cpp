#include <iostream>
#include <vector>

// Macro
#define PI 3.14

// Typedef
typedef int entier;

// Using
using Vec = std::vector<int>;

// Enum
enum Color { RED, GREEN, BLUE };

// Namespace
namespace Geometry {
    int area(int w, int h) {
        return w * h;
    }
}

// Class avec champs et méthodes
class MyClass {
private:
    int x;
    float y;

public:
    MyClass(int val) : x(val), y(0.0f) {}

    void display() const {
        std::cout << "x: " << x << std::endl;
    }

    int getX() const;

    ~MyClass() {}
};

// Déclaration de fonction (sans implémentation)
int MyClass::getX() const;

// Fonction globale
void say_hello() {
    std::cout << "Hello, world!" << std::endl;
}

// Struct
struct Point {
    double x, y;
};

// Template
template<typename T>
T add(T a, T b) {
    return a + b;
}
