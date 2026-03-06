cmake_minimum_required(VERSION 3.21)

project(ChampionsKOF LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS
    Core
    Gui
    Widgets
    OpenGL
)

qt_standard_project_setup()

add_subdirectory(thirdparty/fbneo)

set(SOURCES
    main.cpp
    src/App/AppController.cpp
    src/Video/GameWindow.cpp
    src/Platform/HighPrecisionTimer.cpp
    src/Core/CoreThread.cpp
    src/Core/DummyCore.cpp
    src/Core/FrameRingBuffer.cpp
    src/Utils/FrameHash.cpp
)

set(HEADERS
    src/App/AppController.h
    src/Video/GameWindow.h
    src/Platform/HighPrecisionTimer.h
    src/Core/CoreThread.h
    src/Core/ICore.h
    src/Core/DummyCore.h
    src/Core/FrameData.h
    src/Core/FrameRingBuffer.h
    src/Utils/FrameHash.h
)

qt_add_executable(ChampionsKOF
    ${SOURCES}
    ${HEADERS}
)

target_include_directories(ChampionsKOF PRIVATE
    src
)

target_link_libraries(ChampionsKOF PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::OpenGL
    fbneo_core
)
