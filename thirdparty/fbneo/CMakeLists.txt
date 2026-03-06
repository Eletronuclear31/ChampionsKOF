cmake_minimum_required(VERSION 3.21)

project(fbneo_core LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ======================================
# Base burn (sem varrer drv aqui)
# ======================================
file(GLOB_RECURSE FBNEO_BURN_BASE
    src/burn/*.c
    src/burn/*.cpp
)

file(GLOB_RECURSE FBNEO_BURN_DRV_ALL
    src/burn/drv/*.cpp
)
list(REMOVE_ITEM FBNEO_BURN_BASE ${FBNEO_BURN_DRV_ALL})

# ======================================
# Drivers (inclui todos e remove pontuais)
# ======================================
file(GLOB_RECURSE FBNEO_DRIVERS
    src/burn/drv/*.cpp
)

set(FBNEO_DRIVER_EXCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/cd_interface.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/neogeo/cd_interface.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/capcom/ctv.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/pgm/pgm_draw.cpp
)
list(REMOVE_ITEM FBNEO_DRIVERS ${FBNEO_DRIVER_EXCLUDES})

# ======================================
# CPUs principais
# ======================================
file(GLOB_RECURSE FBNEO_CPU_M68K
    src/cpu/m68000/*.c
    src/cpu/m68000/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_Z80
    src/cpu/z80/*.c
    src/cpu/z80/*.cpp
)

# ======================================
# CPUs auxiliares
# ======================================
file(GLOB_RECURSE FBNEO_CPU_I8085
    src/cpu/i8085/*.c
    src/cpu/i8085/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_HMCS40
    src/cpu/hmcs40/*.c
    src/cpu/hmcs40/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_TMS32010
    src/cpu/tms32010/*.c
    src/cpu/tms32010/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_SH4
    src/cpu/sh4/*.c
    src/cpu/sh4/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_TLCS900
    src/cpu/tlcs900/*.c
    src/cpu/tlcs900/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_I8051
    src/cpu/i8051/*.c
    src/cpu/i8051/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_F8
    src/cpu/f8/*.c
    src/cpu/f8/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_I8X41
    src/cpu/i8x41/*.c
    src/cpu/i8x41/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_I8039
    src/cpu/i8039/*.c
    src/cpu/i8039/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_M6805
    src/cpu/m6805/*.c
    src/cpu/m6805/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_Z180
    src/cpu/z180/*.c
    src/cpu/z180/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_V60
    src/cpu/v60/*.c
    src/cpu/v60/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_M377
    src/cpu/m377/*.c
    src/cpu/m377/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_UPD7810
    src/cpu/upd7810/*.c
    src/cpu/upd7810/*.cpp
)
file(GLOB_RECURSE FBNEO_CPU_UPD7725
    src/cpu/upd7725/*.c
    src/cpu/upd7725/*.cpp
)

# TUs internas (não compilar isoladas)
list(REMOVE_ITEM FBNEO_CPU_HMCS40 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/hmcs40/hmcs40op.cpp)
list(REMOVE_ITEM FBNEO_CPU_TLCS900 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/tlcs900/900tbl.c)
list(REMOVE_ITEM FBNEO_CPU_I8051 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/i8051/mcs51ops.c)
list(REMOVE_ITEM FBNEO_CPU_M6805 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/m6805/6805ops.c)
list(REMOVE_ITEM FBNEO_CPU_Z180 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180/z180dd.c)
list(REMOVE_ITEM FBNEO_CPU_Z180 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180/z180fd.c)
list(REMOVE_ITEM FBNEO_CPU_Z180 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180/z180ed.c)
list(REMOVE_ITEM FBNEO_CPU_Z180 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180/z180cb.c)
list(REMOVE_ITEM FBNEO_CPU_Z180 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180/z180op.c)
list(REMOVE_ITEM FBNEO_CPU_Z180 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180/z180xy.c)
list(REMOVE_ITEM FBNEO_CPU_UPD7810 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/upd7810/7810tbl.c)
list(REMOVE_ITEM FBNEO_CPU_UPD7810 ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/upd7810/7810ops.c)

# V60: compilar somente TU principal em C++ (arquivos .c são internos)
file(GLOB FBNEO_CPU_V60_INTERNAL_C
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/v60/*.c
)
list(REMOVE_ITEM FBNEO_CPU_V60 ${FBNEO_CPU_V60_INTERNAL_C})

# ======================================
# Interface (lista explícita para evitar regressões de glob)
# ======================================
set(FBNEO_INTF_AUDIO)

# Núcleo mínimo de interface/input/replay/video que fornece símbolos usados por burn.cpp e drivers
set(FBNEO_INTF_CORE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/interface.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/input/inp_interface.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/video/vid_interface.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/video/vid_support.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/video/vid_softfx.cpp
)

# Kaillera (fornece is_netgame_or_recording)
set(FBNEO_KAILLERA_CORE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/dep/kaillera/client/net.cpp
)

# mbtwc.cpp provê _MultiByteToWideChar usado por burn.cpp
set(FBNEO_BURNER_WIN32
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burner/win32/mbtwc.cpp
)


# Stubs headless para símbolos de frontend/replay ainda exigidos por burn.cpp/drivers
set(FBNEO_HEADLESS_STUB ${CMAKE_CURRENT_BINARY_DIR}/fbneo_headless_stubs.cpp)
file(WRITE ${FBNEO_HEADLESS_STUB} [=[
#include <stddef.h>
#include <wchar.h>

// pRDI / pDataRomDesc (referenciados por muitos drivers)
void* pRDI = nullptr;
struct BurnRomInfo;
BurnRomInfo* pDataRomDesc = nullptr;

// replay/input state globals
int nReplayStatus = 0;
unsigned int nStartFrame = 0;
int nReplayUndoCount = 0;

struct MovieExtInfo { int dummy; };
MovieExtInfo MovieInfo = { 0 };

int is_netgame_or_recording(void) { return 0; }

int FreezeInputSize(void) { return 0; }
int FreezeInput(unsigned char **, int *) { return 0; }
int UnfreezeInput(const unsigned char *, int) { return 0; }

int inputbuf_freeze(unsigned char **, int *) { return 0; }
int inputbuf_unfreeze(unsigned char *, int) { return 0; }
int inputbuf_freezer_size(void) { return 0; }

int VidSNewShortMsg(const wchar_t *, int, int, int) { return 0; }
]=])


# ======================================
# Som / Memória / Dependências
# ======================================
file(GLOB_RECURSE FBNEO_SND
    src/burn/snd/*.c
    src/burn/snd/*.cpp
    src/snd/*.c
    src/snd/*.cpp
)

file(GLOB_RECURSE FBNEO_MEM
    src/mem/*.c
    src/mem/*.cpp
)

file(GLOB_RECURSE FBNEO_DEP
    src/dep/*.c
    src/dep/*.cpp
)

# Remove backends Linux/RPi no Windows
if(WIN32)
    file(GLOB_RECURSE FBNEO_DEP_PI
        src/dep/pi/*.c
        src/dep/pi/*.cpp
    )
    list(REMOVE_ITEM FBNEO_DEP ${FBNEO_DEP_PI})
endif()

# zlib explícita (libspng)
file(GLOB_RECURSE FBNEO_ZLIB
    src/dep/libs/zlib/*.c
)

# ======================================
# Biblioteca
# ======================================
add_library(fbneo_core STATIC
    ${FBNEO_BURN_BASE}
    ${FBNEO_DRIVERS}

    ${FBNEO_CPU_M68K}
    ${FBNEO_CPU_Z80}
    ${FBNEO_CPU_I8085}
    ${FBNEO_CPU_HMCS40}
    ${FBNEO_CPU_TMS32010}
    ${FBNEO_CPU_SH4}
    ${FBNEO_CPU_TLCS900}
    ${FBNEO_CPU_I8051}
    ${FBNEO_CPU_F8}
    ${FBNEO_CPU_I8X41}
    ${FBNEO_CPU_I8039}
    ${FBNEO_CPU_M6805}
    ${FBNEO_CPU_Z180}
    ${FBNEO_CPU_V60}
    ${FBNEO_CPU_M377}
    ${FBNEO_CPU_UPD7810}
    ${FBNEO_CPU_UPD7725}

    ${FBNEO_INTF_AUDIO}
    ${FBNEO_INTF_CORE}
    ${FBNEO_BURNER_WIN32}
    ${FBNEO_KAILLERA_CORE}
    ${FBNEO_HEADLESS_STUB}

    ${FBNEO_SND}
    ${FBNEO_MEM}
    ${FBNEO_DEP}
    ${FBNEO_ZLIB}
)

# ======================================
# Includes
# ======================================
target_include_directories(fbneo_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src

    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/devices
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/snd
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/neogeo
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/pce
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/pgm
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/sega
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/dataeast
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/taito
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/konami
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burn/drv/irem
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burner
    ${CMAKE_CURRENT_SOURCE_DIR}/src/burner/win32

    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/audio
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/input
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/video
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/video/scalers
    ${CMAKE_CURRENT_SOURCE_DIR}/src/intf/video/win32

    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/m68000
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z80
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/i8085
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/hmcs40
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/tms32010
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/sh4
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/tlcs900
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/i8051
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/f8
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/i8x41
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/i8039
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/m6805
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/z180
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/v60
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/m377
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/upd7810
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpu/upd7725


    ${CMAKE_CURRENT_SOURCE_DIR}/src/snd
    ${CMAKE_CURRENT_SOURCE_DIR}/src/mem
    ${CMAKE_CURRENT_SOURCE_DIR}/src/dep
    ${CMAKE_CURRENT_SOURCE_DIR}/src/dep/kaillera/client
    ${CMAKE_CURRENT_SOURCE_DIR}/src/dep/libs/dr_libs
    ${CMAKE_CURRENT_SOURCE_DIR}/src/dep/libs/zlib
)

# ======================================
# Defines / flags
# ======================================
target_compile_definitions(fbneo_core PRIVATE
    BUILD_STATIC
    FBNEO_NO_FRONTEND
    _CRT_SECURE_NO_WARNINGS
    _USE_MATH_DEFINES
)

if(WIN32)
    target_compile_definitions(fbneo_core PRIVATE WIN32 _WINDOWS BUILD_WIN32 UNICODE _UNICODE)
endif()

if(MSVC)
    target_compile_options(fbneo_core PRIVATE
        /W0
        /Zc:strictStrings-
    )
endif()
