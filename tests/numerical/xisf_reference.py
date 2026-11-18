"""Independent reopening of the small, uncompressed test exports."""

import struct
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from numpy.typing import NDArray


def read_xisf_attachments(
    path: Path,
) -> tuple[list[NDArray[np.generic]], ET.Element]:
    raw = path.read_bytes()
    assert raw[:8] == b"XISF0100"
    size, reserved = struct.unpack_from("<II", raw, 8)
    assert reserved == 0 and size > 0
    root = ET.fromstring(raw[16 : 16 + size])
    images = root.findall("{http://www.pixinsight.com/xisf}Image")
    rasters = []
    for image in images:
        kind, offset, length = image.attrib["location"].split(":")
        width, height, channels = map(int, image.attrib["geometry"].split(":"))
        sample_type = {"Float32": "<f4", "UInt8": "u1"}[image.attrib["sampleFormat"]]
        start, end = int(offset), int(offset) + int(length)
        assert kind == "attachment" and start % 4096 == 0 and 16 + size <= start < end <= len(raw)
        assert channels == 1 or image.attrib["pixelStorage"] == "Normal"
        shape = (height, width) if channels == 1 else (height, width, channels)
        rasters.append(np.frombuffer(raw[start:end], dtype=sample_type).reshape(shape))
    return rasters, images[0]
