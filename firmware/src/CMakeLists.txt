idf_component_register(
    SRCS "app_main.cpp" "main.cpp" "imu.cpp" "segmenter.cpp"
         "features.cpp" "classifier.cpp" "control_mode.cpp" "mqtt_client.cpp"
    INCLUDE_DIRS "../include"
    REQUIRES freertos log
)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
