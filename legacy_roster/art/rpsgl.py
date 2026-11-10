"""The game's 3D textures (`rendering/...*.rpsgl` in nocacherender.big and cacherender.big): jerseys, pants, socks,
the ice (centre logo, rink picture), banners, crowd props. Read 2026-10-06 from the owner's disc; nothing here has
been loaded by the game yet (docs/ROADMAP.md "Jerseys and the ice").

A file is a "chunkzip" (a header and 128 KB chunks of raw deflate) around a PS3 RenderWare file (`\\x89RW4ps3`) that
holds named rasters, DXT1 or DXT5 with a full chain of mipmaps, one after the other:

    chunkzip  'chunkzip', u32 2, unpacked size, 0x20000, chunk count, 16; then per chunk (aligned to 16): u32 size,
              u32 1 (deflated; else stored), the data
    RW4       at 0x44 the size of the header, which names the rasters ('jersey_1_22_3_cm.Raster') and describes
              each (offset and size of its pixels after the header, width, height, mipmaps)

A file read here and packed again with zlib level 9 is the same bytes as the disc's (60 of 60 files tried). A raster
is replaced by one of the same size and format only, so nothing else in the file moves.
"""
import io
import re
import struct
import zlib

CHUNK = 0x20000
OPAQUE_SLACK = 1        # DXT1: a block Pillow got more than this far off is encoded again (None: Pillow's as they are; 0-2 measured equal, mean error 0.5 against 4.9)


class RpsglError(ValueError):
    """The file is not what this module reads (the message says what)."""


