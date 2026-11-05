"""The look of a team in the game's 3D world: jerseys, pants, socks, number sheets, the menu pictures of the jerseys
and the centre-ice logo (needs Pillow, imported when a picture is made; the engine's other modules never need it).

Why this exists (owner, 2026-10-06): Arizona is Utah now and slots 30 and 31 are still the All-Star teams, so their
jerseys and ice show the wrong team. The game takes every 3D texture from a loose file under
`<game folder>/rendering/...` before its disc (proven by `cli rendering-test`; RPCS3's log names the files Play Now
opens: style 1, variants 3 and 4 for Utah, and `centerlogo_22_cm`).

How a jersey is made. Every standard jersey of style 1 is painted on one shared shirt layout (the normal maps of Utah's,
Seattle's, Vegas's, Edmonton's and Vancouver's jerseys agree to 96-100 %). Utah's own style-1 jersey (variant 3 dark,
variant 4 light) is a flat three-colour design: a body colour, a yoke colour and a trim colour, with the crest and two
shoulder marks on top. `recolour()` swaps those three colours for the team's (keeping the cloth's shading), the crest and
shoulder marks are painted over with the team's own logo, and the result goes into the team's own file: every raster
keeps the size the disc's file has, so the file keeps its layout. Pants, socks and the number sheet go the same way.
Nothing of the game's is shipped: the chassis is read from the player's own disc each time (AGENTS rule 10).

Not every version of a team uses that layout: the old All-Star versions (Seattle and Vegas 0 and 1) and style 0 are
painted on other shirts. Those are left as they are (`STANDARD_LAYOUT`).

This season's jerseys (owner, 2026-10-16): the program carries the pack's kits and centre-ice logos of every team both games
have, already moved into the PS3's two cuts (`art/lookpack.py`). `pack_team` and `looks_from` put them onto the
player's own disc files: the dark default version gets the pack's dark kit, the light default its light one, and (0.92.0)
the lowest Alternate version the roster lists its third kit (`pack_versions`). Every other version stays the game's own, and
so does the Alternate of a team the pack has no third for. A team whose roster lists no Alternate version has nowhere to put the pack's third.
Style 1 (the NHL, AHL, CHL, some European clubs) goes the way of the player's own colour map, on the chassis' relief
and number sheet; style 0 (the classic cut of most European clubs and the national teams) keeps the version's own file
with a clean relief (`style0_relief`: the median of 11 clubs' reliefs, which drops their embossed crests) and its own
number sheet in the pack's number colours. Pants and socks share one layout in both cuts: both get the chassis' in the
kit's colours (`kit_palette`). The Select Jerseys picture is the pack's own menu picture of the kit on the game's black
figure (`menu_picture`; the chassis' preview in the kit's colours only for a kit the pack has no menu picture for).
Proven in the lab: gate G2b (Utah,
Toronto), G3 (Davos, Sparta, Berlin, Canada) and round 31, private/notes/study.md. A club's pack centre ice goes
in only where the game shows it at that club's home games and nowhere else (`shown_centre`, `own_ice`): not the DEL's
(one shared ice) and not the national teams' (the game's international ice).

Every team of every league (owner, 2026-10-18) can have its jerseys chosen in the Roster editor's "Jerseys and ice" window
(app/uniforms.py; `editable`, `team_versions`): an NHL team every version, any other team its home, away and Alternate versions,
each the pack's, the game's own, made from the colours (style 1 on the shared layout only) or the player's own picture.
Jerseys belong to an art id, not a slot: a team sharing its art id with a lower slot (the Winter Classic, EASHL and Top
Prospects teams) is changed at that slot (`jersey_owner`).
"""
import functools
import hashlib
import json
import math
import os
import re
from collections import namedtuple

from .. import layout as L
from . import clubart, parts, rpsgl

STYLE = 1
CHASSIS_ART = 22                   # Utah's (Arizona's) own files are the chassis
CHASSIS = {False: 3, True: 4}      # dark and light variant of the chassis
JERSEY = "rendering/jersey/texlib_{s}_{a}_{v}.rpsgl"
PANT = "rendering/pant/texlib_{s}_{a}_{v}.rpsgl"
SOCK = "rendering/sock/sock_{s}_{a}_{v}_cm.rpsgl"
CENTRE = "rendering/icesurface/centerlogo_{a}_cm.rpsgl"
# which centre-ice file a team's home games show (lab rounds 31 and 58, the files RPCS3's log names in Play Now): the DEL's
# 14 clubs show their arena's art (OEtS.arenaartid; they share one, 197), the national teams always file 501, every other
# league the home team's own art (NHL, AHL, SHL, Liiga, Extraliga, NL, Norway, OHL, WHL played; the QMJHL and the Top
# Prospects taken to do the same)
ARENA_ICE_LEAGUES = (4,)
NATIONAL_LEAGUE, NATIONAL_ICE = 8, 501
ICE_PICTURE = "rendering/icesurface/icesurface_{a}_bm.rpsgl"      # the rink seen from above: the NHL teams' arenas have one
DECAL = "rendering/logo/texlib_{a}_{s}_{v}.rpsgl"                  # the logo on the helmets (and shoulders) of a version
PREVIEW = "fe/ion/artassets/jerseys/jersey_{s}_{a}_{v}.big"
# the other files of one version, copied for a version the disc has no files for (`Borrow`; a club's has the first four)
NAME = "rendering/jersey/name_{s}_{a}_{v}_cm.rpsgl"
DECAL_NHL = "rendering/logo/texlib_3{a}_{s}_{v}.rpsgl"
HELMET = "rendering/helmet/helmet_0_{a}_{v}_dm.rpsgl"
POWER = ("rendering/effects/powerring_{a}_{v}.rpsgl", "rendering/effects/powerring_lighting_{a}_{v}.rpsgl")
BORROWED = (NAME, DECAL, DECAL_NHL, HELMET) + POWER
FONT =os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'fonts', 'SourceSans3-Bold.ttf')

# version -> does it use the shared shirt layout? (nm-map correlation with Utah's, tools/look_preview.py --layouts)
STANDARD_LAYOUT = {22: {1: (0, 1, 3, 4)}, 30: {1: (2, 3, 4, 5)}, 31: {1: (2, 3, 4, 5)}}

# the flat colours of the chassis (RGB, measured on the disc's jersey colour maps) and where its crest and marks sit
MASTERS = ((130, 17, 19), (27, 27, 27), (234, 234, 234))         # body, yoke, trim of Utah's style-1 jerseys
CREST = (405, 640, 612, 880)                                      # the box the old crest is painted out of (1024 x 1024)
SHOULDER = ((345, 452, 430, 535), (592, 452, 686, 535))           # the old shoulder marks, left and right
NORMAL_FLAT = (CREST, (335, 445, 440, 540), (585, 445, 695, 540)) # parts of the normal map that carry the old relief

# the colours of a kit: what the chassis' body, yoke and trim colours become (jerseys and socks), what its black
# pants become, and what the number sheet's three colours (digits, outline, small digits' outline) become
Palette = namedtuple('Palette', 'body yoke trim pants font')
Kit = namedtuple('Kit', 'home away')
WHITE = (240, 240, 240)


def kit_for(primary, secondary):
    """A home (dark) and an away (light) kit from a team's two colours (the roster's). Dark: the second colour all
    over, the first as cuffs, stripes and digits. Light: white with the first colour's bands and the second colour's
    sleeves and digits."""
    return Kit(home=Palette(secondary, secondary, primary, secondary, (secondary, secondary, primary)),
               away=Palette(primary, secondary, WHITE, secondary, (secondary, secondary, WHITE)))


def _dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _clamp(v):
    return 0 if v < 0 else 255 if v > 255 else int(round(v))


def refine(img, seeds, tol=40):
    """The real colour of each seed: the mean of the picture's pixels within `tol` of it."""
    colours = img.convert('RGB').getcolors(1 << 22) or []
    out = []
    for seed in seeds:
        n = [0, 0, 0, 0]
        for count, c in colours:
            if _dist2(c, seed) <= tol * tol:
                n[0] += count
                for i in range(3):
                    n[i + 1] += count * c[i]
        out.append(tuple(n[i + 1] / n[0] for i in range(3)) if n[0] else tuple(seed))
    return tuple(out)


def _mapper(masters, targets, tol, shade):
    """A function: one colour of the chassis -> the team's colour (flat parts keep the cloth's shading; a blend of two
    chassis colours (an edge) becomes the same blend of the team's; a colour that is none of them stays)."""
    pairs = [(a, b) for a in range(len(masters)) for b in range(a + 1, len(masters))]

    def lum(c):
        return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2] + 1.0

    def one(c):
        k = min(range(len(masters)), key=lambda i: _dist2(c, masters[i]))
        if _dist2(c, masters[k]) <= tol * tol:
            m, t = masters[k], targets[k]
            if shade == 'mul':
                f = lum(c) / lum(m)
                return tuple(_clamp(t[i] * f) for i in range(3))
            return tuple(_clamp(t[i] + c[i] - m[i]) for i in range(3))
        best = None
        for a, b in pairs:
            ma, mb = masters[a], masters[b]
            d = [mb[i] - ma[i] for i in range(3)]
            n = sum(x * x for x in d) or 1
            t = max(0.0, min(1.0, sum((c[i] - ma[i]) * d[i] for i in range(3)) / n))
            p = tuple(ma[i] + t * d[i] for i in range(3))
            r = _dist2(c, p)
            if best is None or r < best[0]:
                best = (r, a, b, t, p)
        if best is None:                                   # one colour only: no blends to look for
            return c
        r, a, b, t, p = best
        if r > (tol * 1.3) ** 2:
            return c
        return tuple(_clamp(targets[a][i] + t * (targets[b][i] - targets[a][i]) + c[i] - p[i]) for i in range(3))
    return one


def recolour(img, masters, targets, tol=40, shade='add'):
    """`img` with the `masters` colours replaced by `targets` (see _mapper). The alpha channel stays as it is."""
    from PIL import Image
    rgba = img.convert('RGBA')
    rgb = rgba.convert('RGB')
    one = _mapper(masters, targets, tol, shade)
    lut = {c: one(c) for _n, c in (rgb.getcolors(1 << 22) or [])}
    raw = rgb.tobytes()
    data = [lut[(raw[i], raw[i + 1], raw[i + 2])] for i in range(0, len(raw), 3)]
    out = Image.new('RGB', rgb.size)
    out.putdata(data)
    out.putalpha(rgba.getchannel('A'))
    return out


def _ring_colour(img, box, margin=6):
    """The colour just outside `box` (the median of a thin ring around it): the cloth the old crest sat on."""
    l, t, r, b = box
    px = img.convert('RGB').load()
    seen = []
    for x in range(l, r, 4):
        seen += [px[x, max(0, t - margin)], px[x, min(img.height - 1, b + margin)]]
    for y in range(t, b, 4):
        seen += [px[max(0, l - margin), y], px[min(img.width - 1, r + margin), y]]
    return tuple(sorted(c[i] for c in seen)[len(seen) // 2] for i in range(3))


def _fill(img, box):
    """`box` of `img` painted over with the cloth colour around it."""
    from PIL import Image
    img.paste(Image.new('RGB', (box[2] - box[0], box[3] - box[1]), _ring_colour(img, box)), box[:2])


def _paste_mark(img, mark, box, turns=0):
    """The logo `mark` fitted into `box` (centred), turned a quarter turn `turns` times counter-clockwise."""
    from PIL import Image
    if turns:
        mark = mark.rotate(90 * turns, expand=True)
    scale = min((box[2] - box[0]) / mark.width, (box[3] - box[1]) / mark.height)
    mark = mark.resize((max(1, round(mark.width * scale)), max(1, round(mark.height * scale))), Image.LANCZOS)
    x, y = (box[0] + box[2] - mark.width) // 2, (box[1] + box[3] - mark.height) // 2
    layer = img.convert('RGBA')
    layer.alpha_composite(mark.convert('RGBA'), (x, y))
    img.paste(layer.convert('RGB'), (0, 0))


def jersey_colour(chassis_cm, palette, logo):
    """The colour map of a jersey (1024 x 1024): the chassis in the team's colours with the team's crest and marks."""
    out = recolour(chassis_cm, MASTERS, (palette.body, palette.yoke, palette.trim)).convert('RGB')
    _fill(out, CREST)
    for box in SHOULDER:
        _fill(out, box)
    if logo is not None:
        _paste_mark(out, logo, (418, 652, 600, 868))
        _paste_mark(out, logo, SHOULDER[0][:2] + (SHOULDER[0][2] - 4, SHOULDER[0][3] - 4), turns=1)
        _paste_mark(out, logo, (SHOULDER[1][0] + 4,) + SHOULDER[1][1:], turns=-1)
    return out


def flatten(img, boxes):
    """The normal map with the relief of the old crest and marks taken out: each box takes the mean of its own ring."""
    from PIL import Image
    out = img.convert('RGBA')
    px = out.load()
    for l, t, r, b in boxes:
        ring = [px[x, y] for x in range(l - 6, r + 6, 3) for y in (t - 6, b + 6)] + \
               [px[x, y] for y in range(t, b, 3) for x in (l - 6, r + 6)]
        mean = tuple(round(sum(c[i] for c in ring) / len(ring)) for i in range(4))
        out.paste(Image.new('RGBA', (r - l, b - t), mean), (l, t))
    return out


def _digest(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=list).encode()).hexdigest()[:12]


# --- the menu pictures of the jerseys ------------------------------------------------------------------------------
# `fe/ion/artassets/jerseys/jersey_<style>_<art>_<variant>.big` holds a 256 x 256 render of the jersey on a transparent
# ground (the same shirt, light and pose for every team, so the shirt is the part that differs from team to team).
PREVIEW_TEAMS = tuple(range(0, 30))


def preview_picture(art_file):
    """A menu preview (bytes of its .big) as a Pillow picture."""
    from PIL import Image
    from . import bigf, dds
    width, height, pixels = dds.read(bigf.ArtFile(art_file).image())
    img = Image.new('RGBA', (width, height))
    img.putdata([p for row in pixels for p in row])
    return img


def shirt_mask(disc, own, styles=(STYLE,)):
    """Where the shirt is in a menu preview: the pixels that differ between teams (the head, the gloves and the rest are
    the same in every preview). `own` are previews of the chassis. Returns a Pillow 'L' picture."""
    from PIL import Image, ImageChops, ImageFilter
    mask = Image.new('L', own[0].size, 0)
    for art in PREVIEW_TEAMS:
        for v in (0, 1, 2, 3, 4):
            raw = disc.find(PREVIEW.format(s=STYLE, a=art, v=v))
            if raw is None:
                continue
            other = preview_picture(raw).convert('RGB')
            if other.size != mask.size:
                continue
            for ref in own:
                diff = ImageChops.difference(ref.convert('RGB'), other).convert('L').point(lambda x: 255 if x > 28 else 0)
                mask = ImageChops.lighter(mask, diff)
    return mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))


