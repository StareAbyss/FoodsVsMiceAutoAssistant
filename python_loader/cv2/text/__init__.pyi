__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Enumerations
ERFILTER_NM_RGBLGrad: int
ERFILTER_NM_RGBLGRAD: int
ERFILTER_NM_IHSGrad: int
ERFILTER_NM_IHSGRAD: int
OCR_LEVEL_WORD: int
OCR_LEVEL_TEXTLINE: int

ERGROUPING_ORIENTATION_HORIZ: int
ERGROUPING_ORIENTATION_ANY: int
erGrouping_Modes = int
"""One of [ERGROUPING_ORIENTATION_HORIZ, ERGROUPING_ORIENTATION_ANY]"""

PSM_OSD_ONLY: int
PSM_AUTO_OSD: int
PSM_AUTO_ONLY: int
PSM_AUTO: int
PSM_SINGLE_COLUMN: int
PSM_SINGLE_BLOCK_VERT_TEXT: int
PSM_SINGLE_BLOCK: int
PSM_SINGLE_LINE: int
PSM_SINGLE_WORD: int
PSM_CIRCLE_WORD: int
PSM_SINGLE_CHAR: int
page_seg_mode = int
"""One of [PSM_OSD_ONLY, PSM_AUTO_OSD, PSM_AUTO_ONLY, PSM_AUTO, PSM_SINGLE_COLUMN, PSM_SINGLE_BLOCK_VERT_TEXT, PSM_SINGLE_BLOCK, PSM_SINGLE_LINE, PSM_SINGLE_WORD, PSM_CIRCLE_WORD, PSM_SINGLE_CHAR]"""

OEM_TESSERACT_ONLY: int
OEM_CUBE_ONLY: int
OEM_TESSERACT_CUBE_COMBINED: int
OEM_DEFAULT: int
ocr_engine_mode = int
"""One of [OEM_TESSERACT_ONLY, OEM_CUBE_ONLY, OEM_TESSERACT_CUBE_COMBINED, OEM_DEFAULT]"""

OCR_DECODER_VITERBI: int
decoder_mode = int
"""One of [OCR_DECODER_VITERBI]"""

OCR_KNN_CLASSIFIER: int
OCR_CNN_CLASSIFIER: int
classifier_type = int
"""One of [OCR_KNN_CLASSIFIER, OCR_CNN_CLASSIFIER]"""



# Classes
class ERFilter(cv2.Algorithm):
    # Classes
    class Callback:
        ...


class BaseOCR:
    ...

class OCRTesseract(BaseOCR):
    # Functions
    @_typing.overload
    def run(self, image: cv2.typing.MatLike, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.UMat, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.typing.MatLike, mask: cv2.typing.MatLike, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.UMat, mask: cv2.UMat, min_confidence: int, component_level: int = ...) -> str: ...

    def setWhiteList(self, char_whitelist: str) -> None: ...

    @classmethod
    def create(cls, datapath: str = ..., language: str = ..., char_whitelist: str = ..., oem: int = ..., psmode: int = ...) -> OCRTesseract: ...


class OCRHMMDecoder(BaseOCR):
    # Classes
    class ClassifierCallback:
        ...


    # Functions
    @_typing.overload
    def run(self, image: cv2.typing.MatLike, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.UMat, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.typing.MatLike, mask: cv2.typing.MatLike, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.UMat, mask: cv2.UMat, min_confidence: int, component_level: int = ...) -> str: ...

    @classmethod
    @_typing.overload
    def create(cls, classifier: OCRHMMDecoder.ClassifierCallback, vocabulary: str, transition_probabilities_table: cv2.typing.MatLike, emission_probabilities_table: cv2.typing.MatLike, mode: int = ...) -> OCRHMMDecoder: ...
    @classmethod
    @_typing.overload
    def create(cls, classifier: OCRHMMDecoder.ClassifierCallback, vocabulary: str, transition_probabilities_table: cv2.UMat, emission_probabilities_table: cv2.UMat, mode: int = ...) -> OCRHMMDecoder: ...
    @classmethod
    @_typing.overload
    def create(cls, filename: str, vocabulary: str, transition_probabilities_table: cv2.typing.MatLike, emission_probabilities_table: cv2.typing.MatLike, mode: int = ..., classifier: int = ...) -> OCRHMMDecoder: ...
    @classmethod
    @_typing.overload
    def create(cls, filename: str, vocabulary: str, transition_probabilities_table: cv2.UMat, emission_probabilities_table: cv2.UMat, mode: int = ..., classifier: int = ...) -> OCRHMMDecoder: ...


class OCRBeamSearchDecoder(BaseOCR):
    # Classes
    class ClassifierCallback:
        ...


    # Functions
    @_typing.overload
    def run(self, image: cv2.typing.MatLike, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.UMat, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.typing.MatLike, mask: cv2.typing.MatLike, min_confidence: int, component_level: int = ...) -> str: ...
    @_typing.overload
    def run(self, image: cv2.UMat, mask: cv2.UMat, min_confidence: int, component_level: int = ...) -> str: ...

    @classmethod
    @_typing.overload
    def create(cls, classifier: OCRBeamSearchDecoder.ClassifierCallback, vocabulary: str, transition_probabilities_table: cv2.typing.MatLike, emission_probabilities_table: cv2.typing.MatLike, mode: decoder_mode = ..., beam_size: int = ...) -> OCRBeamSearchDecoder: ...
    @classmethod
    @_typing.overload
    def create(cls, classifier: OCRBeamSearchDecoder.ClassifierCallback, vocabulary: str, transition_probabilities_table: cv2.UMat, emission_probabilities_table: cv2.UMat, mode: decoder_mode = ..., beam_size: int = ...) -> OCRBeamSearchDecoder: ...


