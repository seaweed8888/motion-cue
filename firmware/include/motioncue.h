#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace motioncue {
struct Sample { float t; std::array<float,6> axis; };
using Features = std::array<float,55>;
Features features(const std::vector<Sample>& samples);
enum class MotionState { IDLE, CAPTURING, CLASSIFYING, WAIT_FOR_IDLE };
class Segmenter {
public:
    MotionState state = MotionState::IDLE;
    bool push(const Sample& sample);
    std::vector<Sample> event;
private:
    bool initialized = false;
    std::array<float,3> baseline{};
    std::vector<Sample> pre;
    float onset=-1, quiet=-1, started=0, ended=0, previous=-1;
};
class ControlMode {
public:
    bool armed=false;
    bool twist_toggle=true;
    bool gesture(int label);
    void disconnect() { armed=false; }
};
class Session {
public:
    ControlMode mode;
    std::string id, lease, command_id;
    bool live=false;
    void pulse(const std::string& session, const std::string& token, uint32_t now,
               const std::string& command="", bool armed=false);
    void tick(uint32_t now);
    void disconnect();
private:
    uint32_t last=0;
};
int classify(const Features& values);
int process_sample(Segmenter& segmenter, Session& session, const Sample& sample);
// Driver must supply calibrated SI units and acquisition timestamps.
bool imu_begin();
bool imu_read(Sample& sample);
}
