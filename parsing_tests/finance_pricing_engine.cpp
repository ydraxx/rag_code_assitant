// finance_pricing_engine.cpp
#include <algorithm>
#include <chrono>
#include <cmath>
#include <exception>
#include <functional>
#include <future>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <stdexcept>
#include <string>
#include <thread>
#include <tuple>
#include <vector>
#include <variant>

namespace Finance {

    // Types d'instruments
    enum class InstrumentType { EuropeanOption, AsianOption, BarrierOption };

    // Données de marché
    struct MarketData {
        double spot;
        double rate;      // taux sans risque
        double volatility;
        double dividendYield;

        MarketData(double s, double r, double v, double q)
        : spot(s), rate(r), volatility(v), dividendYield(q) {}
    };

    // Base pour tout instrument
    class Instrument {
    public:
        virtual ~Instrument() = default;
        virtual InstrumentType type() const = 0;
        virtual double payoff(const std::vector<double>& path) const = 0;
    };

    // Option européenne vanilla
    class EuropeanOption : public Instrument {
    public:
        EuropeanOption(double strike, bool isCall)
        : K(strike), call(isCall) {}

        InstrumentType type() const override {
            return InstrumentType::EuropeanOption;
        }

        double payoff(const std::vector<double>& path) const override {
            double ST = path.back();
            return call ? std::max(ST - K, 0.0) : std::max(K - ST, 0.0);
        }

    private:
        double K;
        bool call;
    };

    // Générateur de trajectoires de prix
    class PathGenerator {
    public:
        PathGenerator(const MarketData& md, size_t steps, unsigned seed = std::random_device{}())
        : market(md), nSteps(steps), rng(seed), norm(0.0, 1.0) {}

        std::vector<double> generate() {
            std::vector<double> path;
            path.reserve(nSteps + 1);
            double S = market.spot;
            double dt = 1.0 / nSteps;
            path.push_back(S);

            for (size_t i = 1; i <= nSteps; ++i) {
                double z = norm(rng);
                // schéma d’Euler discretisé
                S *= std::exp((market.rate - market.dividendYield - 0.5 * market.volatility * market.volatility) * dt
                              + market.volatility * std::sqrt(dt) * z);
                path.push_back(S);
            }
            return path;
        }

    private:
        MarketData market;
        size_t nSteps;
        std::mt19937_64 rng;
        std::normal_distribution<double> norm;
    };

    // Résultat d'une simulation
    struct SimulationResult {
        double price;
        double stdError;
    };

    // Engine de pricing abstrait
    class PricingEngine {
    public:
        virtual ~PricingEngine() = default;
        virtual SimulationResult calculate(const Instrument& inst) = 0;
    };

    // Monte-Carlo pricing engine
    class MonteCarloEngine : public PricingEngine {
    public:
        MonteCarloEngine(const MarketData& md, size_t steps, size_t nSim, size_t nThreads = std::thread::hardware_concurrency())
        : market(md), stepsPerPath(steps), nSimulations(nSim), threadCount(std::max<size_t>(1, nThreads)) {}

        SimulationResult calculate(const Instrument& inst) override {
            if (nSimulations == 0) {
                throw std::invalid_argument("Number of simulations must be > 0");
            }

            std::vector<std::future<std::pair<double,double>>> futures;
            size_t simPerThread = nSimulations / threadCount;
            size_t remaining = nSimulations % threadCount;
            std::mutex mtx;

            auto worker = [&](size_t sims) {
                double sumPayoff = 0.0;
                double sumSqPayoff = 0.0;
                PathGenerator pg(market, stepsPerPath);

                for (size_t i = 0; i < sims; ++i) {
                    auto path = pg.generate();
                    double payoff = inst.payoff(path);
                    sumPayoff += payoff;
                    sumSqPayoff += payoff * payoff;
                }
                return std::make_pair(sumPayoff, sumSqPayoff);
            };

            // Lancer les threads
            for (size_t t = 0; t < threadCount; ++t) {
                size_t work = simPerThread + (t < remaining ? 1 : 0);
                futures.push_back(std::async(std::launch::async, worker, work));
            }

            // Collecter les résultats
            double totalSum = 0.0, totalSumSq = 0.0;
            for (auto& fut : futures) {
                auto [s, ss] = fut.get();
                totalSum += s;
                totalSumSq += ss;
            }

            double meanPayoff = totalSum / nSimulations;
            double variance = (totalSumSq / nSimulations) - (meanPayoff * meanPayoff);
            double stdError = std::sqrt(variance / nSimulations);
            // actualisation
            double discount = std::exp(-market.rate * 1.0);
            return { meanPayoff * discount, stdError * discount };
        }

    private:
        MarketData market;
        size_t stepsPerPath;
        size_t nSimulations;
        size_t threadCount;
    };

    // Factory pour choisir l’engine
    class EngineFactory {
    public:
        static std::unique_ptr<PricingEngine> create(const std::string& name,
                                                     const MarketData& md,
                                                     size_t steps,
                                                     size_t sims,
                                                     size_t threads = 0) {
            if (name == "MC") {
                return std::make_unique<MonteCarloEngine>(md, steps, sims, threads);
            }
            throw std::runtime_error("Engine '" + name + "' non supporté");
        }
    };

} // namespace Finance

int main(int argc, char* argv[]) {
    try {
        // Paramètres de marché
        Finance::MarketData md(100.0, 0.01, 0.2, 0.0);

        // Instrument : call européen strike 100
        Finance::EuropeanOption option(100.0, true);

        // Créer un engine Monte-Carlo
        auto engine = Finance::EngineFactory::create("MC", md, /*steps=*/252, /*sims=*/1000000, /*threads=*/4);

        // Lancer la simulation
        auto result = engine->calculate(option);

        std::cout << "Prix de l'option (MC)       : " << result.price << std::endl;
        std::cout << "Erreur standard (MC)        : " << result.stdError << std::endl;

    } catch (const std::exception& ex) {
        std::cerr << "Erreur : " << ex.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
