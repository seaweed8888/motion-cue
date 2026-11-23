#include "motioncue.h"
#include "gesture_model.h"
#include <algorithm>
namespace motioncue {
int classify(const Features& values) {
#if MOTIONCUE_MODEL_READY
    float probabilities[4]{};
    auto input=values;
    if(gesture_model_predict_proba(input.data(),input.size(),probabilities,4)<0)return 0;
    int label=std::max_element(probabilities,probabilities+4)-probabilities;
    return probabilities[label]>=MOTIONCUE_THRESHOLD?label:0;
#else
    (void)values;
    return 0;
#endif
}
}
