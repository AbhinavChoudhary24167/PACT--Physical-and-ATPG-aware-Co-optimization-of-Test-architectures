#include <cstdlib>
#include <cstring>
#include <iostream>
#include "interface/techlib_builder.h"
#include "interface/netlist_builder.h"
#include "core/circuit.h"
#include "core/simulator.h"

using namespace IntfNs;
using namespace CoreNs;

static int failure(const char *message) {
    std::cerr << message << "\n";
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 4) return failure("usage: compound_circuit_test LIB NETLIST depth|arity|truth");
    Techlib library;
    MdtLibBuilder libraryBuilder(&library);
    if (!libraryBuilder.read(argv[1])) return failure("library read failed");
    Netlist netlist;
    netlist.setTechlib(&library);
    VlogNlBuilder builder(&netlist);
    if (!builder.read(argv[2]) || !netlist.check()) return failure("netlist read failed");
    Circuit circuit;
    if (!circuit.buildCircuit(&netlist)) return failure("circuit build failed");
    if (circuit.numPI_ != 4 || circuit.numPPI_ != 1 || circuit.numPO_ != 1)
        return failure("fixture population changed");

    if (!std::strcmp(argv[3], "depth")) {
        for (const Gate &gate : circuit.circuitGates_) {
            if (gate.numLevel_ < 0 || gate.numLevel_ >= circuit.totalLvl_)
                return failure("gate lies outside the allocated circuit levels");
            for (int fanout : gate.fanoutVector_)
                if (circuit.circuitGates_[fanout].numLevel_ <= gate.numLevel_)
                    return failure("fanout level does not follow its driver");
        }
    } else if (!std::strcmp(argv[3], "arity")) {
        int and2 = 0, or2 = 0, inv = 0;
        for (const Gate &gate : circuit.circuitGates_) {
            if (gate.gateType_ == Gate::PI || gate.gateType_ == Gate::PPI ||
                gate.gateType_ == Gate::PO || gate.gateType_ == Gate::PPO) continue;
            if (gate.gateType_ == Gate::AND2 && gate.numFI_ == 2) ++and2;
            else if (gate.gateType_ == Gate::OR2 && gate.numFI_ == 2) ++or2;
            else if (gate.gateType_ == Gate::INV && gate.numFI_ == 1) ++inv;
            else return failure("compound-cell primitive type does not match its own inputs");
        }
        if (and2 != 1 || or2 != 2 || inv != 1)
            return failure("AOI211 primitive population changed");
    } else if (!std::strcmp(argv[3], "truth")) {
        Simulator simulator(&circuit);
        for (int word = 0; word < 32; ++word) {
            for (Gate &gate : circuit.circuitGates_) {
                if (gate.gateType_ != Gate::PI && gate.gateType_ != Gate::PPI) continue;
                int bit = 4;
                if (gate.gateType_ == Gate::PI) {
                    const char *name = netlist.getTop()->getPort(gate.cellId_)->name_;
                    const char *names[] = {"a", "b", "c", "e"};
                    for (bit = 0; bit < 4 && std::strcmp(name, names[bit]); ++bit) {}
                    if (bit == 4) return failure("unexpected functional input");
                }
                const bool value = (word >> bit) & 1;
                gate.goodSimLow_ = value ? PARA_L : PARA_H;
                gate.goodSimHigh_ = value ? PARA_H : PARA_L;
            }
            simulator.goodSim();
            const bool a = word & 1, b = word & 2, c = word & 4, e = word & 8;
            const bool nextState = !(a || b || (c && e));
            for (const Gate &gate : circuit.circuitGates_) {
                if (gate.gateType_ != Gate::PO && gate.gateType_ != Gate::PPO) continue;
                const bool expected = gate.gateType_ == Gate::PO ? bool(word & 16) : nextState;
                if (gate.goodSimLow_ != (expected ? PARA_L : PARA_H) ||
                    gate.goodSimHigh_ != (expected ? PARA_H : PARA_L))
                    return failure("FAN truth table disagrees with AOI211/Q semantics");
            }
        }
    } else return failure("unknown test mode");
    std::cout << argv[3] << " PASS\n";
    return 0;
}