def _classes(c):
    """How much a shaded colour of the preview belongs to each chassis colour: (body = red, yoke = black, trim = white)."""
    mx, mn = max(c), min(c)
    sat = (mx - mn) / mx if mx else 0
    lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    if sat > 0.38 and c[0] >= c[1] and c[0] >= c[2]:
        return (1.0, 0.0, 0.0)
    white = max(0.0, min(1.0, (lum - 70) / 50))                    # unsaturated: dark is the yoke, light is the trim
    return (0.0, 1.0 - white, white)


def recolour_preview(img, mask, palette_colours):
    """The menu preview with its shirt (inside `mask`) in new colours: each colour's class decides which of the three
    new colours it becomes, its brightness (the shading) is kept."""
    rgba = img.convert('RGBA')
    px, mk = rgba.load(), mask.load()
    inside = [(x, y) for y in range(rgba.height) for x in range(rgba.width) if mk[x, y] and px[x, y][3]]
    ref = [[], [], []]                                              # brightness of each class: its brighter half
    for x, y in inside:
        c = px[x, y]
        w = _classes(c[:3])
        k = w.index(max(w))
        ref[k].append(0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2])
    top = [sorted(v)[int(len(v) * 0.85)] if v else 128.0 for v in ref]
    cache = {}
    for x, y in inside:
        c = px[x, y]
        if c not in cache:
            w = _classes(c[:3])
            lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
            out = [0.0, 0.0, 0.0]
            for k in range(3):
                if w[k]:
                    f = lum / max(top[k], 1.0)
                    for i in range(3):
                        out[i] += w[k] * palette_colours[k][i] * f
            cache[c] = tuple(_clamp(v) for v in out) + (c[3],)
        px[x, y] = cache[c]
    return rgba


