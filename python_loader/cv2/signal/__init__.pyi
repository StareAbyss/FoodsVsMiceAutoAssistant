__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Functions
@_typing.overload
def resampleSignal(inputSignal: cv2.typing.MatLike, inFreq: int, outFreq: int, outSignal: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def resampleSignal(inputSignal: cv2.UMat, inFreq: int, outFreq: int, outSignal: cv2.UMat | None = ...) -> cv2.UMat: ...


