__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Enumerations
FTP: int
PSP: int
FAPS: int
DECODE_3D_UNDERWORLD: int



# Classes
class GrayCodePattern(StructuredLightPattern):
    # Functions
    @classmethod
    def create(cls, width: int, height: int) -> GrayCodePattern: ...

    def getNumberOfPatternImages(self) -> int: ...

    def setWhiteThreshold(self, value: int) -> None: ...

    def setBlackThreshold(self, value: int) -> None: ...

    @_typing.overload
    def getImagesForShadowMasks(self, blackImage: cv2.typing.MatLike, whiteImage: cv2.typing.MatLike) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
    @_typing.overload
    def getImagesForShadowMasks(self, blackImage: cv2.UMat, whiteImage: cv2.UMat) -> tuple[cv2.UMat, cv2.UMat]: ...

    @_typing.overload
    def getProjPixel(self, patternImages: _typing.Sequence[cv2.typing.MatLike], x: int, y: int) -> tuple[bool, cv2.typing.Point]: ...
    @_typing.overload
    def getProjPixel(self, patternImages: _typing.Sequence[cv2.UMat], x: int, y: int) -> tuple[bool, cv2.typing.Point]: ...


class StructuredLightPattern(cv2.Algorithm):
    # Functions
    @_typing.overload
    def generate(self, patternImages: _typing.Sequence[cv2.typing.MatLike] | None = ...) -> tuple[bool, _typing.Sequence[cv2.typing.MatLike]]: ...
    @_typing.overload
    def generate(self, patternImages: _typing.Sequence[cv2.UMat] | None = ...) -> tuple[bool, _typing.Sequence[cv2.UMat]]: ...

    @_typing.overload
    def decode(self, patternImages: _typing.Sequence[_typing.Sequence[cv2.typing.MatLike]], disparityMap: cv2.typing.MatLike | None = ..., blackImages: _typing.Sequence[cv2.typing.MatLike] | None = ..., whiteImages: _typing.Sequence[cv2.typing.MatLike] | None = ..., flags: int = ...) -> tuple[bool, cv2.typing.MatLike]: ...
    @_typing.overload
    def decode(self, patternImages: _typing.Sequence[_typing.Sequence[cv2.typing.MatLike]], disparityMap: cv2.UMat | None = ..., blackImages: _typing.Sequence[cv2.UMat] | None = ..., whiteImages: _typing.Sequence[cv2.UMat] | None = ..., flags: int = ...) -> tuple[bool, cv2.UMat]: ...


class SinusoidalPattern(StructuredLightPattern):
    # Classes
    class Params:
        width: int
        height: int
        nbrOfPeriods: int
        shiftValue: float
        methodId: int
        nbrOfPixelsBetweenMarkers: int
        horizontal: bool
        setMarkers: bool

        # Functions
        def __init__(self) -> None: ...



    # Functions
    @classmethod
    def create(cls, parameters: SinusoidalPattern.Params = ...) -> SinusoidalPattern: ...

    @_typing.overload
    def computePhaseMap(self, patternImages: _typing.Sequence[cv2.typing.MatLike], wrappedPhaseMap: cv2.typing.MatLike | None = ..., shadowMask: cv2.typing.MatLike | None = ..., fundamental: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
    @_typing.overload
    def computePhaseMap(self, patternImages: _typing.Sequence[cv2.UMat], wrappedPhaseMap: cv2.UMat | None = ..., shadowMask: cv2.UMat | None = ..., fundamental: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

    @_typing.overload
    def unwrapPhaseMap(self, wrappedPhaseMap: cv2.typing.MatLike, camSize: cv2.typing.Size, unwrappedPhaseMap: cv2.typing.MatLike | None = ..., shadowMask: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def unwrapPhaseMap(self, wrappedPhaseMap: cv2.UMat, camSize: cv2.typing.Size, unwrappedPhaseMap: cv2.UMat | None = ..., shadowMask: cv2.UMat | None = ...) -> cv2.UMat: ...

    @_typing.overload
    def findProCamMatches(self, projUnwrappedPhaseMap: cv2.typing.MatLike, camUnwrappedPhaseMap: cv2.typing.MatLike, matches: _typing.Sequence[cv2.typing.MatLike] | None = ...) -> _typing.Sequence[cv2.typing.MatLike]: ...
    @_typing.overload
    def findProCamMatches(self, projUnwrappedPhaseMap: cv2.UMat, camUnwrappedPhaseMap: cv2.UMat, matches: _typing.Sequence[cv2.UMat] | None = ...) -> _typing.Sequence[cv2.UMat]: ...

    @_typing.overload
    def computeDataModulationTerm(self, patternImages: _typing.Sequence[cv2.typing.MatLike], shadowMask: cv2.typing.MatLike, dataModulationTerm: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def computeDataModulationTerm(self, patternImages: _typing.Sequence[cv2.UMat], shadowMask: cv2.UMat, dataModulationTerm: cv2.UMat | None = ...) -> cv2.UMat: ...



