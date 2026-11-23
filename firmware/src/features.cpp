#include "motionlink.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace motionlink {
Features features(const std::vector<Sample>& s) {
    if(s.size()<3) throw std::invalid_argument("At least 3 samples required");
    for(size_t i=0;i<s.size();++i) {
        if(!std::isfinite(s[i].t) || (i && s[i].t<=s[i-1].t)) throw std::invalid_argument("Invalid timestamp");
        for(float x:s[i].axis) if(!std::isfinite(x)) throw std::invalid_argument("Invalid channel");
    }
    Features out{}; size_t k=0;
    out[k++]=s.back().t-s.front().t;
    for(size_t a=0;a<6;++a) {
        float lo=s[0].axis[a],hi=lo,sum=0,energy=0,var=0;
        for(const auto& r:s) {float x=r.axis[a];lo=std::min(lo,x);hi=std::max(hi,x);sum+=x;energy+=x*x;}
        float mean=sum/s.size();
        for(const auto& r:s) {float d=r.axis[a]-mean;var+=d*d;}
        out[k++]=lo;out[k++]=hi;out[k++]=mean;out[k++]=std::sqrt(var/s.size());
        out[k++]=energy/s.size();out[k++]=s.back().axis[a]-s.front().axis[a];
        for(size_t part=0;part<3;++part) {
            size_t begin=part*s.size()/3,end=(part+1)*s.size()/3;float total=0;
            for(size_t i=begin;i<end;++i)total+=s[i].axis[a];
            out[k++]=total/(end-begin);
        }
    }
    return out;
}
}
