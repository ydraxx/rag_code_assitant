#include <string>
#include <map>

double computeRisk(const std::map<std::string, double>& positions) {
    double risk = 0.0;
    for (const auto& p : positions) {
        risk += p.second * 0.01;
    }
    return risk;
}
