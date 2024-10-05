__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Classes
class Tracker(cv2.Algorithm):
    # Functions
    @_typing.overload
    def compute(self, img: cv2.typing.MatLike, num: int, len: int, K: cv2.typing.MatLike, rvec: cv2.typing.MatLike, tvec: cv2.typing.MatLike, termcrit: cv2.typing.TermCriteria = ...) -> tuple[float, cv2.typing.MatLike, cv2.typing.MatLike]: ...
    @_typing.overload
    def compute(self, img: cv2.UMat, num: int, len: int, K: cv2.UMat, rvec: cv2.UMat, tvec: cv2.UMat, termcrit: cv2.typing.TermCriteria = ...) -> tuple[float, cv2.UMat, cv2.UMat]: ...

    def clearState(self) -> None: ...


class Rapid(Tracker):
    # Functions
    @classmethod
    @_typing.overload
    def create(cls, pts3d: cv2.typing.MatLike, tris: cv2.typing.MatLike) -> Rapid: ...
    @classmethod
    @_typing.overload
    def create(cls, pts3d: cv2.UMat, tris: cv2.UMat) -> Rapid: ...


class OLSTracker(Tracker):
    # Functions
    @classmethod
    @_typing.overload
    def create(cls, pts3d: cv2.typing.MatLike, tris: cv2.typing.MatLike, histBins: int = ..., sobelThesh: int = ...) -> OLSTracker: ...
    @classmethod
    @_typing.overload
    def create(cls, pts3d: cv2.UMat, tris: cv2.UMat, histBins: int = ..., sobelThesh: int = ...) -> OLSTracker: ...


class GOSTracker(Tracker):
    # Functions
    @staticmethod
    @_typing.overload
    def create(pts3d: cv2.typing.MatLike, tris: cv2.typing.MatLike, histBins: int = ..., sobelThesh: int = ...) -> OLSTracker: ...
    @staticmethod
    @_typing.overload
    def create(pts3d: cv2.UMat, tris: cv2.UMat, histBins: int = ..., sobelThesh: int = ...) -> OLSTracker: ...



# Functions
@_typing.overload
def convertCorrespondencies(cols: cv2.typing.MatLike, srcLocations: cv2.typing.MatLike, pts2d: cv2.typing.MatLike | None = ..., pts3d: cv2.typing.MatLike | None = ..., mask: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def convertCorrespondencies(cols: cv2.UMat, srcLocations: cv2.UMat, pts2d: cv2.UMat | None = ..., pts3d: cv2.UMat | None = ..., mask: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def drawCorrespondencies(bundle: cv2.typing.MatLike, cols: cv2.typing.MatLike, colors: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def drawCorrespondencies(bundle: cv2.UMat, cols: cv2.UMat, colors: cv2.UMat | None = ...) -> cv2.UMat: ...

@_typing.overload
def drawSearchLines(img: cv2.typing.MatLike, locations: cv2.typing.MatLike, color: cv2.typing.Scalar) -> cv2.typing.MatLike: ...
@_typing.overload
def drawSearchLines(img: cv2.UMat, locations: cv2.UMat, color: cv2.typing.Scalar) -> cv2.UMat: ...

@_typing.overload
def drawWireframe(img: cv2.typing.MatLike, pts2d: cv2.typing.MatLike, tris: cv2.typing.MatLike, color: cv2.typing.Scalar, type: int = ..., cullBackface: bool = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def drawWireframe(img: cv2.UMat, pts2d: cv2.UMat, tris: cv2.UMat, color: cv2.typing.Scalar, type: int = ..., cullBackface: bool = ...) -> cv2.UMat: ...

@_typing.overload
def extractControlPoints(num: int, len: int, pts3d: cv2.typing.MatLike, rvec: cv2.typing.MatLike, tvec: cv2.typing.MatLike, K: cv2.typing.MatLike, imsize: cv2.typing.Size, tris: cv2.typing.MatLike, ctl2d: cv2.typing.MatLike | None = ..., ctl3d: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def extractControlPoints(num: int, len: int, pts3d: cv2.UMat, rvec: cv2.UMat, tvec: cv2.UMat, K: cv2.UMat, imsize: cv2.typing.Size, tris: cv2.UMat, ctl2d: cv2.UMat | None = ..., ctl3d: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def extractLineBundle(len: int, ctl2d: cv2.typing.MatLike, img: cv2.typing.MatLike, bundle: cv2.typing.MatLike | None = ..., srcLocations: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def extractLineBundle(len: int, ctl2d: cv2.UMat, img: cv2.UMat, bundle: cv2.UMat | None = ..., srcLocations: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def findCorrespondencies(bundle: cv2.typing.MatLike, cols: cv2.typing.MatLike | None = ..., response: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def findCorrespondencies(bundle: cv2.UMat, cols: cv2.UMat | None = ..., response: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def rapid(img: cv2.typing.MatLike, num: int, len: int, pts3d: cv2.typing.MatLike, tris: cv2.typing.MatLike, K: cv2.typing.MatLike, rvec: cv2.typing.MatLike, tvec: cv2.typing.MatLike) -> tuple[float, cv2.typing.MatLike, cv2.typing.MatLike, float]: ...
@_typing.overload
def rapid(img: cv2.UMat, num: int, len: int, pts3d: cv2.UMat, tris: cv2.UMat, K: cv2.UMat, rvec: cv2.UMat, tvec: cv2.UMat) -> tuple[float, cv2.UMat, cv2.UMat, float]: ...


