#include "motioncue.h"
// Portable processing entry point. Board loop and MQTT transport await hardware selection.
namespace motioncue {
int process_sample(Segmenter& segmenter, Session& session, const Sample& sample) {
    if(!segmenter.push(sample))return -1;
    int label=classify(features(segmenter.event));
    if(!session.live)return -1;
    if(label==3) {session.mode.gesture(label);return label;}
    return session.mode.gesture(label)?label:0;
}
}
