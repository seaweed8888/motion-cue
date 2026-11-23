#include "motioncue.h"
namespace motioncue {
bool ControlMode::gesture(int label) {
    if(label==3) { armed=twist_toggle?!armed:true;return false; }
    return armed && (label==1 || label==2);
}
}
