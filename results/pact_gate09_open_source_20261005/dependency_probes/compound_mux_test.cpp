#include <cstring>
#include <iostream>
#include "interface/techlib_builder.h"
#include "interface/netlist_builder.h"
#include "core/circuit.h"
#include "core/simulator.h"
using namespace IntfNs;
using namespace CoreNs;
static int failure(const char *message) { std::cerr << message << "\n"; return 1; }
int main(int argc, char **argv) {
    if (argc != 4) return failure("usage: compound_mux_test LIB NETLIST arity|truth");
    Techlib library;
    MdtLibBuilder libraryBuilder(&library);
    if (!libraryBuilder.read(argv[1])) return failure("library read failed");
    Netlist netlist;
    netlist.setTechlib(&library);
    VlogNlBuilder builder(&netlist);
    if (!builder.read(argv[2]) || !netlist.check()) return failure("netlist read failed");
    Circuit circuit;
    if (!circuit.buildCircuit(&netlist)) return failure("circuit build failed");
    if (circuit.numPI_ != 3 || circuit.numPPI_ != 1 || circuit.numPO_ != 1)
        return failure("fixture population changed");
    if (!std::strcmp(argv[3], "arity")) {
        for (const Gate &gate : circuit.circuitGates_) {
            if (gate.gateType_ == Gate::PI || gate.gateType_ == Gate::PPI ||
                gate.gateType_ == Gate::PO || gate.gateType_ == Gate::PPO) continue;
            Cell *cell = netlist.getTop()->getCell(gate.cellId_);
            Cell *primitive = cell->libc_->getCell(gate.primitiveId_);
            int inputs = 0;
            for (int pin = 0; pin < primitive->getNPort(); ++pin)
                if (primitive->getPort(pin)->type_ == Port::INPUT) ++inputs;
            if (gate.numFI_ != inputs) return failure("receiver sharing a primitive net became an extra fanin");
        }
    } else if (!std::strcmp(argv[3], "truth")) {
        Simulator simulator(&circuit);
        for (int word = 0; word < 16; ++word) {
            for (Gate &gate : circuit.circuitGates_) {
                if (gate.gateType_ != Gate::PI && gate.gateType_ != Gate::PPI) continue;
                int bit = 3;
                if (gate.gateType_ == Gate::PI) {
                    const char *name = netlist.getTop()->getPort(gate.cellId_)->name_;
                    const char *names[] = {"a", "b", "s"};
                    for (bit = 0; bit < 3 && std::strcmp(name, names[bit]); ++bit) {}
                    if (bit == 3) return failure("unexpected functional input");
                }
                bool value = (word >> bit) & 1;
                gate.goodSimLow_ = value ? PARA_L : PARA_H;
                gate.goodSimHigh_ = value ? PARA_H : PARA_L;
            }
            simulator.goodSim();
            bool nextState = (word & 4) ? bool(word & 2) : bool(word & 1);
            for (const Gate &gate : circuit.circuitGates_) {
                if (gate.gateType_ != Gate::PO && gate.gateType_ != Gate::PPO) continue;
                bool expected = gate.gateType_ == Gate::PO ? bool(word & 8) : nextState;
                if (gate.goodSimLow_ != (expected ? PARA_L : PARA_H) ||
                    gate.goodSimHigh_ != (expected ? PARA_H : PARA_L))
                    return failure("FAN truth table disagrees with MUX/Q semantics");
            }
        }
    } else return failure("unknown test mode");
    std::cout << argv[3] << " PASS\n";
    return 0;
}
