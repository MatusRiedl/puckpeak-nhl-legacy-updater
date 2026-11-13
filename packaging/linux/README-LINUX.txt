Blueline (NHL Legacy) for Linux
==================================

1. Unpack this folder anywhere, for example in your home folder.
2. Start BluelineLegacy in it (double-click it, or in a terminal: ./BluelineLegacy).
   On a Steam Deck, use Desktop Mode.
3. On the Setup tab, press "Find RPCS3" and pick one of these:
   - your RPCS3 AppImage (for example ~/Downloads/rpcs3-...AppImage, or ~/Applications/rpcs3.AppImage with EmuDeck),
   - the rpcs3 program, if RPCS3 came from your system's software store or package manager,
   - RPCS3's folder: ~/.config/rpcs3 (the Flatpak keeps it in ~/.var/app/net.rpcs3.RPCS3/config/rpcs3).
   The program finds your saves and your game from there, also when RPCS3 keeps them in another folder.
4. Close RPCS3 before you patch the game or update a roster.

Nothing to install: the window brings everything it needs. It runs on 64-bit Linux from 2022 or newer
(Ubuntu 22.04, Debian 12, Fedora 36, SteamOS 3, Arch and others like them).

The command line does the same without the window:  ./BluelineLegacy --help

If the window does not open, start ./BluelineLegacy in a terminal and send us what it prints and the file
~/.local/share/NHLLegacyRosterUpdater/logs/error.log
