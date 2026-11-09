#!/usr/bin/env python3
"""fc4-nx: makes the installed layout Far Cry 4 expects, from an extracted disc.

On the Xbox 360 the disc's installer (default.xex) copies installation1/ to the hard drive, and the game (game.xex)
then reads those archives as if they sat in its root: game:\\common.dat, game:\\shadersobj.dat,
game:\\worlds\\fcc_main\\fcc_main.dat ... This hard-links every file of installation1/ to the same relative path under
the game folder (no extra space, same volume), merging directories with the disc's own (worlds/ holds both the
installed world archives and the disc's localized ones). Existing files are left alone.

  python fc4_install_layout.py <game folder>
"""
import os
import sys


def main():
    game = os.path.abspath(sys.argv[1])
    src_root = os.path.join(game, "installation1")
    made = kept = 0
    for d, _, files in os.walk(src_root):
        rel = os.path.relpath(d, src_root)
        out_dir = os.path.normpath(os.path.join(game, rel))
        os.makedirs(out_dir, exist_ok=True)
        for f in files:
            src, dst = os.path.join(d, f), os.path.join(out_dir, f)
            if os.path.exists(dst):
                kept += 1
                continue
            os.link(src, dst)
            made += 1
            print("linked", os.path.relpath(dst, game))
    print(f"{made} links made, {kept} already present")


if __name__ == "__main__":
    main()