def unpack(data):
    """The bytes inside a chunkzip (data that is no chunkzip is returned as it is)."""
    if data[:8] != b'chunkzip':
        return bytes(data)
    _version, total, _chunk, count = struct.unpack_from('>IIII', data, 8)
    start, out = 0x30, bytearray()
    for _ in range(count):
        size, flag = struct.unpack_from('>II', data, start - 8)
        blk = data[start:start + size]
        out += zlib.decompressobj(-15).decompress(blk) if flag == 1 else blk
        start = ((start + size + 8 + 15) // 16) * 16
    if len(out) != total:
        raise RpsglError("the file does not unpack to the size it says")
    return bytes(out)


def pack(data, level=9):
    """`data` packed the way the game's files are."""
    count = (len(data) + CHUNK - 1) // CHUNK
    out = bytearray(0x30)
    out[0:8] = b'chunkzip'
    struct.pack_into('>IIIII', out, 8, 2, len(data), CHUNK, count, 16)
    pos = 0x30
    for i in range(count):
        comp = zlib.compressobj(level, zlib.DEFLATED, -15)
        blk = comp.compress(data[i * CHUNK:(i + 1) * CHUNK]) + comp.flush()
        struct.pack_into('>II', out, pos - 8, len(blk), 1)
        out += blk
        following = ((pos + len(blk) + 8 + 15) // 16) * 16
        if i < count - 1:
            out += b'\0' * (following - len(out))
        pos = following
    return bytes(out)


class Rpsgl:
    """One texture file: its rasters can be listed, shown and replaced."""

    def __init__(self, raw):
        self.packed = raw[:8] == b'chunkzip'
        self.data = bytearray(unpack(raw))
        if self.data[1:6] != b'RW4ps':
            raise RpsglError("not a RenderWare PS3 file")
        self.header = struct.unpack_from('>I', self.data, 0x44)[0]
        self.rasters = self._rasters()

    def _rasters(self):
        d, hs = self.data, self.header
        names = [m.group(1).decode() for m in re.finditer(rb'([A-Za-z0-9_]+)\.Raster\x00', bytes(d[:hs]))]
        spots = []
        for p in range(0x40, hs - 8, 4):
            if struct.unpack_from('>I', d, p)[0] == 0x10030 and struct.unpack_from('>I', d, p - 4)[0] == 1 \
                    and struct.unpack_from('>I', d, p - 8)[0] == 0x80:
                spots.append((struct.unpack_from('>I', d, p - 20)[0], struct.unpack_from('>I', d, p - 12)[0]))
        sizes = []
        for m in re.finditer(b'\x00\x00\xff\xff\x00\x00\x00\x00', bytes(d[:hs])):
            w, h, mips = struct.unpack_from('>HHB', d, m.end())
            sizes.append((w, h, mips))
        out = {}
        for i, (off, size) in enumerate(spots):
            if i >= len(names) or i >= len(sizes):
                continue
            w, h, mips = sizes[i]
            blocks = sum(max(1, (w >> k) // 4) * max(1, (h >> k) // 4) for k in range(mips))
            fmt = 'DXT1' if abs(blocks * 8 - size) < 0x100 else 'DXT5' if abs(blocks * 16 - size) < 0x100 else None
            out[names[i]] = {'name': names[i], 'at': hs + off, 'size': size, 'width': w, 'height': h, 'mips': mips,
                             'format': fmt}
        return out

    def image(self, name):
        """The raster `name` as a Pillow RGBA picture (the first mipmap)."""
        from PIL import Image
        r = self.rasters[name]
        if r['format'] is None:
            raise RpsglError(f"{name} is not DXT1 or DXT5")
        w, h = r['width'], r['height']
        size = (w // 4) * (h // 4) * (8 if r['format'] == 'DXT1' else 16)
        hdr = bytearray(128)
        hdr[0:4] = b'DDS '
        struct.pack_into('<7I', hdr, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, 0, 0, 1)
        struct.pack_into('<II4s', hdr, 76, 32, 4, r['format'].encode())
        struct.pack_into('<I', hdr, 108, 0x1000)
        img = Image.open(io.BytesIO(bytes(hdr) + bytes(self.data[r['at']:r['at'] + size])))
        img.load()
        return img.convert('RGBA')

    def replace(self, name, img, coverage=None, flat=None):
        """Put the picture `img` (Pillow; resized to the raster's size when it differs) into the raster `name`, with all
        its mipmaps (dds.mipmaps). `coverage`: alpha says how much of a pixel shows, as on the centre-ice logos, the
        number sheets and the helmet decals (the default); not for the normal maps (`*_nm`), whose alpha is data.
        `flat`: a colour every level is flattened onto (dds.flatten: the centre ice). The file keeps its size and
        layout."""
        from PIL import Image
        from . import dds
        r = self.rasters[name]
        if r['format'] is None:
            raise RpsglError(f"{name} is not DXT1 or DXT5")
        if coverage is None:
            coverage = not name.endswith('_nm')
        w, h = r['width'], r['height']
        img = img.convert('RGBA')
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS) if coverage else \
                Image.merge('RGBA', [c.resize((w, h), Image.LANCZOS) for c in img.split()])
        if coverage and r['format'] == 'DXT5':
            encoded = dds.mipmaps(img, r['format'], r['mips'], True, flat=flat)
        elif coverage:              # DXT1: opaque (jerseys, pants, socks, masks); only the blocks Pillow got far off
            encoded = dds.mipmaps(img, r['format'], r['mips'], True, colour_slack=OPAQUE_SLACK, alpha_slack=None)
        else:                       # normal maps: Pillow's blocks (smooth data, small errors), every channel on its own
            encoded = dds.mipmaps(img, r['format'], r['mips'], False, colour_slack=None, alpha_slack=None)
        if len(encoded) != r['size']:
            raise RpsglError(f"{name}: the new picture came out {len(encoded)} bytes, the raster has {r['size']}")
        self.data[r['at']:r['at'] + r['size']] = encoded

    def copy(self, name, other, other_name):
        """Raster `name` made equal to raster `other_name` of the file `other`: the encoded bytes are taken over as they
        are when both have the same size, format and mipmaps (no second round of compression), otherwise the picture is
        replaced like `replace` does."""
        r, o = self.rasters[name], other.rasters[other_name]
        if all(r[k] == o[k] for k in ('width', 'height', 'mips', 'format', 'size')) and r['format'] is not None:
            self.data[r['at']:r['at'] + r['size']] = other.data[o['at']:o['at'] + o['size']]
        else:
            self.replace(name, other.image(other_name))

    def build(self):
        """The file as the game reads it (packed again when it was)."""
        return pack(bytes(self.data)) if self.packed else bytes(self.data)
