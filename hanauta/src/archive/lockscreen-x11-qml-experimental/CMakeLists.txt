cmake_minimum_required(VERSION 3.21)
project(hanauta_lockscreen_x11 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Qml Quick Widgets)
find_package(X11 REQUIRED)

qt_standard_project_setup()

set(HANAUTA_LOCK_SOURCES
    src/AuthBridge.cpp
    src/AuthWindow.cpp
    src/PamClient.cpp
    src/XSecurelockWindow.cpp
)

qt_add_executable(auth_hanauta
    src/auth_main.cpp
    ${HANAUTA_LOCK_SOURCES}
)

qt_add_executable(saver_hanauta
    src/saver_main.cpp
    ${HANAUTA_LOCK_SOURCES}
)

set_target_properties(auth_hanauta PROPERTIES QT_QML_MODULE_NO_IMPORT_SCAN TRUE)
set_target_properties(saver_hanauta PROPERTIES QT_QML_MODULE_NO_IMPORT_SCAN TRUE)

target_include_directories(auth_hanauta PRIVATE src)
target_include_directories(saver_hanauta PRIVATE src)

target_link_libraries(auth_hanauta PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::Widgets
    X11::X11
)

target_link_libraries(saver_hanauta PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::Widgets
    X11::X11
)

qt_add_resources(auth_hanauta "hanauta_lock_qml"
    PREFIX "/"
    FILES
        qml/MainAuth.qml
        qml/MainSaver.qml
        qml/Center.qml
        qml/InputField.qml
        qml/theme.js
)

qt_add_resources(saver_hanauta "hanauta_lock_qml"
    PREFIX "/"
    FILES
        qml/MainAuth.qml
        qml/MainSaver.qml
        qml/Center.qml
        qml/InputField.qml
        qml/theme.js
)
