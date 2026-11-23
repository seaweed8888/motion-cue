#include "motionlink.h"
// Hardware deliberately unconfigured: do not invent a board, driver or pinout.
namespace motionlink {
bool imu_begin() { return false; }
bool imu_read(Sample&) { return false; }
}
