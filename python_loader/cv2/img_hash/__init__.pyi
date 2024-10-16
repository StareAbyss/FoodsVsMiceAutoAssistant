__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Enumerations
BLOCK_MEAN_HASH_MODE_0: int
BLOCK_MEAN_HASH_MODE_1: int
BlockMeanHashMode = int
"""One of [BLOCK_MEAN_HASH_MODE_0, BLOCK_MEAN_HASH_MODE_1]"""



# Classes
class AverageHash(ImgHashBase):
    # Functions
    @classmethod
    def create(cls) -> AverageHash: ...


class ImgHashBase(cv2.Algorithm):
    # Functions
    @_typing.overload
    def compute(self, inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def compute(self, inputArr: cv2.UMat, outputArr: cv2.UMat | None = ...) -> cv2.UMat: ...

    @_typing.overload
    def compare(self, hashOne: cv2.typing.MatLike, hashTwo: cv2.typing.MatLike) -> float: ...
    @_typing.overload
    def compare(self, hashOne: cv2.UMat, hashTwo: cv2.UMat) -> float: ...


class BlockMeanHash(ImgHashBase):
    # Functions
    def setMode(self, mode: int) -> None: ...

    def getMean(self) -> _typing.Sequence[float]: ...

    @classmethod
    def create(cls, mode: int = ...) -> BlockMeanHash: ...


class ColorMomentHash(ImgHashBase):
    # Functions
    @classmethod
    def create(cls) -> ColorMomentHash: ...


class MarrHildrethHash(ImgHashBase):
    # Functions
    def getAlpha(self) -> float: ...

    def getScale(self) -> float: ...

    def setKernelParam(self, alpha: float, scale: float) -> None: ...

    @classmethod
    def create(cls, alpha: float = ..., scale: float = ...) -> MarrHildrethHash: ...


class PHash(ImgHashBase):
    # Functions
    @classmethod
    def create(cls) -> PHash: ...


class RadialVarianceHash(ImgHashBase):
    # Functions
    @classmethod
    def create(cls, sigma: float = ..., numOfAngleLine: int = ...) -> RadialVarianceHash: ...

    def getNumOfAngleLine(self) -> int: ...

    def getSigma(self) -> float: ...

    def setNumOfAngleLine(self, value: int) -> None: ...

    def setSigma(self, value: float) -> None: ...



# Functions
@_typing.overload
def averageHash(inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def averageHash(inputArr: cv2.UMat, outputArr: cv2.UMat | None = ...) -> cv2.UMat: ...

@_typing.overload
def blockMeanHash(inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ..., mode: int = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def blockMeanHash(inputArr: cv2.UMat, outputArr: cv2.UMat | None = ..., mode: int = ...) -> cv2.UMat: ...

@_typing.overload
def colorMomentHash(inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def colorMomentHash(inputArr: cv2.UMat, outputArr: cv2.UMat | None = ...) -> cv2.UMat: ...

@_typing.overload
def marrHildrethHash(inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ..., alpha: float = ..., scale: float = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def marrHildrethHash(inputArr: cv2.UMat, outputArr: cv2.UMat | None = ..., alpha: float = ..., scale: float = ...) -> cv2.UMat: ...

@_typing.overload
def pHash(inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def pHash(inputArr: cv2.UMat, outputArr: cv2.UMat | None = ...) -> cv2.UMat: ...

@_typing.overload
def radialVarianceHash(inputArr: cv2.typing.MatLike, outputArr: cv2.typing.MatLike | None = ..., sigma: float = ..., numOfAngleLine: int = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def radialVarianceHash(inputArr: cv2.UMat, outputArr: cv2.UMat | None = ..., sigma: float = ..., numOfAngleLine: int = ...) -> cv2.UMat: ...


