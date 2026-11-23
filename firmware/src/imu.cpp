#include "motioncue.h"
// Hardware deliberately unconfigured: do not invent a board, driver or pinout.
namespace motioncue {
bool imu_begin() { return false; }
bool imu_read(Sample&) { return false; }
}
