// Exact Icarus settled-timestamp transition collection, matching its VCD dump.
// Only emission/storage changes. Stimulus, circuit and simulator are unchanged.
#include <vpi_user.h>
#include <zlib.h>
#include <cstdint>
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

namespace {
struct Net { vpiHandle handle; int previous; bool dirty; size_t index; };
std::vector<Net> nets;
std::vector<size_t> dirty;
std::vector<uint8_t> counts;
vpiHandle marker;
gzFile output = nullptr;
uint32_t expected_cycles = 0, written = 0;
size_t unknown = 0;
int32_t active = -1;
bool scheduled = false, failed = false;

int scalar(vpiHandle handle) {
    s_vpi_value value{};
    value.format = vpiScalarVal;
    vpi_get_value(handle, &value);
    return value.value.scalar;
}

void fail(const char* message) {
    if (!failed) vpi_printf("PACT_COUNTS_ERROR: %s\n", message);
    failed = true;
    vpi_control(vpiFinish, 1);
}

void bytes(const void* data, unsigned size) {
    if (!output || gzwrite(output, data, size) != static_cast<int>(size))
        fail("compressed output write failed");
}

void integer(uint32_t value) {
    uint8_t data[4];
    for (unsigned i=0; i<4; ++i) data[i] = (value >> (i*8)) & 255;
    bytes(data, 4);
}

void finish_cycle() {
    if (active < 0 || failed) return;
    if (static_cast<uint32_t>(active) != written) {
        fail("noncontiguous or repeated cycle marker"); return;
    }
    bytes(counts.data(), counts.size());
    ++written;
    std::fill(counts.begin(), counts.end(), 0);
}

PLI_INT32 flush(p_cb_data) {
    scheduled = false;
    if (failed) return 0;
    s_vpi_value value{};
    value.format = vpiVectorVal;
    vpi_get_value(marker, &value);
    if (value.value.vector[0].bval) { fail("unknown cycle marker"); return 0; }
    int32_t cycle = static_cast<int32_t>(value.value.vector[0].aval);
    if (cycle < -1 || (cycle >= 0 && static_cast<uint32_t>(cycle) >= expected_cycles)) {
        fail("cycle outside workload"); return 0;
    }
    // Use the final cycle marker at this timestamp, irrespective of callback
    // order. Icarus VCD emits each dirty scalar's final settled value once.
    if (cycle != active) {
        finish_cycle();
        active = cycle;
        if (cycle >= 0 && static_cast<uint32_t>(cycle) != written) {
            fail("missing or repeated measured cycle"); return 0;
        }
    }
    for (size_t i: dirty) {
        Net& net = nets[i];
        int now = scalar(net.handle);
        bool old_unknown = net.previous != vpi0 && net.previous != vpi1;
        bool new_unknown = now != vpi0 && now != vpi1;
        if (old_unknown && !new_unknown) --unknown;
        if (!old_unknown && new_unknown) ++unknown;
        if (cycle >= 0) {
            if (new_unknown) { fail("unknown active measured net"); return 0; }
            if (now != net.previous) {
                if (old_unknown) {
                    fail("unknown active net transition"); return 0;
                }
                if (counts[i] == 255) { fail("per-cycle transition overflow"); return 0; }
                ++counts[i];
            }
        }
        net.previous = now;
        net.dirty = false;
    }
    dirty.clear();
    if (cycle >= 0 && unknown) { fail("unknown active measured nets"); return 0; }
    return 0;
}

void queue_flush() {
    if (scheduled || failed) return;
    scheduled = true;
    s_vpi_time when{};
    when.type = vpiSimTime;
    s_cb_data callback{};
    callback.reason = cbReadOnlySynch;
    callback.cb_rtn = flush;
    callback.time = &when;
    vpi_register_cb(&callback);
}

PLI_INT32 changed(p_cb_data cb) {
    if (cb->user_data) {
        Net* net = reinterpret_cast<Net*>(cb->user_data);
        if (!net->dirty) { net->dirty = true; dirty.push_back(net->index); }
    }
    queue_flush();
    return 0;
}

PLI_INT32 end(p_cb_data) {
    if (scheduled && !failed) flush(nullptr);
    finish_cycle();
    if (!failed && written == expected_cycles) {
        bytes("PACTDONE", 8);
        vpi_printf("PACT_COUNTS_COMPLETE cycles=%u nets=%zu\n", written, nets.size());
    } else {
        vpi_printf("PACT_COUNTS_INCOMPLETE cycles=%u expected=%u\n", written, expected_cycles);
    }
    if (output) gzclose(output);
    output = nullptr;
    return 0;
}

PLI_INT32 start(p_cb_data) {
    const char* config = std::getenv("PACT_ACTIVITY_CONFIG");
    const char* destination = std::getenv("PACT_ACTIVITY_OUTPUT");
    if (!config || !destination) { fail("missing activity configuration"); return 0; }
    std::ifstream input(config);
    std::string line;
    if (!std::getline(input, line)) { fail("missing cycle count"); return 0; }
    try { expected_cycles = std::stoul(line); }
    catch (...) { fail("invalid cycle count"); return 0; }
    if (!expected_cycles) { fail("empty workload"); return 0; }
    std::vector<std::string> names;
    while (std::getline(input, line)) {
        if (line.empty() || (!names.empty() && line <= names.back())) {
            fail("net names must be nonempty, sorted and unique"); return 0;
        }
        names.push_back(line);
    }
    marker = vpi_handle_by_name(const_cast<char*>("tb.cycle_id"), nullptr);
    if (!marker || vpi_get(vpiSize, marker) != 32 || names.empty()) {
        fail("missing cycle marker or nets"); return 0;
    }
    nets.reserve(names.size());
    for (const auto& name: names) {
        std::string path = "tb.dut." + name;
        vpiHandle handle = vpi_handle_by_name(const_cast<char*>(path.c_str()), nullptr);
        if (!handle || vpi_get(vpiSize, handle) != 1) {
            vpi_printf("PACT_COUNTS_MISSING %s\n", path.c_str());
            fail("missing or nonscalar measured net"); return 0;
        }
        int initial = scalar(handle);
        if (initial != vpi0 && initial != vpi1) ++unknown;
        dirty.push_back(nets.size());
        nets.push_back({handle, initial, true, nets.size()});
    }
    counts.resize(nets.size());
    output = gzopen(destination, "wb1");
    if (!output) { fail("cannot create activity output"); return 0; }
    bytes("PACTCN01", 8);
    integer(nets.size()); integer(expected_cycles);
    for (const auto& name: names) { integer(name.size()); bytes(name.data(), name.size()); }
    for (auto& net: nets) {
        s_cb_data callback{};
        callback.reason = cbValueChange; callback.cb_rtn = changed;
        callback.obj = net.handle;
        callback.user_data = reinterpret_cast<PLI_BYTE8*>(&net);
        vpi_register_cb(&callback);
    }
    s_cb_data callback{};
    callback.reason = cbValueChange; callback.cb_rtn = changed; callback.obj = marker;
    vpi_register_cb(&callback);
    callback = {}; callback.reason = cbEndOfSimulation; callback.cb_rtn = end;
    vpi_register_cb(&callback);
    queue_flush();
    return 0;
}

void register_counts() {
    s_cb_data callback{};
    callback.reason = cbStartOfSimulation; callback.cb_rtn = start;
    vpi_register_cb(&callback);
}
}

extern "C" {
void (*vlog_startup_routines[])() = {register_counts, nullptr};
}