def crest_box(img, mask):
    """Where the crest sits in a menu preview: the cream parts of Utah's coyote (a colour the shirt has nowhere else),
    trimmed of strays and padded; (left, top, right, bottom)."""
    px, mk = img.convert('RGBA').load(), mask.load()
    mid = img.width // 2
    pts = [(x, y) for y in range(img.height // 3, img.height) for x in range(mid - img.width // 5, mid + img.width // 5)
           if mk[x, y] and px[x, y][3] > 200 and px[x, y][0] > 170 and px[x, y][1] > 135 and px[x, y][2] > 80
           and px[x, y][0] - px[x, y][2] > 45]
    if len(pts) < 20:
        return None
    xs, ys = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
    cut = max(1, len(pts) // 25)
    return xs[cut] - 6, ys[cut] - 20, xs[-cut] + 14, ys[-cut] + 8


def preview_image(chassis_img, mask, palette, logo):
    """The menu preview of a jersey as a picture: the chassis preview in the team's colours with the team's crest."""
    out = recolour_preview(chassis_img, mask, (palette.body, palette.yoke, palette.trim))
    box = crest_box(chassis_img, mask)
    if box is not None:
        _fill_rgba(out, box, mask, chassis_img)
        if logo is not None:
            _paste_rgba(out, logo, box)
    return out


def preview_file(chassis_img, mask, palette, logo, template_art):
    """The menu preview of a jersey (bytes of a .big) in the team's own art file `template_art` (only its picture changes)."""
    from . import install
    return install.art_file(template_art, preview_image(chassis_img, mask, palette, logo))


def _fill_rgba(img, box, mask, original, reach=11):
    """The old crest painted out of `img` inside `box`: the pixels of `original` (the chassis picture) that differ from the
    shirt colour around the crest, a little widened, take the average of the (recoloured) shirt pixels near them, so the
    cloth's light and shade run on under the new crest."""
    from PIL import Image, ImageChops, ImageFilter
    px0, mk = original.convert('RGBA').load(), mask.load()
    ring = [px0[x, y][:3] for x in range(max(0, box[0] - 5), min(img.width, box[2] + 5)) for y in (box[1] - 4, box[3] + 4)
            if 0 <= y < img.height and mk[x, y] and px0[x, y][3] > 200]
    ring += [px0[x, y][:3] for y in range(max(0, box[1]), min(img.height, box[3])) for x in (box[0] - 4, box[2] + 4)
             if 0 <= x < img.width and mk[x, y] and px0[x, y][3] > 200]
    if not ring:
        return
    old = tuple(sorted(c[i] for c in ring)[len(ring) // 2] for i in range(3))
    region = original.convert('RGB').crop(box)
    diff = ImageChops.difference(region, Image.new('RGB', region.size, old)).convert('L').point(lambda v: 255 if v > 40 else 0)
    crest = diff.filter(ImageFilter.MaxFilter(7))
    w, h = region.size
    cp, sp = crest.load(), img.load()
    good = {}
    for y in range(-reach, h + reach):
        for x in range(-reach, w + reach):
            X, Y = box[0] + x, box[1] + y
            inside = 0 <= x < w and 0 <= y < h
            if 0 <= X < img.width and 0 <= Y < img.height and mk[X, Y] and sp[X, Y][3] > 200 and not (inside and cp[x, y]):
                good[(x, y)] = sp[X, Y][:3]
    out = []
    for y in range(h):
        for x in range(w):
            if not cp[x, y]:
                out.append(None)
                continue
            tot, wsum = [0.0, 0.0, 0.0], 0.0
            for yy in range(y - reach, y + reach + 1, 2):
                for xx in range(x - reach, x + reach + 1, 2):
                    c = good.get((xx, yy))
                    if c:
                        k = 1.0 / (1 + (xx - x) ** 2 + (yy - y) ** 2)
                        wsum += k
                        for i in range(3):
                            tot[i] += k * c[i]
            out.append(tuple(round(t / wsum) for t in tot) + (255,) if wsum else None)
    for i, c in enumerate(out):
        if c is not None and mk[box[0] + i % w, box[1] + i // w]:
            img.putpixel((box[0] + i % w, box[1] + i // w), c)


def _paste_rgba(img, mark, box):
    from PIL import Image
    scale = min((box[2] - box[0]) / mark.width, (box[3] - box[1]) / mark.height)
    mark = mark.convert('RGBA').resize((max(1, round(mark.width * scale)), max(1, round(mark.height * scale))), Image.LANCZOS)
    img.alpha_composite(mark, ((box[0] + box[2] - mark.width) // 2, (box[1] + box[3] - mark.height) // 2))


# the pack's own menu picture of a kit (`ui/textures/common/teamjerseysxl/jersey_<cut>_<art>_0_<variant>`, 512 x 512: the
# shirt alone, turned a little, on a clear ground; the look pack keeps it as `m/<slot>_<role>.webp`) goes onto the game's
# black figure: the chassis' menu picture without its shirt, the gloves moved under the pack's cuffs. Every pack kit is
# drawn in the same pose, so the collar and the cuffs sit at the same shares of the shirt's width and height in all of
# them (measured on 9 kits of the three makes, 2026-10-18).
MENU_COLLAR = 0.568                            # the collar's middle, share of the shirt's width
MENU_CUFFS = ((0.15, 0.77), (0.92, 0.74))      # the left and right cuff's lower middle, shares of width and height
MENU_TUCK = 5                                  # how far a glove reaches up into its sleeve (pixels)
MENU_REACH = 14                                # how far the neck and the legs go on under the place the shirt was
Figure = namedtuple('Figure', 'body gloves')
# body: the figure's alpha ('L'; the figure is black); gloves: ((0 left / 1 right, alpha of the glove, (x, y) of its top
# middle), ...)


def menu_frame(chassis_img, mask):
    """Where the game's shirt is in the chassis' menu picture: (the middle of the figure's head, (left, top, right, bottom)
    of the shirt; the mask's rows with at least 20 shirt pixels, so stray pixels do not count)."""
    mk = mask.load()
    w, h = mask.size
    rows = [(y, [x for x in range(w) if mk[x, y]]) for y in range(h)]
    rows = [(y, xs) for y, xs in rows if len(xs) >= 20]
    if not rows:
        return w / 2, (0, 0, w - 1, h - 1)
    top, bottom = rows[0][0], rows[-1][0]
    left, right = min(xs[0] for _y, xs in rows), max(xs[-1] for _y, xs in rows)
    alpha = chassis_img.convert('RGBA').getchannel('A').crop((0, 0, w, max(1, top))).point(lambda v: 255 if v > 40 else 0)
    head = alpha.getbbox()
    return ((head[0] + head[2] - 1) / 2 if head else (left + right) / 2), (left, top, right, bottom)


def menu_figure(chassis_img, mask, reach=MENU_REACH):
    """The game's black figure in the chassis' menu picture, without the shirt (a Figure). The figure is pure black, so
    its alpha is all there is; the shirt's coloured edge pixels outside the mask are left out. The gloves are the figure's
    parts beside the legs below the shirt's middle; the head and the legs go on `reach` pixels into the place the shirt
    was, so no gap shows where the pack's shirt is cut another way."""
    from PIL import Image
    src = chassis_img.convert('RGBA')
    sp, mk = src.load(), mask.load()
    w, h = src.size
    head_x, (left, top, right, bottom) = menu_frame(chassis_img, mask)
    fig = Image.new('L', (w, h), 0)
    fp = fig.load()
    for y in range(h):
        for x in range(w):
            c = sp[x, y]
            if not mk[x, y] and max(c[:3]) < 64:
                fp[x, y] = c[3]
    legs = []                                   # the legs: the run of the figure through the middle below the shirt
    mid = int(head_x)
    for y in range(bottom + 1, h):
        if fp[mid, y] > 40:
            a = b = mid
            while a > 0 and fp[a - 1, y] > 40:
                a -= 1
            while b < w - 1 and fp[b + 1, y] > 40:
                b += 1
            legs.append((a, b))
    gloves, body = [], fig.copy()
    if legs:
        leg_left, leg_right = min(a for a, _b in legs), max(b for _a, b in legs)
        bp = body.load()
        for side, beside in enumerate((lambda x: x < leg_left, lambda x: x > leg_right)):
            glove = Image.new('L', (w, h), 0)
            gp = glove.load()
            for y in range((top + bottom) // 2, h):
                for x in range(w):
                    if beside(x) and fp[x, y]:
                        gp[x, y], bp[x, y] = fp[x, y], 0
            solid = glove.point(lambda v: 255 if v > 40 else 0)
            box = solid.getbbox()
            if box is None:
                continue
            sx = solid.load()
            xs = [x for y in range(box[1], min(box[3], box[1] + 6)) for x in range(box[0], box[2]) if sx[x, y]]
            gloves.append((side, glove, (sum(xs) / len(xs), box[1])))
    bp = body.load()
    keep = body.copy()
    kp = keep.load()
    for x in range(w):
        for y in range(h):
            if mk[x, y] or kp[x, y] <= 40:
                continue
            for step in (-1, 1):
                yy, n = y + step, 0
                while 0 <= yy < h and mk[x, yy] and n < reach:
                    bp[x, yy] = max(bp[x, yy], kp[x, y])
                    yy, n = yy + step, n + 1
    return Figure(body, tuple(gloves))


def menu_picture(chassis_img, mask, kit_menu, figure=None):
    """The Select Jerseys picture of a kit from the pack's own menu picture `kit_menu` (RGBA, the shirt on a clear ground):
    the shirt as tall (or as wide) as the game's, its top at the game's shoulders, its collar under the figure's head, on
    the game's black figure (`figure`: menu_figure, made when not given) with the gloves under the pack's cuffs. 256 x 256
    RGBA like the game's."""
    from PIL import Image, ImageChops
    head_x, (left, top, right, bottom) = menu_frame(chassis_img, mask)
    figure = figure or menu_figure(chassis_img, mask)
    shirt = kit_menu.convert('RGBA')
    box = shirt.getchannel('A').point(lambda v: 255 if v > 16 else 0).getbbox()
    alpha = figure.body.copy()
    out = Image.new('RGBA', alpha.size, (0, 0, 0, 0))
    if box is None:
        out.putalpha(alpha)
        return out
    shirt = shirt.crop(box)
    scale = min((right - left + 1) / shirt.width, (bottom + 4 - top) / shirt.height)
    shirt = shirt.resize((max(1, round(shirt.width * scale)), max(1, round(shirt.height * scale))), Image.LANCZOS)
    x = max(0, min(out.width - shirt.width, round(head_x - MENU_COLLAR * shirt.width)))
    for side, glove, (gx, gy) in figure.gloves:
        cx, cy = MENU_CUFFS[side]
        moved = Image.new('L', alpha.size, 0)
        moved.paste(glove, (round(x + cx * shirt.width - gx), round(top + cy * shirt.height - MENU_TUCK - gy)))
        alpha = ImageChops.lighter(alpha, moved)
    out.putalpha(alpha)
    layer = Image.new('RGBA', out.size, (0, 0, 0, 0))
    layer.paste(shirt, (x, top))
    return Image.alpha_composite(out, layer)


# --- the centre-ice logo -----------------------------------------------------------------------------------------
# measured on the disc's own `centerlogo_<art>_cm` (1024 x 1024 DXT5): an opaque ice-white disc about 388 px in radius
# with a thin blue ring, the club's logo on it, the arena's name set round it outside the disc (twice: above and
# below, the left word on the left half), and a strip 48 px wide at x 488-536 that is fully transparent (the red line
# crosses there). Every transparent pixel carries the ice colour in its RGB, the strip the logo's colours bled in.
ICE = (231, 233, 231)
RING = (8, 60, 173)
DISC_RADIUS = 388
STRIP = (488, 536)


def split_arena(name):
    """An arena's name as the two halves the ice shows (left word(s), right word(s)): 'The Delta Center' ->
    ('DELTA', 'CENTER'); 'Climate Pledge Arena' -> ('CLIMATE', 'PLEDGE ARENA')."""
    words = name.upper().split()
    if len(words) > 2 and words[0] == 'THE':
        words = words[1:]
    if len(words) < 2:
        return (' '.join(words), '')
    cut = min(range(1, len(words)), key=lambda k: abs(len(' '.join(words[:k])) - len(' '.join(words[k:]))))
    return ' '.join(words[:cut]), ' '.join(words[cut:])


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def _ring_base(size, top, scale):
    """Radius of the baseline the letters of one size ride on: above they stand outside it, below the baseline is the
    outer edge and the letters point in."""
    return (DISC_RADIUS + 34) * scale + (0 if top else size * 0.66)


def _advances(text, font, scale):
    return [font.getlength(c) + 3 * scale for c in text]


def _fit_size(text, scale):
    """The biggest letter size (px, at `scale`) for which `text` spans at most 58 degrees of the ring."""
    size = 86 * scale
    while size > 30 * scale:
        font = _font(size)
        if math.degrees(sum(_advances(text, font, scale)) / _ring_base(size, True, scale)) <= 58:
            break
        size = int(size * 0.94)
    return size


def _arc_word(canvas, text, mid, top, colour, scale, size):
    """`text` set along the outside of the disc, its middle `mid` degrees from straight up (top) or straight down
    (below), negative to the left; letters stand upright (their tops point away from the disc above, towards it below)."""
    from PIL import Image, ImageDraw
    if not text:
        return
    cx = canvas.width // 2
    font = _font(size)
    advance = _advances(text, font, scale)
    base = _ring_base(size, top, scale)
    angle = math.radians(mid) - sum(advance) / base / 2
    tile = int(size * 2)
    for c, adv in zip(text, advance):
        theta = angle + adv / base / 2
        angle += adv / base
        glyph = Image.new('RGBA', (tile, tile), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((tile / 2, tile / 2), c, font=font, fill=tuple(colour) + (255,), anchor='ms')
        glyph = glyph.rotate(-math.degrees(theta) if top else math.degrees(theta), resample=Image.BICUBIC)
        x = cx + base * math.sin(theta)
        y = cx - base * math.cos(theta) if top else cx + base * math.cos(theta)
        canvas.alpha_composite(glyph, (round(x - tile / 2), round(y - tile / 2)))


def centre_logo(logo, arena, colour=(32, 32, 32), size=1024):
    """The centre-ice logo for a team: the club's logo on the ice-white disc with the thin ring, the arena's name round
    it, transparent where the red line crosses (and ice-white under everything transparent, as the game's own are)."""
    from PIL import Image, ImageDraw
    scale = 2
    big = size * scale
    cx = big // 2
    canvas = Image.new('RGBA', (big, big), ICE + (0,))
    draw = ImageDraw.Draw(canvas)
    r = DISC_RADIUS * scale
    draw.ellipse((cx - r, cx - r, cx + r, cx + r), fill=RING + (255,))
    r2 = r - 8 * scale
    draw.ellipse((cx - r2, cx - r2, cx + r2, cx + r2), fill=ICE + (255,))
    if logo is not None:
        box = int(2 * r2 * 0.80)
        k = min(box / logo.width, box / logo.height)
        mark = logo.convert('RGBA').resize((max(1, round(logo.width * k)), max(1, round(logo.height * k))), Image.LANCZOS)
        canvas.alpha_composite(mark, (cx - mark.width // 2, cx - mark.height // 2))
    left, right = split_arena((arena or '').translate({ord(c): None for c in '®™℠'}).strip())     # no marks on the ring
    size_px = min((_fit_size(t, scale) for t in (left, right) if t), default=0)       # both halves in one size
    for text, mid in ((left, -32), (right, 32)):
        _arc_word(canvas, text, mid, True, colour, scale, size_px)
        _arc_word(canvas, text, mid, False, colour, scale, size_px)
    return finish_centre(canvas.resize((size, size), Image.LANCZOS))


def finish_centre(img):
    """A centre-ice picture the way the game's own are: ice-white under everything transparent, the strip where the red
    line crosses transparent and carrying the picture's colours bled in from its edges. Used for ours and the player's."""
    from PIL import Image
    img = img.convert('RGBA')
    size = img.width
    k = size / 1024
    s0, s1 = round(STRIP[0] * k), round(STRIP[1] * k)
    rgb, alpha = img.convert('RGB'), img.getchannel('A')
    ice = Image.new('RGB', img.size, ICE)
    rgb = Image.composite(rgb, ice, alpha.point(lambda v: 255 if v else 0))
    half = (s0 + s1) // 2
    rgb.paste(rgb.crop((s0 - 2, 0, s0 - 1, img.height)).resize((half - s0, img.height)), (s0, 0))   # the colours bled in
    rgb.paste(rgb.crop((s1 + 1, 0, s1 + 2, img.height)).resize((s1 - half, img.height)), (half, 0))
    alpha.paste(0, (s0, 0, s1, img.height))
    rgb.putalpha(alpha)
    return rgb


def centre_file(raw, art, logo, arena, colour, picture=None):
    """The team's own centre-ice file with the new picture in it (`picture`: the player's own, else drawn from the logo)."""
    f = rpsgl.Rpsgl(raw)
    f.replace(f"centerlogo_{art}_cm", finish_centre(picture) if picture is not None else centre_logo(logo, arena, colour),
              flat=ICE)              # opaque or clear in every level, as the game's own: no hatch (dds.flatten)
    return f.build()


def has_ice_picture(art):
    """Does the team's arena have a rink picture on the disc (the NHL teams 0-29 do, not the All-Star slots 30 and 31)?"""
    return art < 30


OTHER = 'other'     # a look's centre when the new centre ice (art/brightice.py) has the team's centre: no centre file here


def _ice_picture_wanted(look):
    """Is the rink picture redrawn with the team's logo? With a new centre-ice logo of an NHL team, except the pack's (or
    the new centre ice's, `OTHER`) on a team whose rink picture already shows its own logo (only Utah's shows Arizona's)."""
    return look.centre != 'game' and has_ice_picture(look.art) and (
        not (look.centre.startswith('pack:') or look.centre == OTHER) or look.art in NEW_TEAMS)


def _makes_centre(look):
    return look.centre not in ('game', OTHER)


# where the centre-ice logo sits in the rink picture (512 x 512): its middle, and the half width of what to paint over
RINK_CENTRE, RINK_REACH = (257, 255), 44


def ice_picture_file(raw, art, logo):
    """The team's rink picture with Arizona's coyote at centre ice taken out and the team's logo in its place (the red
    line stays across it). The game shows this picture under the centre-ice logo."""
    from PIL import Image
    f = rpsgl.Rpsgl(raw)
    name = f"icesurface_{art}_bm"
    img = f.image(name).convert('RGBA')
    cx, cy = RINK_CENTRE
    box = (cx - RINK_REACH, cy - RINK_REACH, cx + RINK_REACH, cy + RINK_REACH)
    line = [y for y in range(box[1], box[3]) if _is_red(img.getpixel((box[0] - 2, y)))]
    for y in range(box[1], box[3]):                        # the ice as it is left of the old logo, across it
        img.paste(Image.new('RGBA', (box[2] - box[0], 1), img.getpixel((box[0] - 2, y))), (box[0], y))
    if logo is not None:
        size = RINK_REACH * 1.3
        k = min(size / logo.width, size / logo.height)
        mark = logo.convert('RGBA').resize((max(1, round(logo.width * k)), max(1, round(logo.height * k))), Image.LANCZOS)
        img.alpha_composite(mark, (cx - mark.width // 2, cy - mark.height // 2))
    for y in line:                                         # the red line over the logo, as the game's own picture has it
        red = f.image(name).getpixel((box[0] - 2, y))
        over = Image.new('RGBA', (box[2] - box[0], 1), red[:3] + (100,))
        img.alpha_composite(over, (box[0], y))
    f.replace(name, img)
    return f.build()


def _is_red(c):
    return c[0] - c[1] > 60 and c[0] - c[2] > 40


def decal_file(raw, art, variant, logo):
    """The team's logo on the helmet (and shoulder) decal of a version, on a white edge as the game's own are."""
    from PIL import Image
    from . import images
    f = rpsgl.Rpsgl(raw)
    name = f"logo_{art}_{STYLE}_{variant}_0"
    r = f.rasters[name]
    canvas = Image.new('RGBA', (r['width'], r['height']), (0, 0, 0, 0))
    if logo is not None:
        mark = images._crop_centred(images._outlined(images._fit(images._trim(logo), r['width'] * 0.8, r['height'] * 0.8), 2))
        mark = images._fit(mark, r['width'] * 0.9, r['height'] * 0.9)
        canvas.alpha_composite(mark, ((canvas.width - mark.width) // 2, (canvas.height - mark.height) // 2))
    f.replace(name, canvas)
    return f.build()


# --- the files ---------------------------------------------------------------------------------------------------
PANT_MASTERS = ((22, 22, 22), (234, 234, 234))                   # the chassis' pants: black with white stripes


class Chassis:
    """Utah's own style-1 files on the player's disc (the cloth the other teams' are cut from), read once."""

    def __init__(self, disc):
        self.disc = disc
        self.files = {}
        self.shades = {}

    def shade(self, light):
        """The chassis sock's shading (`sock_shade`), worked out once per light / dark."""
        if light not in self.shades:
            self.shades[light] = sock_shade(self.sock(light).image(f"sock_{STYLE}_{CHASSIS_ART}_{CHASSIS[light]}_cm"))
        return self.shades[light]

    def _get(self, inner):
        if inner not in self.files:
            raw = self.disc.render(inner)
            if raw is None:
                raise rpsgl.RpsglError(f"the disc has no {inner}")
            self.files[inner] = rpsgl.Rpsgl(raw)
        return self.files[inner]

    def jersey(self, light):
        return self._get(JERSEY.format(s=STYLE, a=CHASSIS_ART, v=CHASSIS[light]))

    def pant(self, light):
        return self._get(PANT.format(s=STYLE, a=CHASSIS_ART, v=CHASSIS[light]))

    def sock(self, light):
        return self._get(SOCK.format(s=STYLE, a=CHASSIS_ART, v=CHASSIS[light]))


Look = namedtuple('Look', 'art kit logos arena ice_colour versions files centre pack style',
                  defaults=((), 'make', (), STYLE))
# art: the team's art id; kit: a Kit; logos: (logo for dark jerseys, logo for light jerseys and the ice) as Pillow pictures;
# arena: the name on the ice; ice_colour: the colour of that name; versions: ((variant, is the version a light one), ...) made
# from the colours; files: ((variant, light, path of the player's own colour map), ...); centre: 'make' (drawn from the logo),
# 'game' (the game's own stays), 'pack:<member>#<check>' (the pack's, from the look pack) or the path of the player's own
# picture; pack: (PackKit, ...) the pack's kits; style: the cut of the team's jerseys (1, or 0 for a team of the classic cut:
# only its pack kits are made then)
PackKit = namedtuple('PackKit', 'variant light member numbers crc menu scheme font like sock pants',
                     defaults=(None, None, None, None, None, None))
# a version that gets the pack's kit: the look pack's picture `member` (its check sum `crc`), numbers (fill, outline) or None,
# menu: the pack's own menu picture of the kit as '<member>#<check sum>' (None: the menu picture is the chassis' recoloured),
# scheme: (ring, outer, name) of its number sheet (the digits' two rings, outer or None, and the colour of the names), or None
# (a pack from before: the names wear the digits' colour); font: the pack's own number sheet as '<member>#<check sum>'
# (None: the sheet is recoloured from the colours above); like: the variant whose disc files a version the disc has none for
# (a row `alternate_rows` added) starts from (`Borrow`), or None; sock: the pack's own sock of the kit as '<member>#<check sum>'
# and pants: its pants' (main, stripe) colours (0.95.0; None: both are the chassis' in the kit's colours, `kit_palette`)
PACK = 'pack'                    # the choice "This season's" (edits.json 'uniforms' versions and 'ice' use)


ALTERNATE = 2                      # `wgjx` locstring of the Alternate version (version_words)


def roster_versions(R, art, style=STYLE):
    """The jersey versions of a team the roster lists (`stockteamjerseys`) in cut `style` (style 1: the one Play Now uses
    for the NHL): [(variant, light, isdefault)] sorted; empty when the roster has no such table."""
    try:
        t = R.f['wgjx']
    except KeyError:
        return []
    return sorted({(t.get(i, 'variant'), bool(t.get(i, 'islightcolor')), bool(t.get(i, 'isdefault')))
                   for i in range(t.cur_rec) if t.get(i, 'teamartid') == art and t.get(i, 'style') == style})


def version_words(R, art, style=STYLE):
    """{variant: locstring}: the word the game's Select Jerseys shows for each version of a team in cut `style` (0 Home,
    1 Away, 2 Alternate, others a season's name such as "2009-10 Classic"; lab round 34). Not the colour: the old AHL
    clubs' light version is their Home one (Charlotte, Utica)."""
    try:
        t = R.f['wgjx']
    except KeyError:
        return {}
    return {t.get(i, 'variant'): t.get(i, 'locstring') for i in range(t.cur_rec)
            if t.get(i, 'teamartid') == art and t.get(i, 'style') == style}


def jersey_versions(R, art):
    """The versions of a team the roster lists that use the shared layout: [(variant, light)] in style 1."""
    wanted = STANDARD_LAYOUT.get(art, {}).get(STYLE, ())
    return tuple((v, light) for v, light, _d in roster_versions(R, art) if v in wanted)


def art_style(R, art):
    """The cut (style) of a team's default jerseys in the roster (`stockteamjerseys`), or None when it lists none or two."""
    try:
        t = R.f['wgjx']
    except KeyError:
        return None
    styles = {t.get(i, 'style') for i in range(t.cur_rec) if t.get(i, 'teamartid') == art and t.get(i, 'isdefault')}
    return min(styles) if len(styles) == 1 else None


def pack_versions(R, art, style):
    """{role: (variant, light)}: the versions of a team the pack's kits go on: 'dark' and 'light', the default dark and
    light versions of the team's cut, and (0.92.0, owner: the alternates too) 'third', the lowest Alternate version
    (`locstring` 2) the roster lists in that cut. Every other version stays the game's own."""
    try:
        t = R.f['wgjx']
    except KeyError:
        return {}
    rows = sorted((t.get(i, 'variant'), bool(t.get(i, 'islightcolor')))
                  for i in range(t.cur_rec)
                  if t.get(i, 'teamartid') == art and t.get(i, 'style') == style and t.get(i, 'isdefault'))
    out = {}
    for variant, light in rows:
        out.setdefault('light' if light else 'dark', (variant, light))
    taken = {variant for variant, _light in out.values()}
    alternates = sorted((t.get(i, 'variant'), bool(t.get(i, 'islightcolor')))
                        for i in range(t.cur_rec)
                        if t.get(i, 'teamartid') == art and t.get(i, 'style') == style and t.get(i, 'locstring') == ALTERNATE
                        and not t.get(i, 'isdefault'))
    for variant, light in alternates:
        if variant not in taken:                     # a variant number a home or away row uses is never the third's
            out['third'] = (variant, light)
            break
    return out


NHL = range(32)                    # the NHL's slots (their art id is the slot)


def team_art(R, slot):
    """(art id, cut) of a team's jerseys: the cut of its default versions (`art_style`), style 1 for the NHL (Play Now's
    cut) and when the roster lists none or two."""
    art = R.T.get(slot, 'artid')
    style = None if slot in NHL else art_style(R, art)
    return art, STYLE if style is None else style


def jersey_owner(R, slot):
    """The slot whose jerseys these are: the lowest slot with the same art id (the Winter Classic, EASHL and Top Prospects
    teams share an NHL team's or each other's)."""
    T = R.T
    art = T.get(slot, 'artid')
    return next(s for s in range(T.cur_rec) if T.get(s, 'artid') == art)


def team_versions(R, slot):
    """[(variant, light, isdefault)]: the versions of a team the Roster editor offers and the update makes: every style-1
    version of an NHL team (Utah, Seattle and Vegas: DEFAULT_VERSIONS when the roster lists none), the home and away
    (default) versions of the team's cut elsewhere, and its Alternate versions (0.92.0; the others stay Legacy's own)."""
    art, style = team_art(R, slot)
    listed = roster_versions(R, art, style)
    if slot in NHL:
        return listed or [(v, light, False) for v, light in DEFAULT_VERSIONS.get(slot, ())]
    alternates = set(_alternate_variants(R, art, style))
    return [row for row in listed if row[2] or row[0] in alternates]


def _alternate_variants(R, art, style):
    """The variant numbers of a team's Alternate rows (`locstring` 2) in cut `style`."""
    try:
        t = R.f['wgjx']
    except KeyError:
        return []
    return [t.get(i, 'variant') for i in range(t.cur_rec)
            if t.get(i, 'teamartid') == art and t.get(i, 'style') == style and t.get(i, 'locstring') == ALTERNATE
            and not t.get(i, 'isdefault')]


ROWS_MAX = 749                     # the most rows table wgjx holds (stock.ROSTER_MAX)
ROWS_KEPT = sum(len(variants) for _, variants in L.CLUB_DONOR.values())     # gamepatch.art_fit adds these after us
ROW_VARIANT, ROW_FEVARIANT, ROW_INDEX, ROW_WORD, ROW_DEFAULT = 'TccF', 'XOdd', 'xnYt', 'gZuU', 'MSFy'


def alternate_rows(R, look_pack):
    """Give a team the look pack has a third kit for but the roster no Alternate version (Winnipeg, Chicago, a score of
    AHL / CHL clubs, 0.92.0) a row of its own in `wgjx` (stockteamjerseys), in place: its away row with the next free variant
    number, the next jersey index, the word Alternate (2) and not a default. The files come from `Borrow` (the away version's,
    painted with the pack's third). Deterministic and done once: a roster that lists the Alternate (the game's or this row)
    gets nothing. Returns [(slot, art, variant)] of the rows added."""
    added = []
    try:
        t = R.f['wgjx']
    except KeyError:
        return added
    for slot, team in sorted((getattr(look_pack, 'teams', None) or {}).items()):
        if 'third' not in (team.get('kits') or {}) or slot >= R.T.cur_rec or not look_pack.holds(slot, R):
            continue
        art = R.T.get(slot, 'artid')
        style = art_style(R, art)
        if style is None or style != team.get('style') or jersey_owner(R, slot) != slot or pack_versions(R, art, style).get('third'):
            continue
        rows = [i for i in range(t.cur_rec) if t.get(i, 'teamartid') == art]
        away = _away_row(R, art, style)
        if away is None or t.cur_rec >= ROWS_MAX - ROWS_KEPT:
            continue
        variant = max(t.get(i, 'variant') for i in rows) + 1
        if len(str(variant)) != len(str(t.get(away, 'variant'))):         # the files' names keep their length (Borrow)
            continue
        row = {f: t.get(away, f) for f in t.fields}
        row.update({ROW_VARIANT: variant, ROW_FEVARIANT: variant, ROW_WORD: ALTERNATE, ROW_DEFAULT: 0,
                    ROW_INDEX: max(t.get(i, 'jerseyindex') for i in rows) + 1})
        t.add_record(row)
        added.append((slot, art, variant))
    return added


def _away_row(R, art, style):
    """The index in `wgjx` of a team's Away row (`locstring` 1, a default) in cut `style`, else its light default one, else
    None."""
    t = R.f['wgjx']
    rows = [i for i in range(t.cur_rec) if t.get(i, 'teamartid') == art and t.get(i, 'style') == style and t.get(i, 'isdefault')]
    return next((i for i in rows if t.get(i, 'locstring') == 1), next((i for i in rows if t.get(i, 'islightcolor')), None))


def away_variant(R, art, style):
    """The variant number of a team's Away version (_away_row), or None."""
    i = _away_row(R, art, style)
    return None if i is None else R.f['wgjx'].get(i, 'variant')


def renamed_variant(raw, art, style, old, new):
    """The texture file `raw` (bytes) of version `old` of art `art` with the version's number in the raster names of its
    header (`jersey_1_23_6_cm`, `23_1_6`, `powerring_23_6`) changed to `new`: the same digit count, so nothing moves."""
    if len(str(old)) != len(str(new)):
        raise ValueError(f"{old} -> {new}: the numbers differ in length")
    f = rpsgl.Rpsgl(raw)
    data = bytearray(f.data)
    data[:f.header] = re.sub(rf'(?<!\d)(3?{art})_((?:{style}_)?){old}(?!\d)'.encode(), rf'\g<1>_\g<2>{new}'.encode(),
                             bytes(data[:f.header]))
    return rpsgl.Rpsgl(rpsgl.pack(bytes(data)) if f.packed else bytes(data)).build()


class Borrow:
    """The disc as `Maker` reads it, with the files of a version the disc lacks (an Alternate version `alternate_rows` gave a
    team) read from another version of the same team: a 3D texture with its number changed (`renamed_variant`), a menu
    picture as it is. `lend` names the pairs; a file the disc has itself is never replaced."""

    def __init__(self, disc):
        self.disc = disc.disc if isinstance(disc, Borrow) else disc
        self.lent = {}                                  # {path: the path it is read from}

    def __getattr__(self, name):
        return getattr(self.disc, name)

    def lend(self, art, style, new, like):
        for template in (JERSEY, PANT, SOCK, PREVIEW) + BORROWED:
            mine, theirs = (template.format(s=style, a=art, v=v) for v in (new, like))
            if not self.disc.has(mine) and self.disc.has(theirs):
                self.lent[mine] = (theirs, art, style, like, new)

    def has(self, inner):
        return self.disc.has(self.lent[inner][0] if inner in self.lent else inner)

    def find(self, inner):
        return self.disc.find(self.lent[inner][0] if inner in self.lent else inner)

    def render(self, inner):
        if inner not in self.lent:
            return self.disc.render(inner)
        path, art, style, like, new = self.lent[inner]
        raw = self.disc.render(path)
        return None if raw is None else renamed_variant(raw, art, style, like, new)


def club_logos(R, leagues):
    """{slot: logo link} of the clubs of the data pack's leagues (`leagues`, datasource: 'leagues') that roster `R` holds
    in their slots (a league left out of the update leaves other teams there)."""
    out = {}
    for league in (leagues or {}).values():
        for t in league.get('teams') or []:
            if t.get('logo') and not t.get('own') and R.T.get(t['slot'], 'JkmY') == t.get('full'):
                out[t['slot']] = t['logo']
    return out


def editable(R, slot):
    """Why the Roster editor cannot change the jerseys and ice of slot `slot` (a sentence for the player), or None when it
    can."""
    if not isinstance(slot, int) or not 0 <= slot < R.T.cur_rec:
        return "Pick a team first."
    if not team_versions(R, slot):
        return "The game has no jerseys of its own for this team."
    owner = jersey_owner(R, slot)
    if owner != slot:
        return f"This team wears the jerseys of {R.team_name(owner)}: change them there."
    return None


def number_roles(fill, outline, light):
    """Colours for `recolour(chassis number sheet, MASTERS, roles)`: the chassis' dark sheet (v3) has a white fill with red
    and black outlines, its light sheet (v4) a red fill with white and black outlines."""
    return (fill, outline, outline) if light else (outline, outline, fill)


def sheet_colours(font):
    """The one or two colours a number sheet is painted in (fill, then outline when it has one): its most common opaque
    colours, a second one only when it covers 5 % as much as the first and differs clearly."""
    from PIL import Image
    img = font.convert('RGBA').resize((256, 256), Image.NEAREST)
    counts, raw = {}, img.tobytes()
    for i in range(0, len(raw), 4):
        if raw[i + 3] > 200:
            key = (raw[i] // 8, raw[i + 1] // 8, raw[i + 2] // 8)
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked:
        return ()
    fill = tuple(v * 8 + 4 for v in ranked[0][0])
    for key, n in ranked[1:]:
        colour = tuple(v * 8 + 4 for v in key)
        if n < ranked[0][1] * 0.05:
            break
        if _dist2(colour, fill) > 60 * 60:
            return fill, colour
    return (fill,)


def recolour_sheet(font, fill, outline, name=None):
    """A version's own number sheet (style 0: each club has its own lettering) in the pack's number colours; the letters on
    top get the names' colour `name` when there is one."""
    own = sheet_colours(font)
    if not own:
        return font.convert('RGBA')
    out = recolour(font, own, (fill, outline)[:len(own)], tol=48)
    if name is not None:
        for top, bottom, right in LETTER_ROWS:
            box = (0, round(font.height * top), round(font.width * right), round(font.height * bottom))
            letters = sheet_colours(font.crop(box))
            if letters:
                out.paste(recolour(font.crop(box), letters[:1], (name,), tol=48), box[:2])
    return out


Numbers = namedtuple('Numbers', 'fill ring outer name')      # a pack kit's number sheet colours (see recolour_numbers)


def _font_key(font):
    return [list(c) if c is not None else None for c in font] if isinstance(font, Numbers) else list(map(list, font))


LETTER_ROWS = ((0.0, 0.105, 1.0), (0.105, 0.20, 0.82))     # the names' letters on a number sheet: top, bottom, right edge
SMALL_FROM = 0.716                 # the small digits start below here (the clear rows 366-367 of 512); the big digits and C / A above
OUTER_RING = 0.004                                         # the digits' outer ring: this part of the sheet's width
NAME_ROWS = ((0.0, 0.0, 1.0, 0.09), (0.0, 0.094, 0.82, 0.20))   # the chassis' two rows of letters: left, top, right, bottom
EMPTY_CELL = 24                    # a cell of a pack's sheet whose alpha stays under this holds no glyph


def recolour_numbers(font, light, fill, ring, outer, name):
    """The chassis' number sheet `font` (dark: white digits with a black outline, light: red digits with a black outline; the
    letters on top, the small digits below white with a red outline in both) in a kit's colours (`fill`, `ring`, `outer`, `name`):
    the letters in the names' colour, the big digits and C / A in `fill` with the ring around them and a second ring carved
    into their outer edge, the small digits the same without the second ring. Nothing is drawn outside the chassis' glyphs
    (the alpha stays the chassis'): a ring grown outwards reached into the next row of glyphs, which the game showed as a
    line under and over the number (2026-10-27)."""
    from PIL import Image, ImageChops, ImageFilter
    w, h = font.size
    big = recolour(font, MASTERS, (fill, ring, ring) if light else (ring, ring, fill))
    cut = round(h * SMALL_FROM)
    if outer is not None and outer != ring:                # the second ring: the digits' outermost pixels
        k = max(1, round(w * OUTER_RING))
        top = big.crop((0, 0, w, cut))
        alpha = top.getchannel('A')
        edge = ImageChops.subtract(alpha, alpha.filter(ImageFilter.MinFilter(2 * k + 1)))
        layer = Image.composite(Image.new('RGBA', top.size, tuple(outer) + (255,)), top, edge)
        layer.putalpha(alpha)
        big.paste(layer, (0, 0))
    small = recolour(font.crop((0, cut, w, h)), MASTERS, (ring, ring, fill))
    big.paste(small, (0, cut))
    letters = recolour(font, MASTERS, (name,) * 3)
    for top, bottom, right in LETTER_ROWS:
        box = (0, round(h * top), round(w * right), round(h * bottom))
        big.paste(letters.crop(box), box[:2])
    return big


def fitted_sheet(sheet, size):
    """A pack's number sheet at the raster's size, resized with its colours weighted by alpha (no dark fringes)."""
    from PIL import Image
    sheet = sheet.convert('RGBA')
    return sheet if sheet.size == size else sheet.convert('RGBa').resize(size, Image.LANCZOS).convert('RGBA')


def _runs(alpha, box):
    """The column runs [(left, right)] of `alpha` (L) inside `box` where some pixel is over half opaque."""
    l, t, r, b = box
    runs, start = [], None
    for x in range(l, r + 1):
        on = x < r and alpha.crop((x, t, x + 1, b)).getextrema()[1] > 128
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x - 1))
            start = None
    return runs


def with_marks(sheet, chassis):
    """The pack's number sheet `sheet` with the marks it leaves out taken from the chassis' sheet `chassis` (same size): some
    sheets have no brackets, apostrophe, period or hyphen in the letter rows, so O'Reilly and St. Louis would lose theirs.
    Each chassis glyph whose cell is empty on `sheet` is painted in the colour of the sheet's letters; a cell the sheet
    fills (also a nameplate sheet's) stays as it is."""
    from PIL import Image, ImageStat
    out, mine, theirs = sheet.copy(), sheet.getchannel('A'), chassis.getchannel('A')
    w, h = sheet.size
    rows = [(round(w * left), round(h * top), round(w * right), round(h * bottom)) for left, top, right, bottom in NAME_ROWS]
    letters = Image.new('L', sheet.size, 0)
    for box in rows:
        letters.paste(mine.crop(box).point(lambda v: 255 if v > 200 else 0), box[:2])
    colour = tuple(round(v) for v in ImageStat.Stat(sheet.convert('RGB'), mask=letters).median) \
        if letters.getbbox() else (255, 255, 255)
    for box in rows:
        for x0, x1 in _runs(theirs, box):
            cell = (max(box[0], x0 - 2), box[1], min(box[2], x1 + 3), box[3])
            if mine.crop(cell).getextrema()[1] >= EMPTY_CELL:
                continue
            mark = Image.new('RGBA', (cell[2] - cell[0], cell[3] - cell[1]), colour + (0,))
            mark.putalpha(theirs.crop(cell))
            out.paste(mark, cell[:2])
    return out


def put_sheet(f, mine, sheet, chassis, base):
    """The pack's number sheet `sheet` as the rasters font_<mine>_cm / _sm / _nm of the jersey file `f` (an Rpsgl): the
    picture with the marks it lacks (with_marks), a shine map from its shape and an even relief (no stitched edges of the
    chassis' digits under the new ones), with the values of the chassis' sheet (`chassis`, an Rpsgl holding font_<base>_*)."""
    from PIL import Image, ImageStat
    cm = chassis.image(f"font_{base}_cm")
    sheet = with_marks(fitted_sheet(sheet, cm.size), cm)
    alpha = cm.getchannel('A')
    inside, outside = alpha.point(lambda v: 255 if v > 200 else 0), alpha.point(lambda v: 255 if v < 16 else 0)
    shine = chassis.image(f"font_{base}_sm").convert('L').resize(cm.size)
    lit, dull = (round(ImageStat.Stat(shine, mask=m).median[0]) for m in (inside, outside))
    relief = tuple(round(v) for v in ImageStat.Stat(chassis.image(f"font_{base}_nm").resize(cm.size), mask=outside).median)
    f.replace(f"font_{mine}_cm", sheet)
    f.replace(f"font_{mine}_sm", Image.composite(Image.new('RGBA', cm.size, (lit,) * 3 + (255,)),
                                                 Image.new('RGBA', cm.size, (dull,) * 3 + (255,)), sheet.getchannel('A')))
    f.replace(f"font_{mine}_nm", Image.new('RGBA', cm.size, relief))


def median_picture(pictures):
    """The per-pixel median of an odd number of same-sized pictures, band by band (min / max only, so it is exact and the
    same on every PC)."""
    from PIL import Image, ImageChops
    mode = pictures[0].mode
    bands = []
    for b in range(len(pictures[0].getbands())):
        column = [p.getchannel(b) for p in pictures]
        n = len(column)
        for rnd in range(n):                               # odd-even transposition sort: n rounds sort n values
            for i in range(rnd % 2, n - 1, 2):
                lo, hi = ImageChops.darker(column[i], column[i + 1]), ImageChops.lighter(column[i], column[i + 1])
                column[i], column[i + 1] = lo, hi
        bands.append(column[n // 2])
    return Image.merge(mode, bands)


# style 0's relief and shine: the median of these clubs' own (art, variant): their folds agree, their embossed crests do not
RELIEF_FROM = ((36, 0), (37, 0), (180, 0), (183, 0), (187, 0), (190, 0), (280, 0), (283, 0), (290, 0), (320, 0), (325, 0))
# the shine map's glossy spots most versions carry (crest, league patch, shoulder patches, back tag): flattened
SHINE_FLAT = ((415, 705, 625, 900), (565, 605, 675, 670), (140, 405, 270, 530), (754, 405, 884, 530), (460, 25, 564, 190))


def _corr(a, b):
    pa, pb = list(a.tobytes()), list(b.tobytes())     # one channel ('L'): a byte per pixel
    ma, mb = sum(pa) / len(pa), sum(pb) / len(pb)
    num = sum((x - ma) * (y - mb) for x, y in zip(pa, pb))
    den = math.sqrt(sum((x - ma) ** 2 for x in pa) * sum((y - mb) ** 2 for y in pb))
    return num / den if den else 0.0


def sample_palette(chassis_cm, user_cm):
    """The three colours of a player's own colour map: its mean colour where the chassis is body, yoke and trim coloured
    (the crest and shoulder marks left out). Returns (body, yoke, trim)."""
    from PIL import Image
    small = (256, 256)
    base = chassis_cm.convert('RGB').resize(small, Image.BOX)
    mine = user_cm.convert('RGB').resize(small, Image.BOX)
    skip = [tuple(c // 4 for c in box) for box in (CREST,) + SHOULDER]
    sums = [[0, 0, 0, 0] for _ in MASTERS]
    bp, mp = base.load(), mine.load()
    for y in range(small[1]):
        for x in range(small[0]):
            if any(b[0] - 3 <= x <= b[2] + 3 and b[1] - 3 <= y <= b[3] + 3 for b in skip):
                continue
            c = bp[x, y]
            k = min(range(3), key=lambda i: _dist2(c, MASTERS[i]))
            if _dist2(c, MASTERS[k]) <= 25 * 25:
                u = mp[x, y]
                sums[k][0] += 1
                for i in range(3):
                    sums[k][i + 1] += u[i]
    return tuple(tuple(round(s[i + 1] / s[0]) for i in range(3)) if s[0] else MASTERS[k] for k, s in enumerate(sums))


def kit_palette(chassis_cm, kit_cm, light):
    """The colours of an pack kit for the pants, socks and menu picture: Palette(body, yoke, trim, pants, None). Each of
    body, yoke and trim is the kit's median colour where the chassis has that colour (a mean blends the stripes the warp
    moves a little); a stripe colour (trim of a dark shirt, body of a light one) that came out as the shirt's own colour
    takes the kit's next common colour; the pants are the darkest colour that covers 4 % of the kit."""
    from PIL import Image
    small = (256, 256)
    base = chassis_cm.convert('RGB').resize(small, Image.BOX)
    mine = kit_cm.convert('RGB').resize(small, Image.BOX)
    skip = [tuple(c // 4 for c in box) for box in (CREST,) + SHOULDER]
    regions, counts, total = [[] for _ in MASTERS], {}, 0
    bp, mp = base.load(), mine.load()
    for y in range(small[1]):
        for x in range(small[0]):
            if any(b[0] - 3 <= x <= b[2] + 3 and b[1] - 3 <= y <= b[3] + 3 for b in skip):
                continue
            u = mp[x, y]
            key = (u[0] // 16, u[1] // 16, u[2] // 16)
            counts[key] = counts.get(key, 0) + 1
            total += 1
            c = bp[x, y]
            k = min(range(3), key=lambda i: _dist2(c, MASTERS[i]))
            if _dist2(c, MASTERS[k]) <= 25 * 25:
                regions[k].append(u)
    picked = []                                     # the kit's colours, most common first, each clearly another
    for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        c = tuple(v * 16 + 8 for v in key)
        if n >= total * 0.02 and all(_dist2(c, o) > 60 * 60 for o, _n in picked):
            picked.append((c, n))
    roles = [tuple(sorted(u[i] for u in got)[len(got) // 2] for i in range(3)) if got else MASTERS[k]
             for k, got in enumerate(regions)]
    main, stripe = (2, 0) if light else (0, 2)
    if _dist2(roles[stripe], roles[main]) < 48 * 48:
        roles[stripe] = next((c for c, _n in picked if _dist2(c, roles[main]) > 60 * 60), roles[stripe])
    dark = [c for c, n in picked if n >= total * 0.04] or [roles[1]]
    pants = min(dark, key=lambda c: (0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2], c))
    return Palette(roles[0], roles[1], roles[2], pants, None)


def crest_of(user_cm):
    """The crest of a colour map as a transparent picture: what differs in the crest's box from the shirt around it (the
    median colour of the box's edge; the shirt's mean colour would leave a box round the crest on a striped or shaded
    shirt)."""
    from PIL import Image, ImageChops, ImageFilter
    region = user_cm.convert('RGB').crop(CREST)
    w, h = region.size
    px = region.load()
    edge = [px[x, y] for x in range(w) for y in (0, 1, h - 2, h - 1)] + \
           [px[x, y] for y in range(2, h - 2) for x in (0, 1, w - 2, w - 1)]
    key = tuple(sorted(c[i] for c in edge)[len(edge) // 2] for i in range(3))
    diff = ImageChops.difference(region, Image.new('RGB', region.size, key)).convert('L')
    alpha = diff.point(lambda v: 0 if v < 40 else min(255, (v - 40) * 4)).filter(ImageFilter.GaussianBlur(0.6))
    out = region.convert('RGBA')
    out.putalpha(alpha)
    return out


def _full_size(img):
    """A colour map as 1024 x 1024 RGB."""
    from PIL import Image
    img = img.convert('RGB')
    return img if img.size == (1024, 1024) else img.resize((1024, 1024), Image.LANCZOS)


class Maker:
    """Makes the files of a look from the player's disc. Heavy parts are made once and kept: the chassis, the shirt mask,
    style 0's relief. `look_pack`: the program's pack pictures (art/lookpack.py), for looks with pack kits."""

    def __init__(self, disc, look_pack=None):
        self.disc = Borrow(clubart.AliasDisc(disc))     # art 900 / 901 (Coachella Valley, Henderson) are read from their donors'
                                                        # files, a version the roster gained (alternate_rows) from its `like`
        self.look_pack = look_pack
        self.chassis = Chassis(self.disc)
        self._mask = None
        self._figure = None
        self._previews = {}
        self._layout = {}
        self._relief0 = None

    def _has(self, inner):
        has = getattr(self.disc, 'has', None)
        return True if has is None else has(inner)

    def style0_relief(self):
        """(file, its name part) of a style-0 jersey whose relief and shine are the median of `RELIEF_FROM` (the clubs'
        shared folds without their embossed crests), made once; None when the disc has fewer than three of them."""
        if self._relief0 is None:
            found = []
            for art, variant in RELIEF_FROM:
                raw = self.disc.render(JERSEY.format(s=0, a=art, v=variant))
                if raw is not None:
                    found.append((rpsgl.Rpsgl(raw), f"0_{art}_{variant}"))
            if len(found) % 2 == 0:
                found = found[:-1]
            self._relief0 = False
            if len(found) >= 3:
                base, name = found[0]
                base.replace(f"jersey_{name}_0_nm", median_picture([f.image(f"jersey_{n}_0_nm") for f, n in found]))
                base.replace(f"jersey_{name}_sm",
                             flatten(median_picture([f.image(f"jersey_{n}_sm") for f, n in found]), SHINE_FLAT))
                self._relief0 = (base, name)
        return self._relief0 or None

    def chassis_cm(self, light):
        return self.chassis.jersey(light).image(f"jersey_{STYLE}_{CHASSIS_ART}_{CHASSIS[light]}_cm")

    def cut_paths(self, look, variant):
        """The files a version written in its own cut writes (an pack kit, or the player's picture in the classic cut):
        the jersey, the pants, socks and menu picture the disc has."""
        return [p for p in (t.format(s=look.style, a=look.art, v=variant) for t in (JERSEY, PANT, SOCK, PREVIEW))
                if self._has(p)]

    def _lend(self, look, kit):
        if kit.like is not None and kit.like != kit.variant:
            self.disc.lend(look.art, look.style, kit.variant, kit.like)

    def borrowed_paths(self, look, kit):
        """The files of a kit's version the disc lacks and copies from its `like` version: the name sheet, the logo on the
        helmet and the like (BORROWED); the jersey, pants, socks and menu picture are the kit's own paints."""
        self._lend(look, kit)
        return [p for p in (t.format(s=look.style, a=look.art, v=kit.variant) for t in BORROWED) if p in self.disc.lent]

    def pack_paths(self, look, kit):
        """The files one pack kit writes: the jersey, the pants, socks and menu picture, and what a version new to the
        roster copies from another."""
        self._lend(look, kit)
        return self.cut_paths(look, kit.variant) + self.borrowed_paths(look, kit)

    def pack_files(self, look, kit):
        """{path: bytes} of one version in the pack's kit (see the module's text)."""
        self._lend(look, kit)
        out = self._painted_files(look, kit)
        for path in self.borrowed_paths(look, kit):
            raw = self.disc.render(path)
            if raw is not None:
                out[path] = raw
        return out

    def _painted_files(self, look, kit):
        light = kit.light
        mine = _full_size(self.look_pack.picture(kit.member))
        palette = kit_palette(self.chassis_cm(light), mine, light)
        if kit.numbers and kit.scheme:
            palette = palette._replace(font=Numbers(kit.numbers[0], *kit.scheme))
        else:
            palette = palette._replace(font=number_roles(*kit.numbers, light) if kit.numbers
                                       else (palette.yoke, palette.yoke, palette.trim))
        # the menu picture is the pack's own (pack_preview), in both cuts; the number sheet too where the pack has one
        sheet = self.look_pack.picture(kit.font.rpartition('#')[0]) if kit.font else None
        sock = self.look_pack.picture(kit.sock.rpartition('#')[0]) if kit.sock else None
        return self.cut_files(look, kit.variant, light, mine, palette, kit.numbers,
                              lambda raw: self.pack_preview(raw, kit, light, palette, mine), sheet, sock, kit.pants)

    def cut_files(self, look, variant, light, mine, palette, numbers, preview, sheet=None, sock=None, pants=None):
        """{path: bytes} of one version with the colour map `mine` (1024 x 1024 RGB) in the team's cut: style 1 on the
        chassis' relief and number sheet, the classic cut in the version's own file with a clean relief and its own number
        sheet (recoloured to `numbers` (fill, outline) when given). A pack kit's own number sheet `sheet` replaces either
        (both cuts lay their glyphs out alike). Pants and socks have one layout in both cuts: the chassis' in `palette`, or
        a pack kit's own sock picture `sock` (shaded like the chassis') and pants colours `pants` (main, stripe);
        `preview(raw)` makes the menu picture from the disc's."""
        art, style = look.art, look.style
        inner = JERSEY.format(s=style, a=art, v=variant)
        raw = self.disc.render(inner)
        if raw is None:
            return {}
        if style != STYLE:                          # the classic cut: the version's own file, a clean relief, own numbers
            f = rpsgl.Rpsgl(raw)
            name = f"{style}_{art}_{variant}"
            if f"jersey_{name}_cm" not in f.rasters:
                return {}
            f.replace(f"jersey_{name}_cm", mine)
            relief = self.style0_relief() if style == 0 else None
            if relief is not None:
                src, base = relief
                for part in ('0_nm', 'sm'):
                    if f"jersey_{name}_{part}" in f.rasters:
                        f.copy(f"jersey_{name}_{part}", src, f"jersey_{base}_{part}")
            if sheet is not None and f"font_{name}_cm" in f.rasters:
                put_sheet(f, name, sheet, self.chassis.jersey(light), f"{STYLE}_{CHASSIS_ART}_{CHASSIS[light]}")
            elif numbers and f"font_{name}_cm" in f.rasters:
                name_colour = palette.font.name if isinstance(palette.font, Numbers) else None
                f.replace(f"font_{name}_cm", recolour_sheet(f.image(f"font_{name}_cm"), *numbers, name=name_colour))
            out = {inner: f.build()}
        else:
            out = {inner: jersey_file(raw, art, variant, self.chassis, light, palette, None, colour_map=mine, sheet=sheet)}
        for path_t, make, own in ((PANT, pant_file, pants), (SOCK, sock_file, sock)):
            inner = path_t.format(s=style, a=art, v=variant)
            raw = self.disc.render(inner)
            if raw is not None:
                out[inner] = make(raw, art, variant, self.chassis, light, palette, style, own)
        inner = PREVIEW.format(s=style, a=art, v=variant)
        raw = self.disc.find(inner)
        if raw is not None:
            out[inner] = preview(raw)
        return out

    def pack_preview(self, raw, kit, light, palette, colour_map):
        """The Select Jerseys picture (bytes of the version's .big `raw`) of a pack kit: the pack's own menu picture of the kit
        on the game's figure (menu_picture), or, for a kit the pack has none for, the chassis' picture in the kit's colours
        with the crest of its colour map."""
        from . import install
        member = (kit.menu or '').split('#')[0]
        if member and self.look_pack.has(member):
            return install.art_file(raw, self.menu_preview(self.look_pack.picture(member)))
        return preview_file(self.preview_of_chassis(light), self.mask(), palette, crest_of(colour_map), raw)

    def menu_preview(self, kit_menu):
        """the pack's menu picture of a kit on the game's figure (menu_picture; the figure is made once)."""
        if self._figure is None:
            self._figure = menu_figure(self.preview_of_chassis(False), self.mask())
        return menu_picture(self.preview_of_chassis(False), self.mask(), kit_menu, self._figure)

    def preview_of_chassis(self, light):
        if light not in self._previews:
            self._previews[light] = preview_picture(self.disc.find(PREVIEW.format(s=STYLE, a=CHASSIS_ART, v=CHASSIS[light])))
        return self._previews[light]

    def mask(self):
        if self._mask is None:
            self._mask = shirt_mask(self.disc, [self.preview_of_chassis(False), self.preview_of_chassis(True)])
        return self._mask

    def _relief(self, f):
        from PIL import Image
        key = next((k for k in f.rasters if k.startswith('jersey') and k.endswith('_nm')), None)
        return None if key is None else f.image(key).getchannel('A').resize((128, 128), Image.BOX)

    def standard(self, art, variant, style=STYLE):
        """Is this version painted on the shared shirt layout (its relief map agrees with the chassis' by 90 %)? Never in
        the classic cut (style 0)."""
        if style != STYLE:
            return False
        key = (art, variant)
        if key not in self._layout:
            raw = self.disc.render(JERSEY.format(s=STYLE, a=art, v=variant))
            ok = False
            if raw is not None:
                mine = self._relief(rpsgl.Rpsgl(raw))
                ref = self._relief(self.chassis.jersey(False))
                ok = mine is not None and _corr(mine, ref) > 0.9
            self._layout[key] = ok
        return self._layout[key]

    def thumbnail(self, art, variant, light, kind, logo=None, colours=None, picture=None, menu=None, style=STYLE):
        """A small picture of what a version will look like: 'game' the disc's own menu picture, 'colours' made from
        `colours` ((primary, secondary)) and `logo`, 'file' made from the player's own colour map `picture`; with `menu`
        (the pack's own menu picture of a pack kit, kind PACK or 'file') the picture the install makes from it. `style`:
        the team's cut."""
        if menu is not None:
            return self.menu_preview(menu)
        if kind == 'game' or (kind == 'file' and not self.standard(art, variant, style)):
            if kind == 'file':
                return picture.convert('RGB').resize((256, 256))
            raw = self.disc.find(PREVIEW.format(s=style, a=art, v=variant))
            return None if raw is None else preview_picture(raw)
        if kind == 'colours':
            kit = kit_for(*colours)
            return preview_image(self.preview_of_chassis(light), self.mask(), kit.away if light else kit.home, logo)
        chassis_cm = self.chassis.jersey(light).image(f"jersey_{STYLE}_{CHASSIS_ART}_{CHASSIS[light]}_cm")
        body, yoke, trim = sample_palette(chassis_cm, picture)
        return preview_image(self.preview_of_chassis(light), self.mask(), Palette(body, yoke, trim, yoke, (yoke,) * 2 + (trim,)),
                             crest_of(picture))

    def own_colour_map(self, art, variant, style=STYLE):
        """The disc's own colour map of a version (1024 x 1024) in the team's cut, the starting point to paint on."""
        raw = self.disc.render(JERSEY.format(s=style, a=art, v=variant))
        return None if raw is None else rpsgl.Rpsgl(raw).image(f"jersey_{style}_{art}_{variant}_cm")

    def own_centre(self, art):
        raw = self.disc.render(CENTRE.format(a=art))
        return None if raw is None else rpsgl.Rpsgl(raw).image(f"centerlogo_{art}_cm")

    def paths(self, look):
        """Every file path a look writes (inside the game's USRDIR)."""
        out = []
        for variant, _light in look.versions:
            out += [t.format(s=STYLE, a=look.art, v=variant) for t in (JERSEY, PANT, SOCK, PREVIEW, DECAL)]
        for variant, _light, _path in look.files:
            if look.style != STYLE:
                out += self.cut_paths(look, variant)
                continue
            out.append(JERSEY.format(s=STYLE, a=look.art, v=variant))
            if self.standard(look.art, variant):
                out += [t.format(s=STYLE, a=look.art, v=variant) for t in (PANT, SOCK, PREVIEW)]
        for kit in look.pack:
            out += self.pack_paths(look, kit)
        if _makes_centre(look):
            out += [p for p in (CENTRE.format(a=look.art),) if self._has(p)]   # the national teams' arenas have none
        if _ice_picture_wanted(look):
            out.append(ICE_PICTURE.format(a=look.art))
        out += [p for p in clubart.extra_paths(look.art) if self._has(p)]
        return out

    def files(self, look):
        """{path inside the game folder's USRDIR: bytes} for one team's look: every version's jersey, pants, socks and menu
        picture, and the centre-ice logo."""
        from PIL import Image
        out = {}
        art = look.art
        for variant, light in look.versions:
            palette = look.kit.away if light else look.kit.home
            logo = look.logos[1] if light else look.logos[0]
            for path, make in ((JERSEY, lambda raw: jersey_file(raw, art, variant, self.chassis, light, palette, logo)),
                               (PANT, lambda raw: pant_file(raw, art, variant, self.chassis, light, palette)),
                               (SOCK, lambda raw: sock_file(raw, art, variant, self.chassis, light, palette))):
                inner = path.format(s=STYLE, a=art, v=variant)
                raw = self.disc.render(inner)
                if raw is not None:
                    out[inner] = make(raw)
            inner = PREVIEW.format(s=STYLE, a=art, v=variant)
            raw = self.disc.find(inner)
            if raw is not None:
                out[inner] = preview_file(self.preview_of_chassis(light), self.mask(), palette, logo, raw)
            inner = DECAL.format(s=STYLE, a=art, v=variant)
            raw = self.disc.render(inner)
            if raw is not None:
                out[inner] = decal_file(raw, art, variant, look.logos[0])
        for variant, light, path in look.files:
            mine = Image.open(path)
            mine.load()
            mine = _full_size(mine)
            if look.style != STYLE:                 # the classic cut: as the pack's kits go (cut_files), in the picture's colours
                palette = kit_palette(self.chassis_cm(light), mine, light)
                palette = palette._replace(font=(palette.yoke, palette.yoke, palette.trim))
                out.update(self.cut_files(look, variant, light, mine, palette, None,
                                          lambda raw, palette=palette, mine=mine: preview_file(
                                              self.preview_of_chassis(light), self.mask(), palette, crest_of(mine), raw)))
                continue
            inner = JERSEY.format(s=STYLE, a=art, v=variant)
            raw = self.disc.render(inner)
            if raw is None:
                continue
            if not self.standard(art, variant):                       # another shirt: only the colour map is theirs
                f = rpsgl.Rpsgl(raw)
                f.replace(f"jersey_{STYLE}_{art}_{variant}_cm", mine)
                out[inner] = f.build()
                continue
            chassis_cm = self.chassis.jersey(light).image(f"jersey_{STYLE}_{CHASSIS_ART}_{CHASSIS[light]}_cm")
            body, yoke, trim = sample_palette(chassis_cm, mine)
            palette = Palette(body, yoke, trim, yoke, (yoke, yoke, trim))
            out[inner] = jersey_file(raw, art, variant, self.chassis, light, palette, None, colour_map=mine)
            for path_t, make in ((PANT, lambda raw: pant_file(raw, art, variant, self.chassis, light, palette)),
                                 (SOCK, lambda raw: sock_file(raw, art, variant, self.chassis, light, palette))):
                inner = path_t.format(s=STYLE, a=art, v=variant)
                raw = self.disc.render(inner)
                if raw is not None:
                    out[inner] = make(raw)
            inner = PREVIEW.format(s=STYLE, a=art, v=variant)
            raw = self.disc.find(inner)
            if raw is not None:
                out[inner] = preview_file(self.preview_of_chassis(light), self.mask(), palette, crest_of(mine), raw)
        for kit in look.pack:
            out.update(self.pack_files(look, kit))
        if _ice_picture_wanted(look):
            raw = self.disc.render(ICE_PICTURE.format(a=art))
            if raw is not None:
                out[ICE_PICTURE.format(a=art)] = ice_picture_file(raw, art, look.logos[1])
        if _makes_centre(look):
            inner = CENTRE.format(a=art)
            raw = self.disc.render(inner)
            if raw is not None:
                picture = None
                if look.centre.startswith('pack:'):
                    picture = self.look_pack.picture(look.centre[5:].split('#')[0])
                elif look.centre != 'make':
                    picture = Image.open(look.centre)
                    picture.load()
                    picture = picture.convert('RGBA').resize((1024, 1024), Image.LANCZOS) if picture.size != (1024, 1024) \
                        else picture.convert('RGBA')
                out[inner] = centre_file(raw, art, look.logos[1], look.arena, look.ice_colour, picture)
        if art in clubart.ARTS:                     # Coachella Valley, Henderson: what is not painted is the donor's
            out.update(clubart.extra_files(self.disc, art))
        return out


def jersey_file(raw, art, variant, chassis, light, palette, logo, colour_map=None, sheet=None):
    """The team's own jersey file (`raw`: the disc's bytes) with the chassis' look in the team's colours (or the player's own
    colour map `colour_map`, 1024 x 1024, on the chassis' relief and number sheet; a pack kit's own number sheet `sheet`
    when it has one)."""
    f = rpsgl.Rpsgl(raw)
    src, v = chassis.jersey(light), CHASSIS[light]
    base, mine = f"{STYLE}_{CHASSIS_ART}_{v}", f"{STYLE}_{art}_{variant}"
    f.replace(f"jersey_{mine}_cm", colour_map if colour_map is not None
              else jersey_colour(src.image(f"jersey_{base}_cm"), palette, logo))
    # the shine map carries the old crest too (a glossy coyote head under the new logo): flattened like the relief
    f.replace(f"jersey_{mine}_sm", flatten(src.image(f"jersey_{base}_sm"), NORMAL_FLAT))
    f.replace(f"jersey_{mine}_0_nm", flatten(src.image(f"jersey_{base}_0_nm"), NORMAL_FLAT))
    if sheet is not None:
        put_sheet(f, mine, sheet, src, base)
        return f.build()
    font = src.image(f"font_{base}_cm")
    f.replace(f"font_{mine}_cm", recolour_numbers(font, light, *palette.font) if isinstance(palette.font, Numbers)
              else recolour(font, MASTERS, palette.font))
    f.copy(f"font_{mine}_nm", src, f"font_{base}_nm")
    f.copy(f"font_{mine}_sm", src, f"font_{base}_sm")
    return f.build()


def pant_file(raw, art, variant, chassis, light, palette, style=STYLE, colours=None):
    """The version's pants: the chassis' in `colours` (main, stripe: a pack kit's own) or in the palette's pants and trim."""
    f = rpsgl.Rpsgl(raw)
    src, v = chassis.pant(light), CHASSIS[light]
    base, mine = f"pant_{STYLE}_{CHASSIS_ART}_{v}", f"pant_{style}_{art}_{variant}"
    pair = tuple(tuple(c) for c in colours) if colours else (palette.pants, palette.trim)
    f.replace(f"{mine}_cm", recolour(src.image(f"{base}_cm"), PANT_MASTERS, pair))
    f.copy(f"{mine}_nm", src, f"{base}_nm")
    f.copy(f"{mine}_sm", src, f"{base}_sm")
    return f.build()


def sock_file(raw, art, variant, chassis, light, palette, style=STYLE, picture=None):
    """The version's sock: a pack kit's own `picture` (the game's layout, 1024 x 512) with the chassis' garter and skate
    shading laid over (`sock_shade`), else the chassis' recoloured to the palette."""
    f = rpsgl.Rpsgl(raw)
    if picture is not None:
        f.replace(f"sock_{style}_{art}_{variant}_cm", shaded_sock(picture, chassis.shade(light)))
    else:
        base = chassis.sock(light).image(f"sock_{STYLE}_{CHASSIS_ART}_{CHASSIS[light]}_cm")
        f.replace(f"sock_{style}_{art}_{variant}_cm", recolour(base, MASTERS, (palette.body, palette.yoke, palette.trim)))
    return f.build()


SOCK_SHADE = (0.7, 1.1)            # the chassis' shading kept within these factors (its stripe edges reach 6x their row)


def sock_shade(base):
    """The chassis sock's shading as an L picture, 255 = SOCK_SHADE[1]: each pixel's grey against its row's median grey
    (the stripes run the full width, so what is left is the garter, the folds and the skate's shadow)."""
    from PIL import Image
    grey = base.convert('L')
    w, h = grey.size
    data = grey.tobytes()
    lo, hi = SOCK_SHADE
    out = bytearray(w * h)
    for y in range(h):
        row = data[y * w:(y + 1) * w]
        median = sorted(row)[w // 2] + 1
        for x, value in enumerate(row):
            out[y * w + x] = round(min(hi, max(lo, (value + 1) / median)) / hi * 255)
    return Image.frombytes('L', (w, h), bytes(out))


def shaded_sock(picture, shade):
    """A pack sock `picture` at the size of the chassis sock's shading `shade` (`sock_shade`), with the shading multiplied in."""
    from PIL import Image, ImageChops
    picture = picture.convert('RGB')
    if picture.size != shade.size:
        picture = picture.resize(shade.size, Image.LANCZOS)
    lift = [min(255, round(v * SOCK_SHADE[1])) for v in range(256)]
    return ImageChops.multiply(picture, Image.merge('RGB', (shade,) * 3)).point(lift * 3)


# --- choosing and installing the looks -------------------------------------------------------------------------------
LOOKS_DRAWING = '#8'               # a change in how the pictures are drawn redraws every installed look once
# '#8' (2026-10-27): the pack's own number sheets (put_sheet), rings carved inside the glyphs (recolour_numbers), Utah's /
# Seattle's / Vegas's other versions in the pack's kit
# '#4' (2026-10-18): the pack's own menu pictures for the pack kits; '#5': the DXT5 blocks and alpha-weighted mips of
# art/dds.py (dds.mipmaps, Rpsgl.replace(coverage=)), docs/notes/centre-ice-quality.md; '#6': the centre ice flattened
# onto the ice's white, opaque or clear (dds.flatten; lab round 32)
NEW_TEAMS = {22: 'UTA', 30: 'SEA', 31: 'VGK'}        # slot -> NHL.com code (the logo)
# the versions that use the shared layout, with the roster's own flag for a light jersey (`stockteamjerseys`: the same in
# the game's own roster and the community's): Utah style 1 v0 v3 dark, v1 v4 light; Seattle v3 v4 dark, v2 v5 light;
# Vegas v2 v4 dark, v3 v5 light
DEFAULT_VERSIONS = {22: ((0, False), (1, True), (3, False), (4, True)),
                    30: ((2, True), (3, False), (4, False), (5, True)),
                    31: ((2, False), (3, True), (4, False), (5, True))}


def team_logo(url, pack=None, cache=None):
    """A club's logo from the picture cache, the program's photo pack or the web (kept in the cache), trimmed."""
    from . import images, install
    img = (cache.logo(url) if cache else None) or (pack.logo(url) if pack else None)
    if img is None:
        img = install._download(url).convert('RGBA')
        if cache:
            cache.put_logo(url, images._trim(img))
    return images._trim(img)


def default_looks(nhl_logos, pack=None, cache=None):
    """The three looks of Utah, Seattle and Vegas (colours and arena names are the community roster's:
    `builder.NHL_LOOK`); `nhl_logos` is the data pack's {NHL.com code: logo link}."""
    from .. import builder
    from . import install
    out = []
    for slot, code in sorted(NEW_TEAMS.items()):
        arena, _city, primary, secondary = builder.NHL_LOOK[slot]
        dark = nhl_logos[code]
        out.append(Look(slot, kit_for(primary, secondary),
                        (team_logo(dark, pack, cache), team_logo(install.plain_logo_url(dark), pack, cache)),
                        arena, secondary, DEFAULT_VERSIONS[slot]))
    return out


def parse_colour(text, fallback):
    """'#rrggbb' (or 'rrggbb') as (r, g, b); the fallback when it is not one."""
    t = (text or '').strip().lstrip('#')
    try:
        return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)) if len(t) == 6 else tuple(fallback)
    except ValueError:
        return tuple(fallback)


def window_team(R, slot):
    """(the slot whose Jerseys and ice window opens when the player picks slot `slot`, why none opens or None): a
    custom team its own (its create-a-team look, custom_kit.py), a team wearing another team's jerseys (the Winter
    Classic teams, EASHL 2) that team's, else its own where `editable`."""
    from .. import custom_kit
    if custom_kit.is_custom(slot) and slot < R.T.cur_rec:
        return slot, None
    why = editable(R, slot)
    if why and isinstance(slot, int) and 0 <= slot < R.T.cur_rec:
        owner = jersey_owner(R, slot)
        if owner != slot and editable(R, owner) is None:
            return owner, None
    return slot, why


def team_colours(R, slot):
    """A team's two colours as the roster has them: (primary, secondary)."""
    T = R.T
    return tuple(tuple(T.get(slot, f"{kind}color_{c}") for c in 'rgb') for kind in ('primary', 'secondary'))


def team_arena(R, slot):
    try:
        return R.f['OEtS'].get(R.T.get(slot, 'arenaid'), 'arenaname')
    except (KeyError, IndexError):
        return ""


def shown_centre(R, slot):
    """The art id of the centre-ice file the game shows at slot `slot`'s home games (ARENA_ICE_LEAGUES)."""
    T = R.T
    league = T.get(slot, 'league')
    if league == NATIONAL_LEAGUE:
        return NATIONAL_ICE
    if league in ARENA_ICE_LEAGUES:
        try:
            return R.f['OEtS'].get(T.get(slot, 'arenaid'), 'arenaartid')
        except (KeyError, IndexError):
            pass
    return T.get(slot, 'artid')


def centre_owners(R):
    """{art id of a centre-ice file: how many teams' home games show it} for every team of roster `R`."""
    owners = {}
    for slot in range(R.T.cur_rec):
        art = shown_centre(R, slot)
        owners[art] = owners.get(art, 0) + 1
    return owners


def ice_group(R, slot):
    """(art id of the centre-ice file, [slots]) when slot `slot`'s home games show a centre ice that other teams' home
    games show too and none of them is an NHL team: the national teams (501), the DEL's clubs (their arena's 197), EASHL
    1 and 2 (255). The player's own picture goes onto that file for all of them (owner, 2026-10-20). None otherwise."""
    if not isinstance(slot, int) or not 0 <= slot < R.T.cur_rec or slot in NHL:
        return None
    shown = shown_centre(R, slot)
    members = [s for s in range(R.T.cur_rec) if shown_centre(R, s) == shown]
    if len(members) < 2 and R.T.get(slot, 'league') != NATIONAL_LEAGUE or any(s in NHL for s in members):
        return None
    return shown, members


def ice_note(R, slot):
    """The window's note on a shared centre ice (ice_group), or None."""
    group = ice_group(R, slot)
    if group is None:
        return None
    league = R.T.get(slot, 'league')
    if league == NATIONAL_LEAGUE:
        return "All national teams play on this ice: a change shows at every national team's home games."
    if league == 4:
        return "All DEL clubs play on this ice: a change shows at every DEL club's home games."
    names = [R.team_name(s) for s in group[1]]
    return f"{', '.join(names[:-1])} and {names[-1]} play on this ice: a change shows at all their home games."


def own_ice(R, slot, owners):
    """Why a new centre ice of a club outside the NHL (slot `slot`: the pack's or the player's own) would not show at its
    home games, or None when it would: the game shows another file there, or one that other teams' home games show too
    (`owners`, centre_owners). A picture of the player's own on a shared ice goes to the group's file instead
    (ice_group, looks_from)."""
    shown = shown_centre(R, slot)
    if R.T.get(slot, 'league') == NATIONAL_LEAGUE:
        return "the national teams all play on the game's international centre ice"
    if owners.get(shown, 0) > 1:
        return "its home games show a centre ice that other teams' home games show too"
    if shown != R.T.get(slot, 'artid'):
        return "its home games show its arena's centre ice"
    return None


def _ink(colour):
    """A colour for the arena's name that can be read on ice-white."""
    return colour if 0.3 * colour[0] + 0.59 * colour[1] + 0.11 * colour[2] < 150 else (32, 32, 32)


PackTeam = namedtuple('PackTeam', 'art style kits centre why')
# a team of the look pack in the player's roster: its art id and cut, {variant: PackKit}, the centre ice ('pack:...' or
# None) and why it is left out (None when it is not)
PLAIN_KIT = Kit(Palette(*(((0, 0, 0),) * 4), ((0, 0, 0),) * 3), Palette(*(((0, 0, 0),) * 4), ((0, 0, 0),) * 3))


def pack_team(R, slot, look_pack):
    """What the look pack has for slot `slot` of roster `R` (a PackTeam), or None when it has nothing for it."""
    team = (look_pack.teams if look_pack is not None else {}).get(slot)
    if team is None:
        return None
    art = R.T.get(slot, 'artid')
    if not look_pack.holds(slot, R):
        return PackTeam(art, None, {}, None, f"the team in its place is not {team.get('name')} (its league was left out "
                                              "of the update?)")
    style = art_style(R, art)
    if style != team.get('style'):
        return PackTeam(art, style, {}, None, "its jerseys in the roster are cut another way")
    places = pack_versions(R, art, style)
    kits = {}
    for role, entry in sorted((team.get('kits') or {}).items()):
        member = look_pack.jersey_member(slot, role)
        if role in places and look_pack.has(member):
            variant, light = places[role]
            numbers = tuple(tuple(c) for c in entry['numbers']) if entry.get('numbers') else None
            scheme = (tuple(entry['ring']), tuple(entry['outer']) if entry.get('outer') else None,
                      tuple(entry['name'])) if numbers and entry.get('ring') and entry.get('name') else None
            menu, font = look_pack.menu_member(slot, role), look_pack.font_member(slot, role)
            sock = look_pack.sock_member(slot, role)
            pants = entry.get('pants')
            kits[variant] = PackKit(variant, light, member, numbers, look_pack.crc(member),
                                    f"{menu}#{look_pack.crc(menu)}" if look_pack.has(menu) else None, scheme,
                                    f"{font}#{look_pack.crc(font)}" if look_pack.has(font) else None,
                                    like=away_variant(R, art, style) if role == 'third' else None,
                                    sock=f"{sock}#{look_pack.crc(sock)}" if look_pack.has(sock) else None,
                                    pants=tuple(tuple(c) for c in pants[:2]) if pants and len(pants) >= 2 else None)
    # Utah's, Seattle's and Vegas's other home and away versions would be made from the colours (default_use): they wear the
    # pack's kit of the same lightness, so the game shows this season's whichever of them it picks (Play Now took Utah's
    # variant 0, 2026-10-27)
    listed = {(v, light) for v, light, _d in roster_versions(R, art, style)}
    home_away = {v for role, (v, _l) in places.items() if role != 'third'}
    by_light = {k.light: k for _v, k in sorted(kits.items(), reverse=True) if _v in home_away}      # never the alternate
    for variant, light in DEFAULT_VERSIONS.get(slot, ()) if style == STYLE else ():
        if variant not in kits and light in by_light and (variant, light) in listed:
            kits[variant] = by_light[light]._replace(variant=variant)
    member = look_pack.ice_member(slot)
    centre = f"pack:{member}#{look_pack.crc(member)}" if team.get('ice') and look_pack.has(member) else None
    why = None if kits or centre else "the roster lists none of its jerseys"
    return PackTeam(art, style, kits, centre, why)


def default_use(slot, variant, light, kits):
    """What a version of an NHL team becomes when the player chose nothing: the pack's kit when the look pack has one for it
    (`kits` {variant: PackKit}), else made from the colours (Utah, Seattle, Vegas), else the game's own."""
    if variant in kits:
        return PACK
    return 'colours' if (variant, light) in DEFAULT_VERSIONS.get(slot, ()) else 'game'


def default_ice(slot, centre):
    """The centre ice of an NHL team when the player chose nothing: the pack's (`centre` not None), else drawn from the logo
    (Utah, Seattle, Vegas), else the game's own."""
    return PACK if centre else 'logo' if slot in NEW_TEAMS else 'game'


def _choose(slot, versions_listed, choice, kits, style=STYLE, drawn=True):
    """(versions made from the colours, the player's pictures, the pack's kits) of a team's versions: the player's choice
    `choice` {variant: use} or what the update does by itself (default_use). 'colours' needs the shared layout's cut and
    a logo where the look is one of Utah's, Seattle's, Vegas's (`drawn`)."""
    versions, files, packed = [], [], []
    for variant, light, _d in versions_listed:
        use = choice.get(str(variant)) or default_use(slot, variant, light, kits)
        if use == PACK and variant not in kits:          # no pack in this program: as if the player chose nothing
            use = default_use(slot, variant, light, {})
        if use == PACK:
            packed.append(kits[variant])
        elif use == 'colours' and drawn and style == STYLE:
            versions.append((variant, light))
        elif use.startswith('file:'):
            files.append((variant, light, use[5:]))
    return versions, files, packed


def _centre(slot, ice, pack_centre):
    """The centre ice a team's look gets: 'make', 'game', the pack's ('pack:...') or the player's picture (a path)."""
    use = ice.get('use') or default_ice(slot, pack_centre)
    if use == PACK and not pack_centre:
        use = default_ice(slot, None)
    return 'make' if use == 'logo' else 'game' if use == 'game' else pack_centre if use == PACK else use[5:]


def _logos(link, pack, cache):
    from . import install
    return team_logo(link, pack, cache), team_logo(install.plain_logo_url(link), pack, cache)


def _nhl_look(R, slot, team, e, logo_links, nhl_logos, pack, cache):
    """The look of NHL team `slot` (every version the window offers; Utah, Seattle and Vegas made from the colours)."""
    from .. import builder
    kits = team.kits if team is not None else {}
    pack_centre = team.centre if team is not None else None
    mine, ice = e.get('uniforms') or {}, e.get('ice') or {}
    default = slot in NEW_TEAMS
    primary, secondary = builder.NHL_COLOURS[slot]          # what an update writes (the roster may be older)
    arena = builder.NHL_ARENAS[slot]
    c = mine.get('colours') or {}
    primary, secondary = parse_colour(c.get('primary'), primary), parse_colour(c.get('secondary'), secondary)
    arena = ice.get('arena') or arena
    link = c.get('crest') or logo_links.get(slot) or (nhl_logos or {}).get(NEW_TEAMS.get(slot, ''))
    drawn = True                                # can versions be made from the colours (is there a logo)?
    if link is None and default:
        drawn = False
    logos = (None, None)
    if link:
        try:
            logos = _logos(link, pack, cache)
        except Exception:
            if default:
                drawn = False
    if not drawn and not kits and not pack_centre:
        return None
    versions, files, packed = _choose(slot, team_versions(R, slot), mine.get('versions') or {}, kits,
                                      drawn=drawn or not default)
    centre = _centre(slot, ice, pack_centre)
    if centre == 'make' and not drawn:
        centre = 'game'
    if not versions and not files and not packed and centre == 'game':
        return None
    return Look(slot, kit_for(primary, secondary), logos, arena, _ink(secondary), tuple(versions), tuple(files), centre,
                tuple(packed), STYLE)


def _club_look(R, slot, team, e, logo_links, pack, cache, owners, no_ice, shared=None):
    """The look of a team outside the NHL the player chose jerseys or ice for (its home and away versions, its cut). The
    player's own picture on a shared centre ice (ice_group) goes into `shared` {art id: (slot, picture)} instead: the
    lowest slot of a group that set one wins."""
    art, style = team_art(R, slot)
    usable = team is not None and not team.why
    kits = team.kits if usable else {}
    pack_centre = team.centre if usable else None
    mine, ice = e.get('uniforms') or {}, e.get('ice') or {}
    c = mine.get('colours') or {}
    primary, secondary = team_colours(R, slot)
    primary, secondary = parse_colour(c.get('primary'), primary), parse_colour(c.get('secondary'), secondary)
    arena = ice.get('arena') or team_arena(R, slot)
    versions, files, packed = _choose(slot, team_versions(R, slot), mine.get('versions') or {}, kits, style)
    centre = _centre(slot, ice, pack_centre)
    group = ice_group(R, slot) if centre != 'game' else None
    why = None
    if group and centre not in ('make', pack_centre) and shared is not None:
        if group[0] in shared:
            why = f"{R.team_name(shared[group[0]][0])} set this shared ice already"
        else:
            shared[group[0]] = (slot, centre)
        centre = 'game'
    elif group and centre == 'make':
        why = "a centre ice shared with other teams takes only a picture of your own"
    elif centre != 'game':
        why = own_ice(R, slot, owners)
    if why:
        centre = 'game'
        if no_ice is not None:
            no_ice.append((slot, why))
    logos = (None, None)
    link = c.get('crest') or logo_links.get(slot)
    if link and (versions or centre == 'make'):     # a logo only where something is drawn with it
        try:
            logos = _logos(link, pack, cache)
        except Exception:
            pass
    if not versions and not files and not packed and centre == 'game':
        return None
    return Look(art, kit_for(primary, secondary), logos, arena, _ink(secondary), tuple(versions), tuple(files), centre,
                tuple(packed), style)


def _pack_look(R, slot, team, owners, no_ice):
    """The look of a team outside the NHL the player left alone: the pack's home and away kits and centre ice."""
    centre = team.centre or 'game'
    why = own_ice(R, slot, owners) if team.centre else None
    if why:
        centre = 'game'
        if no_ice is not None:
            no_ice.append((slot, why))
    if not team.kits and centre == 'game':
        return None
    return Look(team.art, PLAIN_KIT, (None, None), '', (32, 32, 32), (), (), centre,
                tuple(kit for _v, kit in sorted(team.kits.items())), team.style)


def with_club_defaults(R, slot, e, team, logo_links):
    """The edits of Coachella Valley / Henderson (art 900 / 901) with what the update does by itself when the player chose
    nothing: their jerseys made from the colours of the team table and the crest, and a centre ice drawn from the crest.
    The look pack's kits and centre ice win where it has them."""
    kits = team.kits if team is not None and not team.why else {}
    centre = team.centre if team is not None and not team.why else None
    mine, ice = dict(e.get('uniforms') or {}), dict(e.get('ice') or {})
    choice = dict(mine.get('versions') or {})
    colours = dict(mine.get('colours') or {})
    if not colours.get('primary') and not colours.get('secondary'):
        # the dark jersey is the second colour all over (kit_for): the team's main colour goes second
        main, trim = L.OWN_COLOURS[slot]
        colours.update(primary='#%02x%02x%02x' % tuple(trim), secondary='#%02x%02x%02x' % tuple(main))
    mine['colours'] = colours
    if logo_links.get(slot) or (mine.get('colours') or {}).get('crest'):
        for variant, _light, _d in team_versions(R, slot):
            if variant not in kits:
                choice.setdefault(str(variant), 'colours')
        if not centre:
            ice.setdefault('use', 'logo')
    mine['versions'] = choice
    return dict(e, uniforms=mine, ice=ice)


def looks_from(R, edits_by_slot, logo_links, nhl_logos, pack=None, cache=None, look_pack=None, skipped=None, no_ice=None,
               only=None):
    """The looks to install: Utah, Seattle and Vegas as the update makes them, every team of any league the player gave a
    look in the Roster editor (edits.json 'uniforms' / 'ice', see edits.py; only where `editable`) and every team the
    look pack `look_pack` (this season's jerseys, art/lookpack.py) has. `R` is the new roster; `logo_links` {slot: logo link}.
    A version the player left alone gets the pack's kit when there is one, else stays the game's own (Utah, Seattle, Vegas:
    made from the colours). A team of the pack that cannot have its kits goes into `skipped` as (slot, why); a club
    outside the NHL whose new centre ice the game would not show at its home games (own_ice) keeps the game's own and goes
    into `no_ice` as (slot, why). The player's own picture on a centre ice several teams share (ice_group: the national
    teams, the DEL, EASHL) is a look of its own at that file's art id, with nothing but the ice. `only`: the slots to make
    (the Roster editor's Save: the teams the player gave a look), None: every one."""
    out, shared = [], {}
    in_pack = set(look_pack.teams) if look_pack is not None else set()
    edited = {s for s in edits_by_slot if editable(R, s) is None}
    clubs = set(clubart.slots(R))               # Coachella Valley, Henderson on a roster for the patched game
    owners = centre_owners(R) if any(s not in NHL for s in in_pack | edited | clubs) else {}
    for slot in sorted(set(NEW_TEAMS) | {s for s in edited | in_pack if s in NHL}) + \
            sorted(s for s in edited | in_pack | clubs if s not in NHL):
        if only is not None and slot not in only:
            continue
        team = pack_team(R, slot, look_pack)
        if team is not None and team.why and skipped is not None:
            skipped.append((slot, team.why))
        e = edits_by_slot.get(slot) or {} if slot in edited else {}
        if slot in NHL:
            look = _nhl_look(R, slot, team, e, logo_links, nhl_logos, pack, cache)
        elif e or slot in clubs:
            if slot in clubs:
                e = with_club_defaults(R, slot, e, team, logo_links)
            look = _club_look(R, slot, team, e, logo_links, pack, cache, owners, no_ice, shared)
        elif team.why:
            look = None
        else:
            look = _pack_look(R, slot, team, owners, no_ice)
        if look is not None:
            out.append(look)
    for art, (_slot, picture) in sorted(shared.items()):
        out.append(Look(art, PLAIN_KIT, (None, None), '', (32, 32, 32), (), (), picture, (), STYLE))
    return out


def look_paths(look, maker=None):
    """Every file path (inside the game's USRDIR) a look writes, without making any of it (`maker` finds out which versions
    of the player's own pictures use the shared layout; without it they count as one file each)."""
    if maker is not None:
        return maker.paths(look)
    paths = []
    for variant, _light in look.versions:
        paths += [t.format(s=STYLE, a=look.art, v=variant) for t in (JERSEY, PANT, SOCK, PREVIEW, DECAL)]
    paths += [JERSEY.format(s=look.style, a=look.art, v=variant) for variant, _l, _p in look.files]
    for kit in look.pack:
        paths.append(JERSEY.format(s=look.style, a=look.art, v=kit.variant))
        if look.style == STYLE:
            paths += [t.format(s=STYLE, a=look.art, v=kit.variant) for t in (PANT, SOCK, PREVIEW)]
    if _makes_centre(look):
        paths.append(CENTRE.format(a=look.art))
    if _ice_picture_wanted(look):
        paths.append(ICE_PICTURE.format(a=look.art))
    return paths + clubart.extra_paths(look.art)


def _file_hash(path):
    try:
        with open(path, 'rb') as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except OSError:
        return 'missing'


def look_digest(look):
    """What a look is made of, as a short text: a changed colour, logo, picture, arena or drawing makes a new one."""
    digest = _look_digest(look)
    return _digest(digest, clubart.DRAWING) if look.art in clubart.ARTS else digest


def _look_digest(look):
    logos = [hashlib.sha1(l.convert('RGBA').tobytes()).hexdigest()[:10] if l is not None else '' for l in look.logos]
    return _digest(look.art, [list(map(list, p[:4])) + [_font_key(p.font)] for p in look.kit], logos, look.arena,
                   list(look.ice_colour), [list(v) for v in look.versions],
                   [[v, light, _file_hash(path)] for v, light, path in look.files],
                   look.centre if look.centre in ('make', 'game', OTHER) or look.centre.startswith('pack:')
                   else _file_hash(look.centre), LOOKS_DRAWING,
                   [[k.variant, k.light, k.member, [list(c) for c in k.numbers or ()], k.crc, k.menu, repr(k.scheme), k.font]
                    + ([k.sock, [list(c) for c in k.pants or ()]] if k.sock or k.pants else [])     # a kit without either
                    for k in look.pack],                                                          # keeps its old digest
                   look.style)


def path_art(key):
    """The art id in the path of a file a look writes (JERSEY, PANT, SOCK, CENTRE, ICE_PICTURE, DECAL, PREVIEW, the club art's
    extra files), or None for a path of another kind."""
    for pattern in _art_patterns():
        found = pattern.match(key)
        if found:
            return int(found.group(1))
    return None


@functools.lru_cache(maxsize=1)
def _art_patterns():
    out = []
    for template in (JERSEY, PANT, SOCK, CENTRE, ICE_PICTURE, DECAL, PREVIEW, clubart.NAME) + tuple(clubart.EXTRA) + BORROWED:
        text = re.escape(template).replace(r'\{a\}', r'(\d+)')
        out.append(re.compile('^' + text.replace(r'\{s\}', r'\d+').replace(r'\{v\}', r'\d+') + '$'))
    return out


def split_looks(made, jerseys=True, centres=True):
    """`made` (looks_from) for the two switches "This season's jerseys" and "This season's centre ice" (0.96.0): with
    `centres` off the pack's centre ice becomes the game's own; with `jerseys` off only the pack's centre ice is left (no
    kits). Both on: as they are (the digest of every look stays, so nothing is made again)."""
    if jerseys and centres:
        return list(made)
    out = []
    for m in made:
        packed = str(m.centre).startswith('pack:')
        if jerseys:
            m = m._replace(centre='game') if packed else m
            if m.centre == 'game' and not (m.versions or m.files or m.pack):
                continue
        elif packed:
            m = m._replace(versions=(), files=(), pack=())
        else:
            continue
        out.append(m)
    return out


def install_looks(rpcs3, title_id, looks, say=print, also=(), look_pack=None, only=None, kind=None):
    """Make the files of `looks` from the player's disc and write them into the game folder(s) (RPCS3 closed), with kept
    copies of anything replaced and the manifest "Restore the game's own pictures" uses. Returns how many files were
    written; a look that is installed already is skipped, and a file an earlier run wrote that no look wants any more
    is put back as the game had it. `look_pack`: the pack's pictures, for looks with pack kits. `only` (art ids): `looks` are
    those teams' alone, so only their files are put back (path_art); None: `looks` are every team's. `kind`: 'jerseys'
    or 'centres' when only one of this season's two switches is on: the files of the other kind stay as they are."""
    from . import install
    from .lab import Disc
    install.check(rpcs3, title_id)
    targets = [title_id] + [t for t in also if t != title_id]
    writer = install._Writer([rpcs3.game_folder(t) for t in targets])
    maker = Maker(Disc(rpcs3.game_disc(title_id)), look_pack)
    written, looks = 0, list(looks)
    try:
        wanted = set()
        for n, look in enumerate(looks, 1):
            paths = look_paths(look, maker)
            wanted.update(paths)
            source = f"looks:{look_digest(look)}"
            if all(writer.current(tuple(p.split('/')), source) for p in paths):
                say(f"Jerseys and ice: team {n} of {len(looks)} is installed already")
                continue
            say(f"Jerseys and ice: making team {n} of {len(looks)}")
            files = maker.files(look)
            if not files:
                raise install.ArtError("The game's 3D textures were not found on your disc, so nothing was written.")
            for inner, data in sorted(files.items()):
                writer.write(tuple(inner.split('/')), data, source)
                written += 1
            writer.save()
        for key in writer.stale('looks:', wanted):                   # chosen "the game's own" since the last time
            if kind and parts.writes_centre(key) != (kind == 'centres'):
                continue
            if only is None or path_art(key) in only:
                writer.drop(tuple(key.split('/')))
    finally:
        writer.save()
    return written
