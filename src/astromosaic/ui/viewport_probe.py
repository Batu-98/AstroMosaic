"""Check a signed float texture, TAN projection, context recreation, and CPU preview."""

import argparse
import json
import struct
import sys
from math import atan, cos, sin
from typing import cast

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QColor, QImage, QSurfaceFormat
from PySide6.QtOpenGL import (
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
    QOpenGLVertexArrayObject,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import VoidPtr

_WIDTH, _HEIGHT = 96, 64
_PANEL = (-2.0, 0.0, 0.25, 2.0)
_GL_TRIANGLES = 0x0004
_VERTEX = """#version 150
out vec2 uv;
void main() {
    uv = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(2.0 * uv - 1.0, 0.0, 1.0);
}
"""
_FRAGMENT = """#version 150
uniform sampler2D panel;
in vec2 uv;
out vec4 color;
void main() {
    vec2 p = (uv - 0.5) * 0.8;
    // Rotate the viewing direction about the north axis by atan(1/4) and project onto the panel.
    const float c = 0.9701425;
    const float s = 0.2425356;
    vec3 ray = vec3(c * p.x + s, p.y, c - s * p.x);
    vec2 panel_uv = vec2(0.5) + ray.xy / ray.z;
    if (any(lessThan(panel_uv, vec2(0.0))) || any(greaterThanEqual(panel_uv, vec2(1.0)))) {
        color = vec4(1.0, 0.0, 1.0, 1.0);
    } else {
        float gray = (texture(panel, panel_uv).r + 2.0) / 4.0;
        color = vec4(gray, gray, gray, 1.0);
    }
}
"""


class _FloatViewport(QOpenGLWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.program: QOpenGLShaderProgram | None = None
        self.texture: QOpenGLTexture | None = None
        self.vao: QOpenGLVertexArrayObject | None = None
        self.error: str | None = None
        self.initializations = 0
        self.releases = 0

    def initializeGL(self) -> None:
        self.initializations += 1
        self.context().aboutToBeDestroyed.connect(self.release_resources)
        self.error = None

        self.program = program = QOpenGLShaderProgram()
        shader_types = QOpenGLShader.ShaderTypeBit
        if not (
            program.addShaderFromSourceCode(shader_types.Vertex, _VERTEX)
            and program.addShaderFromSourceCode(shader_types.Fragment, _FRAGMENT)
            and program.link()
        ):
            self.error = f"Shader build failed: {program.log()}"
            return

        self.texture = texture = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
        texture.setFormat(QOpenGLTexture.TextureFormat.R32F)
        texture.setSize(2, 2)
        texture.setMinMagFilters(QOpenGLTexture.Filter.Nearest, QOpenGLTexture.Filter.Nearest)
        texture.allocateStorage(QOpenGLTexture.PixelFormat.Red, QOpenGLTexture.PixelType.Float32)
        if not texture.isStorageAllocated():
            self.error = "OpenGL failed to allocate an R32F texture."
            return
        data = struct.pack("=4f", *_PANEL)
        # The bindings accept a bytes buffer and a Shiboken pointer despite the int stubs.
        pointer = VoidPtr(data)  # type: ignore[arg-type]
        texture.setData(
            QOpenGLTexture.PixelFormat.Red, QOpenGLTexture.PixelType.Float32, cast(int, pointer)
        )

        self.vao = QOpenGLVertexArrayObject()
        if not self.vao.create():
            self.error = "OpenGL failed to create a vertex array."

    def paintGL(self) -> None:
        program, texture, vao = self.program, self.texture, self.vao
        if self.error is not None or program is None or texture is None or vao is None:
            return
        if not program.bind():
            self.error = "OpenGL failed to bind the projection shader."
            return
        program.setUniformValue(program.uniformLocation(b"panel"), 0)
        texture.bind(0)
        vao.bind()
        self.context().functions().glDrawArrays(_GL_TRIANGLES, 0, 3)
        vao.release()
        texture.release(0)
        program.release()

    def release_resources(self) -> None:
        if self.program is None:
            return
        self.makeCurrent()
        if self.vao is not None:
            self.vao.destroy()
            self.vao = None
        if self.texture is not None:
            self.texture.destroy()
            self.texture = None
        self.program = None
        self.doneCurrent()
        self.releases += 1


def _cpu_preview(width: int, height: int) -> QImage:
    angle = atan(0.25)
    c, s = cos(angle), sin(angle)
    image = QImage(width, height, QImage.Format.Format_RGB32)
    outside = QColor(255, 0, 255)
    levels = [round(255 * (value + 2.0) / 4.0) for value in _PANEL]
    grays = [QColor(level, level, level) for level in levels]
    for y in range(height):
        north = (0.5 - (y + 0.5) / height) * 0.8
        for x in range(width):
            east = ((x + 0.5) / width - 0.5) * 0.8
            denominator = c - s * east
            u = 0.5 + (c * east + s) / denominator
            v = 0.5 + north / denominator
            color = grays[2 * int(v * 2) + int(u * 2)] if 0 <= u < 1 and 0 <= v < 1 else outside
            image.setPixelColor(x, y, color)
    return image


def _verify_samples(image: QImage) -> None:
    checks = (
        (0.12, 0.75, (0, 0, 0)),
        (0.60, 0.75, (128, 128, 128)),
        (0.12, 0.25, (143, 143, 143)),
        (0.60, 0.25, (255, 255, 255)),
        (0.95, 0.50, (255, 0, 255)),
    )
    for u, v, expected in checks:
        color = image.pixelColor(int(u * image.width()), int(v * image.height()))
        actual = (color.red(), color.green(), color.blue())
        if any(abs(a - b) > 1 for a, b in zip(actual, expected, strict=True)):
            raise RuntimeError(f"Preview sample at ({u}, {v}) was {actual}, expected {expected}.")


def _gpu_probe() -> dict[str, str | int | float]:
    format = QSurfaceFormat()
    format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    format.setVersion(3, 2)
    format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(format)
    application = QApplication(["astromosaic-viewport-probe"])

    hosts = [QWidget(), QWidget()]
    for host in hosts:
        host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        host.setFixedSize(_WIDTH, _HEIGHT)
    widget = _FloatViewport(hosts[0])
    try:
        for host in hosts:
            widget.setParent(host)
            host.show()
            widget.show()
            image = widget.grabFramebuffer()
            if widget.error or not widget.isValid() or image.isNull():
                raise RuntimeError(widget.error or "Qt could not create an OpenGL framebuffer.")
            dpr = widget.devicePixelRatioF()
            if (image.width(), image.height()) != (round(_WIDTH * dpr), round(_HEIGHT * dpr)):
                raise RuntimeError(
                    "OpenGL framebuffer dimensions disagree with the Qt device pixel ratio."
                )
            _verify_samples(image)
            host.hide()
        if widget.initializations != 2 or widget.releases != 1:
            raise RuntimeError("Qt did not recreate and release the OpenGL context on reparenting.")
        actual_format = widget.context().format()
        return {
            "backend": "opengl",
            "qt": qVersion(),
            "contexts": widget.initializations,
            "gl_version": f"{actual_format.majorVersion()}.{actual_format.minorVersion()}",
            "device_pixel_ratio": dpr,
            "width": image.width(),
            "height": image.height(),
        }
    finally:
        widget.release_resources()
        widget.close()
        for host in hosts:
            host.close()
        application.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("auto", "gpu", "cpu"), default="auto")
    args = parser.parse_args(argv)

    result: dict[str, str | int | float] = {"backend": "cpu", "qt": qVersion()}
    try:
        _verify_samples(_cpu_preview(_WIDTH, _HEIGHT))
        if args.backend != "cpu":
            try:
                result = _gpu_probe()
            except RuntimeError as error:
                if args.backend == "gpu":
                    raise
                result["fallback_reason"] = str(error)
    except RuntimeError as error:
        print(f"viewport-probe: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
