#include "motionlink.h"
namespace motionlink {
void Session::pulse(const std::string& session,const std::string& token,uint32_t now,
                    const std::string& command,bool armed) {
    if(session.empty() || token.empty() || session.size()>128 || token.size()>128)return;
    bool fresh=!live || session!=id;
    if(fresh) {disconnect();id=session;}
    live=true;lease=token;last=now;
    if(!fresh && !command.empty() && command!=command_id) {mode.armed=armed;command_id=command;}
}
void Session::tick(uint32_t now) { if(live && uint32_t(now-last)>1200)disconnect(); }
void Session::disconnect() {live=false;mode.disconnect();id.clear();lease.clear();command_id.clear();}
}
