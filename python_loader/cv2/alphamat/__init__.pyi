__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Functions
@_typing.overload
def infoFlow(image: cv2.typing.MatLike, tmap: cv2.typing.MatLike, result: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def infoFlow(image: cv2.UMat, tmap: cv2.UMat, result: cv2.UMat | None = ...) -> cv2.UMat: ...


