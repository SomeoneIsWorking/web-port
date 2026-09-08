# Each dependency installs into one prefix before its dependants configure.
# Separate CMake scopes preserve upstream export/installation contracts.
include(ExternalProject)
set(_common
    -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE}
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX}
    -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_PREFIX_PATH=${CMAKE_INSTALL_PREFIX}
    -DCMAKE_FIND_ROOT_PATH=${CMAKE_INSTALL_PREFIX}
    -DCMAKE_C_FLAGS=-pthread -DCMAKE_CXX_FLAGS=-pthread
    -DBUILD_SHARED_LIBS=OFF)

function(web_library name repository revision)
    ExternalProject_Add(${name}
        PREFIX "${CMAKE_BINARY_DIR}/${name}"
        SOURCE_DIR "${CMAKE_BINARY_DIR}/sources/${name}"
        GIT_REPOSITORY "${repository}" GIT_TAG "${revision}"
        GIT_SUBMODULES ""
        CMAKE_ARGS ${_common} ${ARGN})
endfunction()

web_library(zlib https://github.com/libsdl-org/zlib.git
    0e68590d11e618d60866aa86629fbda128bc068a
    -DZLIB_BUILD_EXAMPLES=OFF)
web_library(png https://github.com/libsdl-org/libpng.git
    4b9e071b2fc4216369372a3ed260d335dd036f15
    -DPNG_SHARED=OFF -DPNG_TESTS=OFF -DPNG_EXECUTABLES=OFF
    -DZLIB_INCLUDE_DIR=${CMAKE_INSTALL_PREFIX}/include
    -DZLIB_LIBRARY=${CMAKE_INSTALL_PREFIX}/lib/libzlibstatic.a)
ExternalProject_Add_StepDependencies(png configure zlib)
web_library(freetype https://github.com/freetype/freetype.git
    42608f77f20749dd6ddc9e0536788eaad70ea4b5
    -DFT_DISABLE_BZIP2=ON -DFT_DISABLE_BROTLI=ON -DFT_DISABLE_HARFBUZZ=ON
    -DFT_DISABLE_PNG=ON -DFT_DISABLE_ZLIB=ON)

if(WEB_PORT_SDL_SOURCE)
    set(_sdl_source SOURCE_DIR "${WEB_PORT_SDL_SOURCE}" DOWNLOAD_COMMAND "" UPDATE_COMMAND "")
else()
    set(_sdl_source SOURCE_DIR "${CMAKE_BINARY_DIR}/sources/sdl"
        GIT_REPOSITORY https://github.com/SomeoneIsWorking/SDL.git
        GIT_TAG 852bb85bf256ec9dc169dbc376eafb0f467cdc83 GIT_SUBMODULES "")
endif()
ExternalProject_Add(sdl
    PREFIX "${CMAKE_BINARY_DIR}/sdl" ${_sdl_source}
    BUILD_ALWAYS ON
    CMAKE_ARGS ${_common}
        -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_WEBGPU=ON -DSDL_PTHREADS=ON
        -DSDL_TESTS=OFF -DSDL_TEST_LIBRARY=OFF -DSDL_INSTALL=ON -DSDL_INSTALL_TESTS=OFF)
web_library(sdl_image https://github.com/libsdl-org/SDL_image.git
    bec9134a26c7d0f31b36d6083c25296e04cabff5
    -DSDLIMAGE_VENDORED=OFF -DSDLIMAGE_INSTALL=ON -DSDLIMAGE_AVIF=OFF
    -DSDLIMAGE_JXL=OFF -DSDLIMAGE_TIF=OFF -DSDLIMAGE_WEBP=OFF
    -DSDLIMAGE_PNG=ON -DSDLIMAGE_PNG_LIBPNG=ON -DSDLIMAGE_PNG_SHARED=OFF
    -DSDLIMAGE_SAMPLES=OFF -DSDLIMAGE_TESTS=OFF
    -DSDL3_DIR=${CMAKE_INSTALL_PREFIX}/lib/cmake/SDL3
    -DZLIB_INCLUDE_DIR=${CMAKE_INSTALL_PREFIX}/include
    -DZLIB_LIBRARY=${CMAKE_INSTALL_PREFIX}/lib/libzlibstatic.a
    -DPNG_PNG_INCLUDE_DIR=${CMAKE_INSTALL_PREFIX}/include
    -DPNG_LIBRARY_RELEASE=${CMAKE_INSTALL_PREFIX}/lib/libpng16.a)
