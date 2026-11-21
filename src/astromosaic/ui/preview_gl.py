"""OpenGL display of an already projected, coverage-aware sky preview."""

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QRectF, Signal, Slot
from PySide6.QtGui import QSurfaceFormat, QVector4D
from PySide6.QtOpenGL import (
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
    QOpenGLVertexArrayObject,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from shiboken6 import VoidPtr

from astromosaic.display import DisplayFrame

BACKGROUND_RGB = (15, 20, 27)
_GL_COLOR_BUFFER_BIT = 0x4000
_GL_TRIANGLES = 0x0004
_VERTEX = """#version 150
out vec2 viewUV;
void main() {
    vec2 uv = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    viewUV = vec2(uv.x, 1.0 - uv.y);
    gl_Position = vec4(2.0 * uv - 1.0, 0.0, 1.0);
}
"""
_FRAGMENT = """#version 150
uniform sampler2D mosaic;
uniform vec4 imageRect;
uniform float midtones;
uniform int encodeSRGB;
in vec2 viewUV;
out vec4 color;
void main() {
    vec2 uv = (viewUV - imageRect.xy) / imageRect.zw;
    vec4 pixel = texture(mosaic, uv);
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) {
        discard;
    }
    if (textureLod(mosaic, uv, 0.0).a == 0.0) {
        discard;
    }
    if (pixel.a == 0.0) {
        discard;
    }
    // Coverage-premultiplied mip levels average only the valid samples.
    vec3 x = clamp(pixel.rgb / pixel.a, 0.0, 1.0);
    vec3 stretched = ((midtones - 1.0) * x) / (((2.0 * midtones - 1.0) * x) - midtones);
    if (encodeSRGB != 0) {
        stretched = mix(
            12.92 * stretched,
            1.055 * pow(stretched, vec3(1.0 / 2.4)) - 0.055,
            greaterThan(stretched, vec3(0.0031308))
        );
    }
    color = vec4(stretched, 1.0);
}
"""


class OpenGLPreview(QOpenGLWidget):
    failed = Signal(str)

    def __init__(
        self, image_rect: Callable[[], QRectF], paint_overlay: Callable[[], None] | None = None
    ) -> None:
        super().__init__()
        format = QSurfaceFormat()
        format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        format.setVersion(3, 2)
        format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        self.setFormat(format)
        self._image_rect = image_rect
        self._paint_overlay = paint_overlay
        self._program: QOpenGLShaderProgram | None = None
        self._texture: QOpenGLTexture | None = None
        self._vao: QOpenGLVertexArrayObject | None = None
        self._frame: DisplayFrame | None = None
        self._uploaded: tuple[DisplayFrame | None, bool] = (None, False)
        self._midtones = 0.5
        self._preserve_tone = False
        self._failed = False

    def initializeGL(self) -> None:
        self._failed = False
        self.context().aboutToBeDestroyed.connect(self.release_resources)
        program = self._program = QOpenGLShaderProgram()
        shader = QOpenGLShader.ShaderTypeBit
        if not (
            program.addShaderFromSourceCode(shader.Vertex, _VERTEX)
            and program.addShaderFromSourceCode(shader.Fragment, _FRAGMENT)
            and program.link()
        ):
            self._fail(f"Preview shader build failed. {program.log()}")
            return
        self._vao = QOpenGLVertexArrayObject()
        if not self._vao.create():
            self._fail("OpenGL could not create the preview vertex array.")

    def set_display(
        self, frame: DisplayFrame | None, midtones: float, *, preserve_tone: bool = False
    ) -> None:
        self._frame = frame
        self._midtones = 0.5 if preserve_tone else midtones
        self._preserve_tone = preserve_tone
        if frame is None and self._texture is not None and self.isValid():
            self.makeCurrent()
            try:
                self._drop_texture()
            finally:
                self.doneCurrent()
        self.update()

    def _drop_texture(self) -> None:
        if self._texture is not None:
            self._texture.destroy()
            self._texture = None
        self._uploaded = (None, False)

    def _upload(self, frame: DisplayFrame | None) -> None:
        self._drop_texture()
        if frame is None:
            return
        texture = self._texture = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
        texture.setFormat(QOpenGLTexture.TextureFormat.RGBA32F)
        texture.setSize(*frame.size)
        texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
        texture.setMipLevels(texture.maximumMipLevels())
        filtering = QOpenGLTexture.Filter
        texture.setMinMagFilters(filtering.NearestMipMapNearest, filtering.Nearest)
        rgba = QOpenGLTexture.PixelFormat.RGBA
        float32 = QOpenGLTexture.PixelType.Float32
        texture.allocateStorage(rgba, float32)
        if not texture.isStorageAllocated():
            raise RuntimeError("OpenGL could not allocate the preview texture.")
        # Qt consumes the read-only float buffer while this frame holds it alive.
        pixels = (
            frame.preserved_rgba
            if self._preserve_tone and frame.preserved_rgba is not None
            else frame.rgba
        )
        pointer = VoidPtr(pixels.data)  # type: ignore[arg-type]
        texture.setData(rgba, float32, cast(int, pointer))
        error = self.context().functions().glGetError()
        if error:
            raise RuntimeError(f"OpenGL preview upload failed (0x{error:04x}).")
        self._uploaded = (frame, self._preserve_tone)

    def paintGL(self) -> None:
        functions = self.context().functions()
        r, g, b = BACKGROUND_RGB
        functions.glClearColor(r / 255, g / 255, b / 255, 1.0)
        functions.glClear(_GL_COLOR_BUFFER_BIT)
        program, vao = self._program, self._vao
        if self._failed or program is None or vao is None:
            return
        if (self._frame, self._preserve_tone) != self._uploaded:
            try:
                self._upload(self._frame)
            except (RuntimeError, TypeError) as error:
                self._fail(str(error))
                return
        texture = self._texture
        rect = self._image_rect()
        if texture is None or rect.isEmpty():
            return
        if not program.bind():
            self._fail("OpenGL could not bind the preview shader.")
            return
        width, height = self.width(), self.height()
        functions.glUniform1i(program.uniformLocation(b"mosaic"), 0)
        functions.glUniform1f(program.uniformLocation(b"midtones"), self._midtones)
        functions.glUniform1i(
            program.uniformLocation(b"encodeSRGB"),
            int(self._frame is not None and self._frame.photo_levels is not None),
        )
        program.setUniformValue(
            program.uniformLocation(b"imageRect"),
            QVector4D(
                rect.x() / width, rect.y() / height, rect.width() / width, rect.height() / height
            ),
        )
        texture.bind(0)
        vao.bind()
        functions.glDrawArrays(_GL_TRIANGLES, 0, 3)
        vao.release()
        texture.release(0)
        program.release()
        if self._paint_overlay is not None:
            self._paint_overlay()

    def _fail(self, reason: str) -> None:
        self._failed = True
        self.failed.emit(reason)

    @Slot()
    def release_resources(self) -> None:
        if self._program is None:
            return
        self.makeCurrent()
        try:
            if self._vao is not None:
                self._vao.destroy()
                self._vao = None
            self._drop_texture()
            self._program = None
        finally:
            self.doneCurrent()
