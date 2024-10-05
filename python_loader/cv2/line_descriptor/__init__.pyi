__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Classes
class KeyLine:
    angle: float
    class_id: int
    octave: int
    pt: cv2.typing.Point2f
    response: float
    size: float
    startPointX: float
    startPointY: float
    endPointX: float
    endPointY: float
    sPointInOctaveX: float
    sPointInOctaveY: float
    ePointInOctaveX: float
    ePointInOctaveY: float
    lineLength: float
    numOfPixels: int

    # Functions
    def __init__(self) -> None: ...

    def getStartPoint(self) -> cv2.typing.Point2f: ...

    def getEndPoint(self) -> cv2.typing.Point2f: ...

    def getStartPointInOctave(self) -> cv2.typing.Point2f: ...

    def getEndPointInOctave(self) -> cv2.typing.Point2f: ...


class BinaryDescriptor(cv2.Algorithm):
    # Functions
    @classmethod
    def createBinaryDescriptor(cls) -> BinaryDescriptor: ...

    def getNumOfOctaves(self) -> int: ...

    def setNumOfOctaves(self, octaves: int) -> None: ...

    def getWidthOfBand(self) -> int: ...

    def setWidthOfBand(self, width: int) -> None: ...

    def getReductionRatio(self) -> int: ...

    def setReductionRatio(self, rRatio: int) -> None: ...

    def detect(self, image: cv2.typing.MatLike, mask: cv2.typing.MatLike | None = ...) -> _typing.Sequence[KeyLine]: ...

    def compute(self, image: cv2.typing.MatLike, keylines: _typing.Sequence[KeyLine], descriptors: cv2.typing.MatLike | None = ..., returnFloatDescr: bool = ...) -> tuple[_typing.Sequence[KeyLine], cv2.typing.MatLike]: ...


class LSDParam:
    scale: float
    sigma_scale: float
    quant: float
    ang_th: float
    log_eps: float
    density_th: float
    n_bins: int

    # Functions
    def __init__(self) -> None: ...


class LSDDetector(cv2.Algorithm):
    # Functions
    def __init__(self, _params: LSDParam) -> None: ...

    @classmethod
    def createLSDDetector(cls) -> LSDDetector: ...

    @classmethod
    def createLSDDetectorWithParams(cls, params: LSDParam) -> LSDDetector: ...

    @_typing.overload
    def detect(self, image: cv2.typing.MatLike, scale: int, numOctaves: int, mask: cv2.typing.MatLike | None = ...) -> _typing.Sequence[KeyLine]: ...
    @_typing.overload
    def detect(self, images: _typing.Sequence[cv2.typing.MatLike], keylines: _typing.Sequence[_typing.Sequence[KeyLine]], scale: int, numOctaves: int, masks: _typing.Sequence[cv2.typing.MatLike] | None = ...) -> None: ...


class BinaryDescriptorMatcher(cv2.Algorithm):
    # Functions
    def __init__(self) -> None: ...

    def match(self, queryDescriptors: cv2.typing.MatLike, trainDescriptors: cv2.typing.MatLike, mask: cv2.typing.MatLike | None = ...) -> _typing.Sequence[cv2.DMatch]: ...

    def matchQuery(self, queryDescriptors: cv2.typing.MatLike, masks: _typing.Sequence[cv2.typing.MatLike] | None = ...) -> _typing.Sequence[cv2.DMatch]: ...

    def knnMatch(self, queryDescriptors: cv2.typing.MatLike, trainDescriptors: cv2.typing.MatLike, k: int, mask: cv2.typing.MatLike | None = ..., compactResult: bool = ...) -> _typing.Sequence[_typing.Sequence[cv2.DMatch]]: ...

    def knnMatchQuery(self, queryDescriptors: cv2.typing.MatLike, matches: _typing.Sequence[_typing.Sequence[cv2.DMatch]], k: int, masks: _typing.Sequence[cv2.typing.MatLike] | None = ..., compactResult: bool = ...) -> None: ...


class DrawLinesMatchesFlags:
    ...


# Functions
def drawKeylines(image: cv2.typing.MatLike, keylines: _typing.Sequence[KeyLine], outImage: cv2.typing.MatLike | None = ..., color: cv2.typing.Scalar = ..., flags: int = ...) -> cv2.typing.MatLike: ...

def drawLineMatches(img1: cv2.typing.MatLike, keylines1: _typing.Sequence[KeyLine], img2: cv2.typing.MatLike, keylines2: _typing.Sequence[KeyLine], matches1to2: _typing.Sequence[cv2.DMatch], outImg: cv2.typing.MatLike | None = ..., matchColor: cv2.typing.Scalar = ..., singleLineColor: cv2.typing.Scalar = ..., matchesMask: _typing.Sequence[str] = ..., flags: int = ...) -> cv2.typing.MatLike: ...


