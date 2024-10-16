__all__: list[str] = []

import cv2.typing


# Enumerations
CV_SPECKLE_REMOVAL_ALGORITHM: int
CV_SPECKLE_REMOVAL_AVG_ALGORITHM: int
CV_QUADRATIC_INTERPOLATION: int
CV_SIMETRICV_INTERPOLATION: int
CV_DENSE_CENSUS: int
CV_SPARSE_CENSUS: int
CV_CS_CENSUS: int
CV_MODIFIED_CS_CENSUS: int
CV_MODIFIED_CENSUS_TRANSFORM: int
CV_MEAN_VARIATION: int
CV_STAR_KERNEL: int


StereoMatcher_DISP_SHIFT: int
STEREO_MATCHER_DISP_SHIFT: int
StereoMatcher_DISP_SCALE: int
STEREO_MATCHER_DISP_SCALE: int

StereoBinaryBM_PREFILTER_NORMALIZED_RESPONSE: int
STEREO_BINARY_BM_PREFILTER_NORMALIZED_RESPONSE: int
StereoBinaryBM_PREFILTER_XSOBEL: int
STEREO_BINARY_BM_PREFILTER_XSOBEL: int

StereoBinarySGBM_MODE_SGBM: int
STEREO_BINARY_SGBM_MODE_SGBM: int
StereoBinarySGBM_MODE_HH: int
STEREO_BINARY_SGBM_MODE_HH: int


# Classes
class MatchQuasiDense:
    p0: cv2.typing.Point2i
    p1: cv2.typing.Point2i
    corr: float

    # Functions
    def __init__(self) -> None: ...

    def apply(self, rhs: MatchQuasiDense) -> bool: ...


class PropagationParameters:
    corrWinSizeX: int
    corrWinSizeY: int
    borderX: int
    borderY: int
    correlationThreshold: float
    textrureThreshold: float
    neighborhoodSize: int
    disparityGradient: int
    lkTemplateSize: int
    lkPyrLvl: int
    lkTermParam1: int
    lkTermParam2: float
    gftQualityThres: float
    gftMinSeperationDist: int
    gftMaxNumFeatures: int

class QuasiDenseStereo:
    Param: PropagationParameters

    # Functions
    def loadParameters(self, filepath: str) -> int: ...

    def saveParameters(self, filepath: str) -> int: ...

    def getSparseMatches(self) -> _typing.Sequence[MatchQuasiDense]: ...

    def getDenseMatches(self) -> _typing.Sequence[MatchQuasiDense]: ...

    def process(self, imgLeft: cv2.typing.MatLike, imgRight: cv2.typing.MatLike) -> None: ...

    def getMatch(self, x: int, y: int) -> cv2.typing.Point2f: ...

    def getDisparity(self) -> cv2.typing.MatLike: ...

    @classmethod
    def create(cls, monoImgSize: cv2.typing.Size, paramFilepath: str = ...) -> QuasiDenseStereo: ...



