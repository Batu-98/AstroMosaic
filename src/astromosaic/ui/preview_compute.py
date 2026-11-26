"""Compute bilinear sky preview samples on an offscreen OpenGL worker context."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from math import ceil
from typing import cast

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram
from shiboken6 import VoidPtr

_SHADER_STORAGE_BUFFER = 0x90D2
_BUFFER_UPDATE_BARRIER = 0x0200
_RENDERER = 0x1F01
_WORK_GROUP = 64
_MAX_SAMPLES_PER_DISPATCH = 16_384
_COMPUTE = """#version 430
layout(local_size_x = 64) in;
layout(std430, binding = 0) readonly buffer Fractions { dvec2 fractions[]; };
layout(std430, binding = 1) readonly buffer Neighbors { vec4 pixels[]; };
layout(std430, binding = 2) writeonly buffer Results { dvec4 results[]; };
uniform int sampleCount;

void main() {
    uint sampleIndex = gl_GlobalInvocationID.x;
    if (sampleIndex >= uint(sampleCount)) return;
    dvec2 lower = 1.0LF - fractions[sampleIndex];
    dvec2 upper = 1.0LF - lower;
    precise double support = 0.0LF;
    precise dvec3 value = dvec3(0.0LF);
    for (uint corner = 0u; corner < 4u; ++corner) {
        vec3 pixel = pixels[sampleIndex * 4u + corner].xyz;
        if (any(isnan(pixel)) || any(isinf(pixel))) continue;
        precise double weight = (corner < 2u ? lower.x : upper.x)
                              * (corner % 2u == 0u ? lower.y : upper.y);
        support += weight;
        value += dvec3(pixel) * weight;
    }
    results[sampleIndex] = dvec4(support, support > 0.0LF ? value / support : dvec3(0.0LF));
}
"""


def create_preview_surface(parent: QObject, *, enabled: bool) -> QOffscreenSurface | None:
    """Create the surface on the GUI thread for use by one preview job."""
    if not enabled or QGuiApplication.platformName() in {"minimal", "offscreen"}:
        return None
    surface = QOffscreenSurface(parent=parent)
    format = QSurfaceFormat()
    format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    format.setVersion(4, 3)
    surface.setFormat(format)
    surface.create()
    if not surface.isValid():
        surface.deleteLater()
        return None
    return surface


class OpenGLPreviewSampler:
    def __init__(self, context: QOpenGLContext, program: QOpenGLShaderProgram) -> None:
        self._gl = context.extraFunctions()
        self._program = program
        self._count_uniform = program.uniformLocation(b"sampleCount")
        self._buffers = tuple(QOpenGLBuffer() for _ in range(3))
        self.used = False
        self._failed = False

    def create_buffers(self) -> bool:
        for index, buffer in enumerate(self._buffers):
            buffer.setUsagePattern(QOpenGLBuffer.UsagePattern.StreamDraw)
            if not buffer.create() or not buffer.bind():
                return False
            self._gl.glBindBufferBase(_SHADER_STORAGE_BUFFER, index, buffer.bufferId())
        return not self._gl.glGetError()

    def close(self) -> None:
        for buffer in self._buffers:
            buffer.destroy()

    def __call__(
        self, fractions: NDArray[np.float64], neighbors: NDArray[np.float32]
    ) -> NDArray[np.float64] | None:
        if self._failed:
            return None
        try:
            result = self._sample_batches(fractions, neighbors)
        except (RuntimeError, TypeError, ValueError) as error:
            self._failed = True
            logging.getLogger(__name__).info("Sky preview GPU sampling fell back to CPU. %s", error)
            return None
        self.used = True
        return result

    def _sample_batches(
        self, fractions: NDArray[np.float64], neighbors: NDArray[np.float32]
    ) -> NDArray[np.float64]:
        count = len(fractions)
        if count <= _MAX_SAMPLES_PER_DISPATCH:
            return self._sample(fractions, neighbors)
        result = np.empty((count, 4), dtype=np.float64)
        for start in range(0, count, _MAX_SAMPLES_PER_DISPATCH):
            batch = slice(start, start + _MAX_SAMPLES_PER_DISPATCH)
            result[batch] = self._sample(fractions[batch], neighbors[batch])
        return result

    def _sample(
        self, fractions: NDArray[np.float64], neighbors: NDArray[np.float32]
    ) -> NDArray[np.float64]:
        count = len(fractions)
        pixels = np.zeros((count, 4, 4), dtype=np.float32)
        pixels[..., : neighbors.shape[-1]] = neighbors
        result = np.empty((count, 4), dtype=np.float64)
        inputs = (fractions.tobytes(), pixels.tobytes())
        for buffer, data in zip(self._buffers[:2], inputs, strict=True):
            if not buffer.bind():
                raise RuntimeError("OpenGL could not bind a preview sampling buffer.")
            buffer.allocate(data, len(data))
        output = self._buffers[-1]
        if not output.bind():
            raise RuntimeError("OpenGL could not bind the preview results buffer.")
        output.allocate(result.nbytes)
        self._gl.glUniform1i(self._count_uniform, count)
        self._gl.glDispatchCompute(ceil(count / _WORK_GROUP), 1, 1)
        self._gl.glMemoryBarrier(_BUFFER_UPDATE_BARRIER)
        pointer = cast(int, VoidPtr(result.data))  # type: ignore[arg-type]
        if self._gl.glGetError() or not output.read(0, pointer, result.nbytes):
            raise RuntimeError("OpenGL could not read the computed preview samples.")
        return result


@contextmanager
def open_preview_sampler(surface: QOffscreenSurface | None) -> Iterator[OpenGLPreviewSampler | None]:
    if surface is None:
        yield None
        return
    context = QOpenGLContext()
    context.setFormat(surface.format())
    if not context.create() or context.format().version() < (4, 3) or not context.makeCurrent(surface):
        yield None
        return
    program = QOpenGLShaderProgram()
    sampler = None
    try:
        ready = False
        try:
            renderer = context.extraFunctions().glGetString(_RENDERER).lower()
            software = ("llvmpipe", "softpipe", "software", "gdi generic")
            shader_type = QOpenGLShader.ShaderTypeBit.Compute
            if not any(name in renderer for name in software) and (
                program.addShaderFromSourceCode(shader_type, _COMPUTE)
                and program.link() and program.bind()
            ):
                sampler = OpenGLPreviewSampler(context, program)
                ready = sampler.create_buffers()
        except (RuntimeError, TypeError, ValueError) as error:
            logging.getLogger(__name__).info("Sky preview GPU sampling unavailable. %s", error)
        yield sampler if ready else None
    finally:
        if sampler is not None:
            sampler.close()
        program.release()
        del sampler, program
        context.doneCurrent()
