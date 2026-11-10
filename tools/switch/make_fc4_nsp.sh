#!/bin/sh
# fc4-nx (2026-11-10): the NSP forwarder (a HOME menu icon that starts sdmc:/switch/fc4-nx/fc4-nx.nro, back to HOME
# when the game exits). Run from Git Bash in fc4-nx/. Needs:
#   - tools/switch/icon/fc4_icon.jpg (tools/switch/make_fc4_icon.py, from the disc's logo; not in git)
#   - hacbrewpack built from source (../nsp_tools/hacBrewPack, the mirror of The-4n's) and your console's prod.keys
#   - devkitPro (the forwarder is nx-hbloader with its default NRO changed: tools/switch/forwarder)
# Output: out/nsp/<title id>.nsp (install with DBI/Tinfoil/Goldleaf; signature patches needed, like any homebrew NSP).
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TITLE_ID=${TITLE_ID:-01FC4F00C4000000}
KEYS=${KEYS:-$ROOT/out/nsp/keys_filtered.dat}   # prod.keys with only 32/64-digit keys (hacbrewpack 3.05 stops on others)
HBP=${HBP:-$ROOT/../nsp_tools/hacBrewPack/hacbrewpack.exe}
WORK=/c/Users/Public/fc4fwd   # devkitPro's make cannot build in a path with spaces
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$ROOT/tools/switch/forwarder/Makefile" "$ROOT/tools/switch/forwarder/hbl.json" "$ROOT/tools/switch/forwarder/source" "$WORK/"
powershell.exe -NoProfile -Command "& 'C:\devkitPro\msys2\usr\bin\bash.exe' -c 'export HOME=/tmp DEVKITPRO=/opt/devkitpro PATH=/usr/bin:/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin; cd /c/Users/Public/fc4fwd; make -j8 2>&1 | tail -3'"
OUT="$ROOT/out/nsp"; STAGE="$OUT/stage"
rm -rf "$STAGE"; mkdir -p "$STAGE/exefs" "$STAGE/control"
cp "$WORK/hbl.nso" "$STAGE/exefs/main"
cp "$WORK/hbl.npdm" "$STAGE/exefs/main.npdm"
/c/devkitPro/tools/bin/nacptool.exe --create "Far Cry 4" "ChanseyIsTheBest" "0.1.0" "$STAGE/control/control.nacp" --titleid=$TITLE_ID
cp "$ROOT/tools/switch/icon/fc4_icon.jpg" "$STAGE/control/icon_AmericanEnglish.dat"
cd "$STAGE"
"$HBP" -k "$KEYS" --titleid $TITLE_ID --titlename "Far Cry 4" --titlepublisher "ChanseyIsTheBest" --noromfs --nologo \
  --exefsdir exefs --controldir control --nspdir "$OUT" --backupdir "$STAGE/backup"
ls -la "$OUT"/*.nsp
