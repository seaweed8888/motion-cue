#include "motioncue.h"
#include <cmath>
namespace motioncue {
bool Segmenter::push(const Sample& s) {
    if(!std::isfinite(s.t) || (initialized && s.t<=previous)) { *this=Segmenter{}; return false; }
    for(float x:s.axis) if(!std::isfinite(x)) { *this=Segmenter{}; return false; }
    previous=s.t;
    if(!initialized) { for(int a=0;a<3;++a)baseline[a]=s.axis[a];initialized=true; }
    float acc=0,gyro=0;
    for(int a=0;a<3;++a) {float d=s.axis[a]-baseline[a];acc+=d*d;gyro+=s.axis[a+3]*s.axis[a+3];}
    bool moving=acc>1.2f*1.2f || gyro>.7f*.7f;
    bool settled=acc<.6f*.6f && gyro<.35f*.35f;
    if(state==MotionState::IDLE) {
        for(int a=0;a<3;++a)baseline[a]+=.02f*(s.axis[a]-baseline[a]);
        pre.push_back(s);
        while(!pre.empty() && (s.t-pre.front().t>.15f || pre.size()>32))pre.erase(pre.begin());
        onset=moving ? (onset<0?s.t:onset) : -1;
        if(onset>=0 && s.t-onset>=.04f) {event=pre;started=s.t;quiet=-1;state=MotionState::CAPTURING;}
    } else if(state==MotionState::CAPTURING) {
        event.push_back(s);quiet=settled?(quiet<0?s.t:quiet):-1;
        bool overlong=s.t-started>=2.f || event.size()>=256;
        if(overlong || (quiet>=0 && s.t-quiet>=.2f)) {
            state=MotionState::CLASSIFYING;
            ended=s.t;quiet=-1;state=MotionState::WAIT_FOR_IDLE;
            return !overlong;
        }
    } else {
        for(int a=0;a<3;++a)baseline[a]+=.02f*(s.axis[a]-baseline[a]);
        quiet=settled?(quiet<0?s.t:quiet):-1;
        if(quiet>=0 && s.t-quiet>=.2f && s.t-ended>=.5f) {
            state=MotionState::IDLE;onset=quiet=-1;pre.clear();
        }
    }
    return false;
}
}
