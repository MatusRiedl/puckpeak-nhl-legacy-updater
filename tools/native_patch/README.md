# The game patch of NHL Legacy Native

The port has no patch loader, and a patch word cannot be written into its exe: the instruction was translated and optimised away.
A whole function can be replaced. `build.py` makes a small stand-in for `XINPUT1_4.dll`, which the exe imports. It holds our own
compiled copies of the functions the patch changes. At start it checks that the exe is the build it was made for, jumps those
functions to its copies, and writes the patch's data words once the game is in memory. Any other exe: it only passes the
controller calls on. `docs/GAME_PATCH.md` says what the patch does.

The DLL holds translated game functions, so it follows rule 9 of AGENTS.md: it goes in `private/packs/portpatch.zip` and on the
file server, never in git, never in the exe. Nothing in this folder holds game content; `build.py` makes it from the maintainer's
own copy of the game.

## Build

You need the port's source at the tag of the build, its toolchain (`BUILDING.md` there) and, in the clone, the output of its own
first steps: `bin/EBOOT_v101.elf`, `nhl/out/EBOOT_v101.*.json` and the raw lift `nhl/port/recompiled` (before the flags pass).

```
py -3.13 -B tools/native_patch/build.py <port clone> <NHLLegacy.exe> <work folder>
```

Takes a few minutes. It compares the lift with the raw lift and stops when a word of the patch lands in no replaced function. Copy
`<work>/portpatch.zip` to `private/packs/`; `tools/publish_packs.py --only portpatch` sends it (owner's go).

**When `gamepatch.TEAMS_VERSION` changes, build it again.** The pack's version is what the program compares, so with an old pack the
window shows "Patch again" for ever. Check with `python -m legacy_roster game-patch status` on the lab copy.

The entries that go in: the 32-team entry (the year is inside it) and the news entry. The port keeps its own Skip the intro, and it
has no boot login, so those two entries stay out.

## A new build of the port

`build.py` refuses an exe it does not know (`BUILDS`, keyed by the PE stamp and image size). The program refuses it too, so
a new port version means: no patch until this is done, RPCS3 players are not touched.

1. New `BUILDS` row: `table` (the `function_table` in `.rdata`: rows of guest address, host function, name), `tramp_off`, and
   the addresses of `helpers` and `data`. None are exported. Find a helper by small functions in the raw lift that call one helper
   only: the call all of those have in common in the exe is that helper (`llvm-objdump -d`). Read `data` and `tramp_off` from those
   helpers' code.
2. `NATIVE_PATCHED` in `savedata.py`: the new stamp and image.
3. Build, then play it on the lab copy. The log needs `NHL_PUCKPEAK_LOG=1`: `puckpeak_patch.log` next to the DLL says what was
   swapped, or which function did not match. `NHL_PUCKPEAK_NOSWAP=1` turns the swap off without removing the file.

`NHLLauncher.exe` imports the same DLL, so it loads our file too. The first line of the log is that: "not the exe this was made
for", which is harmless. The launcher stays open behind the game and holds the file, so the program refuses Patch and Unpatch
while it runs (`savedata.launcher_running`).
