__all__: list[str] = []

import cv2
import cv2.dnn
import cv2.typing
import typing as _typing


# Enumerations
MCC24: int
SG140: int
VINYL18: int
TYPECHART = int
"""One of [MCC24, SG140, VINYL18]"""



# Classes
class DetectorParameters:
    adaptiveThreshWinSizeMin: int
    adaptiveThreshWinSizeMax: int
    adaptiveThreshWinSizeStep: int
    adaptiveThreshConstant: float
    minContoursAreaRate: float
    minContoursArea: float
    confidenceThreshold: float
    minContourSolidity: float
    findCandidatesApproxPolyDPEpsMultiplier: float
    borderWidth: int
    B0factor: float
    maxError: float
    minContourPointsAllowed: int
    minContourLengthAllowed: int
    minInterContourDistance: int
    minInterCheckerDistance: int
    minImageSize: int
    minGroupSize: int

    # Functions
    @classmethod
    def create(cls) -> DetectorParameters: ...


class CCheckerDetector(cv2.Algorithm):
    # Functions
    def setNet(self, net: cv2.dnn.Net) -> bool: ...

    @_typing.overload
    def processWithROI(self, image: cv2.typing.MatLike, chartType: TYPECHART, regionsOfInterest: _typing.Sequence[cv2.typing.Rect], nc: int = ..., useNet: bool = ..., params: DetectorParameters = ...) -> bool: ...
    @_typing.overload
    def processWithROI(self, image: cv2.UMat, chartType: TYPECHART, regionsOfInterest: _typing.Sequence[cv2.typing.Rect], nc: int = ..., useNet: bool = ..., params: DetectorParameters = ...) -> bool: ...

    @_typing.overload
    def process(self, image: cv2.typing.MatLike, chartType: TYPECHART, nc: int = ..., useNet: bool = ..., params: DetectorParameters = ...) -> bool: ...
    @_typing.overload
    def process(self, image: cv2.UMat, chartType: TYPECHART, nc: int = ..., useNet: bool = ..., params: DetectorParameters = ...) -> bool: ...

    def getBestColorChecker(self) -> CChecker: ...

    def getListColorChecker(self) -> _typing.Sequence[CChecker]: ...

    @classmethod
    def create(cls) -> CCheckerDetector: ...


class CChecker:
    # Functions
    @classmethod
    def create(cls) -> CChecker: ...

    def setTarget(self, _target: TYPECHART) -> None: ...

    def setBox(self, _box: _typing.Sequence[cv2.typing.Point2f]) -> None: ...

    def setChartsRGB(self, _chartsRGB: cv2.typing.MatLike) -> None: ...

    def setChartsYCbCr(self, _chartsYCbCr: cv2.typing.MatLike) -> None: ...

    def setCost(self, _cost: float) -> None: ...

    def setCenter(self, _center: cv2.typing.Point2f) -> None: ...

    def getTarget(self) -> TYPECHART: ...

    def getBox(self) -> _typing.Sequence[cv2.typing.Point2f]: ...

    def getColorCharts(self) -> _typing.Sequence[cv2.typing.Point2f]: ...

    def getChartsRGB(self) -> cv2.typing.MatLike: ...

    def getChartsYCbCr(self) -> cv2.typing.MatLike: ...

    def getCost(self) -> float: ...

    def getCenter(self) -> cv2.typing.Point2f: ...


class CCheckerDraw:
    # Functions
    @_typing.overload
    def draw(self, img: cv2.typing.MatLike) -> cv2.typing.MatLike: ...
    @_typing.overload
    def draw(self, img: cv2.UMat) -> cv2.UMat: ...

    @classmethod
    def create(cls, pChecker: CChecker, color: cv2.typing.Scalar = ..., thickness: int = ...) -> CCheckerDraw: ...