ExternalProject_Add_StepDependencies(sdl_image configure sdl png)
web_library(sdl_ttf https://github.com/libsdl-org/SDL_ttf.git
    a1ce3670aec736ecbf0936c43f2f0cc53aa61e5b
    -DSDLTTF_VENDORED=OFF -DSDLTTF_HARFBUZZ=OFF -DSDLTTF_PLUTOSVG=OFF
    -DSDLTTF_SAMPLES=OFF -DSDLTTF_INSTALL=ON
    -DSDL3_DIR=${CMAKE_INSTALL_PREFIX}/lib/cmake/SDL3
    -DFreetype_DIR=${CMAKE_INSTALL_PREFIX}/lib/cmake/freetype
    -DCMAKE_FIND_PACKAGE_PREFER_CONFIG=ON)
ExternalProject_Add_StepDependencies(sdl_ttf configure sdl freetype)

ExternalProject_Add(bzip2
    PREFIX "${CMAKE_BINARY_DIR}/bzip2"
    GIT_REPOSITORY https://github.com/libarchive/bzip2.git
    GIT_TAG 6a8690fc8d26c815e798c588f796eabe9d684cf0 GIT_SUBMODULES ""
    CONFIGURE_COMMAND ${CMAKE_COMMAND} -S "${CMAKE_SOURCE_DIR}/cmake/bzip2"
        -B <BINARY_DIR> -G Ninja ${_common} -DBZIP2_SOURCE=<SOURCE_DIR>)

find_program(WEB_PORT_MAKE NAMES gmake make REQUIRED)
get_filename_component(_emscripten "${CMAKE_TOOLCHAIN_FILE}/../../../.." ABSOLUTE)
ExternalProject_Add(ffmpeg
    URL https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n7.1.1.tar.gz
    URL_HASH SHA256=f117507dc501f2a6c11f9241d8d0c3213846cfad91764361af37befd6b6c523d
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    PREFIX "${CMAKE_BINARY_DIR}/ffmpeg"
    CONFIGURE_COMMAND <SOURCE_DIR>/configure
        --prefix=${CMAKE_INSTALL_PREFIX} --cc=${_emscripten}/emcc
        --cxx=${_emscripten}/em++ --ar=${_emscripten}/emar
        --ranlib=${_emscripten}/emranlib --nm=${_emscripten}/emnm
        --enable-cross-compile --target-os=none --arch=wasm32
        --disable-asm --disable-inline-asm --disable-programs --disable-doc
        --disable-debug --disable-network --disable-autodetect --disable-everything
        --enable-static --disable-shared --enable-demuxer=mpegps,asf
        --enable-decoder=mpeg1video,adpcm_adx,wmav1,wmav2,wmapro,wmavoice
        --enable-parser=mpegvideo
        --enable-protocol=file --enable-swscale --enable-swresample
        --enable-avformat --enable-avcodec --enable-avutil
        --disable-avdevice --disable-avfilter --disable-postproc
        --extra-cflags=-pthread --extra-ldflags=-pthread
    BUILD_COMMAND ${WEB_PORT_MAKE} -j2
    INSTALL_COMMAND ${WEB_PORT_MAKE} install)
add_custom_target(web_port_dependencies ALL
    DEPENDS sdl sdl_image sdl_ttf freetype zlib png bzip2 ffmpeg)
