#include "web_port/storage.h"

#include <cerrno>
#include <cstring>

#include <emscripten/threading.h>
#include <emscripten/wasmfs.h>

namespace {

bool valid_mountpoint(const char *mountpoint) {
  if (!mountpoint || mountpoint[0] != '/' || !mountpoint[1] || std::strchr(mountpoint + 1, '/') ||
      emscripten_is_main_browser_thread()) {
    errno = EINVAL;
    return false;
  }
  return true;
}

int mount_result(int result) {
  if (result < 0) {
    errno = -result;
  }
  return result == 0;
}

} // namespace

extern "C" int web_port_mount_storage(const char *mountpoint) {
  if (!valid_mountpoint(mountpoint)) {
    return 0;
  }
  backend_t storage = wasmfs_create_opfs_backend();
  return mount_result(wasmfs_create_directory(mountpoint, 0700, storage));
}

extern "C" int web_port_unmount_storage(const char *mountpoint) {
  if (!valid_mountpoint(mountpoint)) {
    return 0;
  }
  return mount_result(wasmfs_unmount(mountpoint));
}
