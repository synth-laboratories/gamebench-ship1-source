// Reference-only mGBA frame extractor. This is not part of the Rust runtime.
#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/serialize.h>
#include <mgba/internal/gba/input.h>
#include <mgba-util/vfs.h>

#include <stdint.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>

enum { WIDTH = 240, HEIGHT = 160 };

static int dump_memory(struct mCore* core, const char* prefix, const char* name, uint32_t address, size_t length) {
  char path[1024];
  if (snprintf(path, sizeof(path), "%s.%s.bin", prefix, name) >= (int)sizeof(path)) return 0;
  FILE* output = fopen(path, "wb");
  if (!output) return 0;
  for (size_t i = 0; i < length; ++i) {
    unsigned char value = (unsigned char)core->busRead8(core, address + (uint32_t)i);
    if (fwrite(&value, 1, 1, output) != 1) {
      fclose(output);
      return 0;
    }
  }
  fclose(output);
  return 1;
}

int main(int argc, char** argv) {
  int dump_objects = argc >= 7 && argc % 2 == 1;
  if (argc != 4 && (argc < 6 || (argc % 2 != 0 && !dump_objects))) {
    fprintf(stderr, "usage: %s ROM STATE OUTPUT.rgb [KEY_MASK HELD_FRAMES [KEY2 FRAMES2 ...]] [OBJ_DUMP_PREFIX]\n", argv[0]);
    return 2;
  }
  struct mCore* core = mCoreFind(argv[1]);
  if (!core) {
    fprintf(stderr, "could not identify Emerald reference\\n");
    return 1;
  }
  core->init(core);
  mCoreInitConfig(core, "gamebench-capture");
  mCoreLoadConfig(core);
  if (!mCoreLoadFile(core, argv[1])) {
    fprintf(stderr, "could not initialize Emerald reference\\n");
    return 1;
  }
  color_t* pixels = calloc(WIDTH * HEIGHT, sizeof(*pixels));
  if (!pixels) return 1;
  core->setVideoBuffer(core, pixels, WIDTH);
  core->reset(core);
  struct VFile* state = VFileOpen(argv[2], O_RDONLY);
  if (!state || !mCoreLoadStateNamed(core, state, SAVESTATE_ALL)) {
    fprintf(stderr, "could not load state\\n");
    return 1;
  }
  state->close(state);
  if (argc >= 6) {
    int segment_end = dump_objects ? argc - 1 : argc;
    for (int arg = 4; arg < segment_end; arg += 2) {
      uint32_t keys = (uint32_t) strtoul(argv[arg], NULL, 0);
      unsigned frames = (unsigned) strtoul(argv[arg + 1], NULL, 0);
      core->setKeys(core, keys);
      for (unsigned i = 0; i < frames; ++i) core->runFrame(core);
      core->clearKeys(core, keys);
    }
  } else {
    core->runFrame(core);
  }
  FILE* output = fopen(argv[3], "wb");
  if (!output) return 1;
  for (size_t i = 0; i < WIDTH * HEIGHT; ++i) {
    uint32_t pixel = pixels[i];
    unsigned char rgb[3] = {
      (unsigned char)(pixel & 0xff),
      (unsigned char)((pixel >> 8) & 0xff),
      (unsigned char)((pixel >> 16) & 0xff),
    };
    fwrite(rgb, 1, sizeof(rgb), output);
  }
  fclose(output);
  if (dump_objects) {
    const char* prefix = argv[argc - 1];
    if (!dump_memory(core, prefix, "bg_vram", 0x06000000, 0x10000)
        || !dump_memory(core, prefix, "bg_palette", 0x05000000, 0x200)
        || !dump_memory(core, prefix, "io", 0x04000000, 0x100)
        || !dump_memory(core, prefix, "ewram", 0x02000000, 0x40000)
        || !dump_memory(core, prefix, "iwram", 0x03000000, 0x8000)
        || !dump_memory(core, prefix, "obj_vram", 0x06010000, 0x8000)
        || !dump_memory(core, prefix, "obj_palette", 0x05000200, 0x200)
        || !dump_memory(core, prefix, "oam", 0x07000000, 0x400)) {
      fprintf(stderr, "could not dump object memory\\n");
      free(pixels);
      core->deinit(core);
      return 1;
    }
  }
  free(pixels);
  core->deinit(core);
  return 0;
}
