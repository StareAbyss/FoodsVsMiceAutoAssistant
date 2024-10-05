__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Functions
@_typing.overload
def BIMEF(input: cv2.typing.MatLike, output: cv2.typing.MatLike | None = ..., mu: float = ..., a: float = ..., b: float = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def BIMEF(input: cv2.UMat, output: cv2.UMat | None = ..., mu: float = ..., a: float = ..., b: float = ...) -> cv2.UMat: ...

@_typing.overload
def BIMEF2(input: cv2.typing.MatLike, k: float, mu: float, a: float, b: float, output: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def BIMEF2(input: cv2.UMat, k: float, mu: float, a: float, b: float, output: cv2.UMat | None = ...) -> cv2.UMat: ...

def autoscaling(input: cv2.typing.MatLike, output: cv2.typing.MatLike) -> None: ...

def contrastStretching(input: cv2.typing.MatLike, output: cv2.typing.MatLike, r1: int, s1: int, r2: int, s2: int) -> None: ...

def gammaCorrection(input: cv2.typing.MatLike, output: cv2.typing.MatLike, gamma: float) -> None: ...

def logTransform(input: cv2.typing.MatLike, output: cv2.typing.MatLike) -> None: ...


