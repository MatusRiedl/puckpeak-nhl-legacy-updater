"""New centre ice (the "Bright ice" switch; since 2026-10-27 the owner's newer set of centre-ice logos, before it the
community's centre circles on white).

The centre circle of the NHL teams 0-29, with the arenas' current names, goes into the player's own disc file, which
keeps its size and layout:

    rendering/icesurface/centerlogo_<art>_cm.rpsgl    the centre circle (1024 x 1024 DXT5, 11 mipmaps)
    rendering/icesurface/icesurface_22_bm.rpsgl       Utah's rink picture, with Arizona's coyote taken out (the game shows
                                                      it under the centre circle); left to `looks` when it drew one

The pack holds each centre's encoded raster as it is (no second round of compression), laid over the raster of the
disc's file; a disc file whose raster has another size, format or mipmaps is left as it is, with a line. Nothing of the
game is shipped. The pack (`ice`): index.json {"format": 1, "built": ..., "centres": {"<art id>": {"raster":
"centerlogo_<art>_cm", "width", "height", "mips", "format", "size", "id": digest, "file": "c/<art>.bin"}}}.

Which centre a team gets: the player's own (Jerseys & ice; `keep`), else this set, else this season's (`looks`: Seattle,
Vegas and the clubs), else the game's. pipeline.install_looks leaves the art ids of this set to it. NOT played in the game
yet.
"""
from . import parts, rpsgl

CENTRE = 'rendering/icesurface/centerlogo_{a}_cm.rpsgl'
RINK = 'rendering/icesurface/icesurface_{a}_bm.rpsgl'
SEASON_ARTS = (501,)        # this season's set, not the community's: the national teams' shared IIHF ice (row pack_ice)
RINK_ARTS = (22,)           # Utah: the disc's rink picture still shows Arizona's coyote at centre ice
DRAWING = '#2'
FIELDS = ('width', 'height', 'mips', 'format', 'size')


def covered(pack):
    """The art ids (int) the pack has a centre for (a pack of the old kind, pictures by name, has none: this season's
    centre ice then stays)."""
    if pack is None:
        return set()
    return {int(a) for a, entry in (pack.index.get('centres') or {}).items() if isinstance(entry, dict)}


def centre_file(disc, art, entry, blob):
    """The disc's centre-ice file of `art` with the pack's raster in it (bytes, packed as the disc's). RpsglError when the
    disc has none or another kind of it."""
    raw = disc.render(CENTRE.format(a=art))
    if raw is None:
        raise rpsgl.RpsglError(f"the disc has no centre-ice file for {art}")
    f = rpsgl.Rpsgl(raw)
    r = f.rasters.get(entry['raster'])
    if r is None or any(r[k] != entry[k] for k in FIELDS) or len(blob) != r['size']:
        raise rpsgl.RpsglError("this copy of the game has another kind of centre-ice file")
    f.data[r['at']:r['at'] + r['size']] = blob
    return f.build()


def rink_file(disc, art):
    """The disc's rink picture of `art` with the old logo at centre ice taken out (bytes), None when the disc has none."""
    from . import looks
    raw = disc.render(RINK.format(a=art))
    return looks.ice_picture_file(raw, art, None) if raw is not None else None


def _drawn_by_looks(writer, rel):
    return any(str((writer.manifest['games'][d].get(rel) or {}).get('source', '')).startswith(parts.TAGS[parts.LOOKS])
               for d in writer.game_dirs)


def install_season(rpcs3, title_id, pack, say=print, also=(), keep=(), skipped=None):
    """The centres of `pack` that are this season's set (SEASON_ARTS), with the switch "This season's centre ice" (tag
    parts.SEASON_ICE_TAG, so that row's Restore undoes them). Returns how many files were written."""
    return install_bright(rpcs3, title_id, pack, say, also=also, keep=keep, skipped=skipped, arts=SEASON_ARTS,
                          tag=parts.SEASON_ICE_TAG, label="This season's centre ice")


def install_bright(rpcs3, title_id, pack, say=print, also=(), keep=(), skipped=None, arts=None, tag=parts.ICE_TAG,
                   label="New centre ice"):
    """Write the centres of `pack` as loose files into the game folder(s) (RPCS3 closed), with kept copies of anything
    replaced; a centre the pack no longer holds goes back as the game had it. `keep`: art ids whose centre the player
    chose in Jerseys & ice (left to `looks`). `skipped` (a list) gets (art id, why). `arts`: only these art ids (None:
    the community's, every art id but SEASON_ARTS); `tag`: the source tag the files carry. Returns how many files were
    written."""
    from . import install
    from .lab import Disc
    install.check(rpcs3, title_id)
    targets = [title_id] + [t for t in also if t != title_id]
    writer = install._Writer([rpcs3.game_folder(t) for t in targets])
    disc = Disc(rpcs3.game_disc(title_id))
    keep = {int(a) for a in keep}
    written, wanted = 0, set()
    try:
        for art, entry in sorted((pack.index.get('centres') or {}).items(), key=lambda kv: int(kv[0])):
            if int(art) in keep or (int(art) not in arts if arts is not None else int(art) in SEASON_ARTS):
                continue
            rel = CENTRE.format(a=art)
            wanted.add(rel)
            try:
                source = f"{tag}{DRAWING}:{art}:{entry['id']}"
                if writer.current(tuple(rel.split('/')), source):
                    continue
                data = centre_file(disc, art, entry, pack.read(entry['file']))
            except (rpsgl.RpsglError, KeyError, ValueError, TypeError) as err:     # TypeError: a pack of the old kind
                say(f"{label}: centre ice {art} left as it is ({err})")
                wanted.discard(rel)
                if skipped is not None:
                    skipped.append((art, str(err)))
                continue
            writer.write(tuple(rel.split('/')), data, source)
            written += 1
        for art in RINK_ARTS:
            rel = RINK.format(a=art)
            if arts is not None or CENTRE.format(a=art) not in wanted or _drawn_by_looks(writer, rel):
                continue
            wanted.add(rel)
            source = f"{parts.ICE_TAG}{DRAWING}:rink:{art}"
            if writer.current(tuple(rel.split('/')), source):
                continue
            try:
                data = rink_file(disc, art)
            except (rpsgl.RpsglError, KeyError, ValueError, OSError) as err:
                data = None
                say(f"New centre ice: rink picture {art} left as it is ({err})")
            if data is None:
                wanted.discard(rel)
                continue
            writer.write(tuple(rel.split('/')), data, source)
            written += 1
        for key in writer.stale(tag, wanted):
            writer.drop(tuple(key.split('/')))
    finally:
        writer.save()
    say(f"{label}: {written} files made" if written else f"{label}: everything is installed already")
    return written