class TextDetector:
    # Functions
    @_typing.overload
    def detect(self, inputImage: cv2.typing.MatLike) -> tuple[_typing.Sequence[cv2.typing.Rect], _typing.Sequence[float]]: ...
    @_typing.overload
    def detect(self, inputImage: cv2.UMat) -> tuple[_typing.Sequence[cv2.typing.Rect], _typing.Sequence[float]]: ...


class TextDetectorCNN(TextDetector):
    # Functions
    @_typing.overload
    def detect(self, inputImage: cv2.typing.MatLike) -> tuple[_typing.Sequence[cv2.typing.Rect], _typing.Sequence[float]]: ...
    @_typing.overload
    def detect(self, inputImage: cv2.UMat) -> tuple[_typing.Sequence[cv2.typing.Rect], _typing.Sequence[float]]: ...

    @classmethod
    def create(cls, modelArchFilename: str, modelWeightsFilename: str) -> TextDetectorCNN: ...



# Functions
@_typing.overload
def computeNMChannels(_src: cv2.typing.MatLike, _channels: _typing.Sequence[cv2.typing.MatLike] | None = ..., _mode: int = ...) -> _typing.Sequence[cv2.typing.MatLike]: ...
@_typing.overload
def computeNMChannels(_src: cv2.UMat, _channels: _typing.Sequence[cv2.UMat] | None = ..., _mode: int = ...) -> _typing.Sequence[cv2.UMat]: ...

@_typing.overload
def createERFilterNM1(cb: ERFilter.Callback, thresholdDelta: int = ..., minArea: float = ..., maxArea: float = ..., minProbability: float = ..., nonMaxSuppression: bool = ..., minProbabilityDiff: float = ...) -> ERFilter: ...
@_typing.overload
def createERFilterNM1(filename: str, thresholdDelta: int = ..., minArea: float = ..., maxArea: float = ..., minProbability: float = ..., nonMaxSuppression: bool = ..., minProbabilityDiff: float = ...) -> ERFilter: ...

@_typing.overload
def createERFilterNM2(cb: ERFilter.Callback, minProbability: float = ...) -> ERFilter: ...
@_typing.overload
def createERFilterNM2(filename: str, minProbability: float = ...) -> ERFilter: ...

def createOCRHMMTransitionsTable(vocabulary: str, lexicon: _typing.Sequence[str]) -> cv2.typing.MatLike: ...

@_typing.overload
def detectRegions(image: cv2.typing.MatLike, er_filter1: ERFilter, er_filter2: ERFilter) -> _typing.Sequence[_typing.Sequence[cv2.typing.Point]]: ...
@_typing.overload
def detectRegions(image: cv2.UMat, er_filter1: ERFilter, er_filter2: ERFilter) -> _typing.Sequence[_typing.Sequence[cv2.typing.Point]]: ...
@_typing.overload
def detectRegions(image: cv2.typing.MatLike, er_filter1: ERFilter, er_filter2: ERFilter, method: int = ..., filename: str = ..., minProbability: float = ...) -> _typing.Sequence[cv2.typing.Rect]: ...
@_typing.overload
def detectRegions(image: cv2.UMat, er_filter1: ERFilter, er_filter2: ERFilter, method: int = ..., filename: str = ..., minProbability: float = ...) -> _typing.Sequence[cv2.typing.Rect]: ...

@_typing.overload
def detectTextSWT(input: cv2.typing.MatLike, dark_on_light: bool, draw: cv2.typing.MatLike | None = ..., chainBBs: cv2.typing.MatLike | None = ...) -> tuple[_typing.Sequence[cv2.typing.Rect], cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def detectTextSWT(input: cv2.UMat, dark_on_light: bool, draw: cv2.UMat | None = ..., chainBBs: cv2.UMat | None = ...) -> tuple[_typing.Sequence[cv2.typing.Rect], cv2.UMat, cv2.UMat]: ...

@_typing.overload
def erGrouping(image: cv2.typing.MatLike, channel: cv2.typing.MatLike, regions: _typing.Sequence[_typing.Sequence[cv2.typing.Point]], method: int = ..., filename: str = ..., minProbablity: float = ...) -> _typing.Sequence[cv2.typing.Rect]: ...
@_typing.overload
def erGrouping(image: cv2.UMat, channel: cv2.UMat, regions: _typing.Sequence[_typing.Sequence[cv2.typing.Point]], method: int = ..., filename: str = ..., minProbablity: float = ...) -> _typing.Sequence[cv2.typing.Rect]: ...

def loadClassifierNM1(filename: str) -> ERFilter.Callback: ...

def loadClassifierNM2(filename: str) -> ERFilter.Callback: ...

def loadOCRBeamSearchClassifierCNN(filename: str) -> OCRBeamSearchDecoder.ClassifierCallback: ...

def loadOCRHMMClassifier(filename: str, classifier: int) -> OCRHMMDecoder.ClassifierCallback: ...

def loadOCRHMMClassifierCNN(filename: str) -> OCRHMMDecoder.ClassifierCallback: ...

def loadOCRHMMClassifierNM(filename: str) -> OCRHMMDecoder.ClassifierCallback: ...


