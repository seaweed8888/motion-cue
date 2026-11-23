#include "motionlink.h"
#include "esp_log.h"

extern "C" void app_main() {
    constexpr const char* tag = "motionlink";
    motionlink::Session session;
    session.disconnect();
    ESP_LOGI(tag, "MotionLink ESP32-S3: disarmed");
    if (!motionlink::imu_begin()) {
        ESP_LOGW(tag, "IMU driver is not configured; gesture control is disabled");
        return;
    }
    ESP_LOGW(tag, "Acquisition and MQTT transport are not integrated; staying disarmed");
}
