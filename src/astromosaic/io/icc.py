"""Recognize standard sRGB matrix and transfer curves in bounded ICC metadata."""

from struct import unpack_from

import numpy as np

MAX_ICC_BYTES = 1024**2
# ICC sRGB colorants in the D50 profile connection space, in R, G, B order.
_SRGB_COLORANTS = (
    (0.43607, 0.22249, 0.01392),
    (0.38506, 0.71689, 0.09708),
    (0.14308, 0.06062, 0.71410),
)
_SRGB_PARAMETERS = (2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045, 0, 0)


def _srgb_curve(data: bytes) -> bool:
    if len(data) < 12:
        return False
    if data[:4] == b"para":
        kind = unpack_from(">H", data, 8)[0]
        if kind in (3, 4):
            count = 5 if kind == 3 else 7
            if len(data) >= 12 + count * 4:
                values = np.array(unpack_from(f">{count}i", data, 12)) / 65536
                return bool(np.allclose(values, _SRGB_PARAMETERS[:count], atol=2 / 65536, rtol=0))
    if data[:4] != b"curv":
        return False
    count = unpack_from(">I", data, 8)[0]
    if not 256 <= count <= 4096 or len(data) < 12 + count * 2:
        return False
    values = np.frombuffer(data, dtype=">u2", offset=12, count=count) / 65535
    if np.any(np.diff(values) < 0):
        return False
    knots = np.linspace(0, 1, count)
    probe = np.concatenate((knots, (knots[:-1] + knots[1:]) * 0.5, [0.04045]))
    expected = np.where(probe <= 0.04045, probe / 12.92, ((probe + 0.055) / 1.055) ** 2.4)
    return bool(np.max(np.abs(np.interp(probe, knots, values) - expected)) <= 0.00015)


def is_srgb_profile(profile: bytes) -> bool:
    """Match the colorants and transfer function instead of trusting the profile name."""
    if not 132 <= len(profile) <= MAX_ICC_BYTES:
        return False
    size = unpack_from(">I", profile)[0]
    count = unpack_from(">I", profile, 128)[0]
    table_end = 132 + count * 12
    if (
        profile[8] not in (2, 4)
        or profile[12:16] not in (b"mntr", b"scnr", b"spac")
        or profile[16:24] != b"RGB XYZ "
        or profile[36:40] != b"acsp"
        or not 6 <= count <= 256
        or not table_end <= size <= len(profile)
    ):
        return False
    tags: dict[bytes, tuple[int, int]] = {}
    for index in range(count):
        key, start, length = unpack_from(">4sII", profile, 132 + 12 * index)
        if (
            key in tags
            or key[:3] in (b"A2B", b"B2A", b"D2B", b"B2D")
            or not table_end <= start <= start + length <= size
        ):
            return False
        tags[key] = (start, start + length)

    for channel, expected in zip((b"r", b"g", b"b"), _SRGB_COLORANTS, strict=True):
        lo, hi = tags.get(channel + b"XYZ", (0, 0))
        if hi - lo != 20 or profile[lo : lo + 4] != b"XYZ ":
            return False
        xyz = np.array(unpack_from(">3i", profile, lo + 8)) / 65536
        if not np.allclose(xyz, expected, atol=0.001, rtol=0):
            return False
        lo, hi = tags.get(channel + b"TRC", (0, 0))
        if hi - lo > 12 + 4096 * 2 or not _srgb_curve(profile[lo:hi]):
            return False
    return True
