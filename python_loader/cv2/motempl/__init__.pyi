__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Functions
@_typing.overload
def calcGlobalOrientation(orientation: cv2.typing.MatLike, mask: cv2.typing.MatLike, mhi: cv2.typing.MatLike, timestamp: float, duration: float) -> float: ...
@_typing.overload
def calcGlobalOrientation(orientation: cv2.UMat, mask: cv2.UMat, mhi: cv2.UMat, timestamp: float, duration: float) -> float: ...

@_typing.overload
def calcMotionGradient(mhi: cv2.typing.MatLike, delta1: float, delta2: float, mask: cv2.typing.MatLike | None = ..., orientation: cv2.typing.MatLike | None = ..., apertureSize: int = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def calcMotionGradient(mhi: cv2.UMat, delta1: float, delta2: float, mask: cv2.UMat | None = ..., orientation: cv2.UMat | None = ..., apertureSize: int = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def segmentMotion(mhi: cv2.typing.MatLike, timestamp: float, segThresh: float, segmask: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, _typing.Sequence[cv2.typing.Rect]]: ...
@_typing.overload
def segmentMotion(mhi: cv2.UMat, timestamp: float, segThresh: float, segmask: cv2.UMat | None = ...) -> tuple[cv2.UMat, _typing.Sequence[cv2.typing.Rect]]: ...

@_typing.overload
def updateMotionHistory(silhouette: cv2.typing.MatLike, mhi: cv2.typing.MatLike, timestamp: float, duration: float) -> cv2.typing.MatLike: ...
@_typing.overload
def updateMotionHistory(silhouette: cv2.UMat, mhi: cv2.UMat, timestamp: float, duration: float) -> cv2.UMat: ...


