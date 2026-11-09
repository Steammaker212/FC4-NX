/* fc4-nx: platform dispatcher for the committed per-platform FFmpeg configure outputs. The base repository's FFmpeg
 * tree ignores /config.h (FFmpeg's .gitignore), so it was missing from the published copy. */
#ifndef FFMPEG_CONFIG_DISPATCH_H
#define FFMPEG_CONFIG_DISPATCH_H
#if defined(__SWITCH__)
#include "config_switch_aarch64.h"
#elif defined(_WIN32) && (defined(_M_ARM64) || defined(__aarch64__))
#include "config_windows_aarch64.h"
#elif defined(_WIN32)
#include "config_windows_x86_64.h"
#elif defined(__APPLE__) && defined(__aarch64__)
#include "config_macos_aarch64.h"
#elif defined(__APPLE__)
#include "config_macos_x86_64.h"
#elif defined(__ANDROID__) && defined(__aarch64__)
#include "config_android_aarch64.h"
#elif defined(__ANDROID__)
#include "config_android_x86_64.h"
#elif defined(__aarch64__)
#include "config_linux_aarch64.h"
#else
#include "config_linux_x86_64.h"
#endif
#endif
