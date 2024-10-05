__all__: list[str] = []

import cv2
import cv2.cuda
import cv2.typing
import typing as _typing


# Enumerations
MPEG1: int
MPEG2: int
MPEG4: int
VC1: int
H264: int
JPEG: int
H264_SVC: int
H264_MVC: int
HEVC: int
VP8: int
VP9: int
AV1: int
NumCodecs: int
NUM_CODECS: int
Uncompressed_YUV420: int
UNCOMPRESSED_YUV420: int
Uncompressed_YV12: int
UNCOMPRESSED_YV12: int
Uncompressed_NV12: int
UNCOMPRESSED_NV12: int
Uncompressed_YUYV: int
UNCOMPRESSED_YUYV: int
Uncompressed_UYVY: int
UNCOMPRESSED_UYVY: int
Codec = int
"""One of [MPEG1, MPEG2, MPEG4, VC1, H264, JPEG, H264_SVC, H264_MVC, HEVC, VP8, VP9, AV1, NumCodecs, NUM_CODECS, Uncompressed_YUV420, UNCOMPRESSED_YUV420, Uncompressed_YV12, UNCOMPRESSED_YV12, Uncompressed_NV12, UNCOMPRESSED_NV12, Uncompressed_YUYV, UNCOMPRESSED_YUYV, Uncompressed_UYVY, UNCOMPRESSED_UYVY]"""

ColorFormat_UNDEFINED: int
COLOR_FORMAT_UNDEFINED: int
ColorFormat_BGRA: int
COLOR_FORMAT_BGRA: int
ColorFormat_BGR: int
COLOR_FORMAT_BGR: int
ColorFormat_GRAY: int
COLOR_FORMAT_GRAY: int
ColorFormat_NV_NV12: int
COLOR_FORMAT_NV_NV12: int
ColorFormat_RGB: int
COLOR_FORMAT_RGB: int
ColorFormat_RGBA: int
COLOR_FORMAT_RGBA: int
ColorFormat_NV_YV12: int
COLOR_FORMAT_NV_YV12: int
ColorFormat_NV_IYUV: int
COLOR_FORMAT_NV_IYUV: int
ColorFormat_NV_YUV444: int
COLOR_FORMAT_NV_YUV444: int
ColorFormat_NV_AYUV: int
COLOR_FORMAT_NV_AYUV: int
ColorFormat_PROP_NOT_SUPPORTED: int
COLOR_FORMAT_PROP_NOT_SUPPORTED: int
ColorFormat = int
"""One of [ColorFormat_UNDEFINED, COLOR_FORMAT_UNDEFINED, ColorFormat_BGRA, COLOR_FORMAT_BGRA, ColorFormat_BGR, COLOR_FORMAT_BGR, ColorFormat_GRAY, COLOR_FORMAT_GRAY, ColorFormat_NV_NV12, COLOR_FORMAT_NV_NV12, ColorFormat_RGB, COLOR_FORMAT_RGB, ColorFormat_RGBA, COLOR_FORMAT_RGBA, ColorFormat_NV_YV12, COLOR_FORMAT_NV_YV12, ColorFormat_NV_IYUV, COLOR_FORMAT_NV_IYUV, ColorFormat_NV_YUV444, COLOR_FORMAT_NV_YUV444, ColorFormat_NV_AYUV, COLOR_FORMAT_NV_AYUV, ColorFormat_PROP_NOT_SUPPORTED, COLOR_FORMAT_PROP_NOT_SUPPORTED]"""

ENC_PARAMS_RC_CONSTQP: int
ENC_PARAMS_RC_VBR: int
ENC_PARAMS_RC_CBR: int
EncodeParamsRcMode = int
"""One of [ENC_PARAMS_RC_CONSTQP, ENC_PARAMS_RC_VBR, ENC_PARAMS_RC_CBR]"""

ENC_MULTI_PASS_DISABLED: int
ENC_TWO_PASS_QUARTER_RESOLUTION: int
ENC_TWO_PASS_FULL_RESOLUTION: int
EncodeMultiPass = int
"""One of [ENC_MULTI_PASS_DISABLED, ENC_TWO_PASS_QUARTER_RESOLUTION, ENC_TWO_PASS_FULL_RESOLUTION]"""

ENC_CODEC_PROFILE_AUTOSELECT: int
ENC_H264_PROFILE_BASELINE: int
ENC_H264_PROFILE_MAIN: int
ENC_H264_PROFILE_HIGH: int
ENC_H264_PROFILE_HIGH_444: int
ENC_H264_PROFILE_STEREO: int
ENC_H264_PROFILE_PROGRESSIVE_HIGH: int
ENC_H264_PROFILE_CONSTRAINED_HIGH: int
ENC_HEVC_PROFILE_MAIN: int
ENC_HEVC_PROFILE_MAIN10: int
ENC_HEVC_PROFILE_FREXT: int
EncodeProfile = int
"""One of [ENC_CODEC_PROFILE_AUTOSELECT, ENC_H264_PROFILE_BASELINE, ENC_H264_PROFILE_MAIN, ENC_H264_PROFILE_HIGH, ENC_H264_PROFILE_HIGH_444, ENC_H264_PROFILE_STEREO, ENC_H264_PROFILE_PROGRESSIVE_HIGH, ENC_H264_PROFILE_CONSTRAINED_HIGH, ENC_HEVC_PROFILE_MAIN, ENC_HEVC_PROFILE_MAIN10, ENC_HEVC_PROFILE_FREXT]"""

ENC_PRESET_P1: int
ENC_PRESET_P2: int
ENC_PRESET_P3: int
ENC_PRESET_P4: int
ENC_PRESET_P5: int
ENC_PRESET_P6: int
ENC_PRESET_P7: int
EncodePreset = int
"""One of [ENC_PRESET_P1, ENC_PRESET_P2, ENC_PRESET_P3, ENC_PRESET_P4, ENC_PRESET_P5, ENC_PRESET_P6, ENC_PRESET_P7]"""

ENC_TUNING_INFO_UNDEFINED: int
ENC_TUNING_INFO_HIGH_QUALITY: int
ENC_TUNING_INFO_LOW_LATENCY: int
ENC_TUNING_INFO_ULTRA_LOW_LATENCY: int
ENC_TUNING_INFO_LOSSLESS: int
ENC_TUNING_INFO_COUNT: int
EncodeTuningInfo = int
"""One of [ENC_TUNING_INFO_UNDEFINED, ENC_TUNING_INFO_HIGH_QUALITY, ENC_TUNING_INFO_LOW_LATENCY, ENC_TUNING_INFO_ULTRA_LOW_LATENCY, ENC_TUNING_INFO_LOSSLESS, ENC_TUNING_INFO_COUNT]"""

Monochrome: int
MONOCHROME: int
YUV420: int
YUV422: int
YUV444: int
NumFormats: int
NUM_FORMATS: int
ChromaFormat = int
"""One of [Monochrome, MONOCHROME, YUV420, YUV422, YUV444, NumFormats, NUM_FORMATS]"""

Weave: int
WEAVE: int
Bob: int
BOB: int
Adaptive: int
ADAPTIVE: int
DeinterlaceMode = int
"""One of [Weave, WEAVE, Bob, BOB, Adaptive, ADAPTIVE]"""

VideoReaderProps_PROP_DECODED_FRAME_IDX: int
VIDEO_READER_PROPS_PROP_DECODED_FRAME_IDX: int
VideoReaderProps_PROP_EXTRA_DATA_INDEX: int
VIDEO_READER_PROPS_PROP_EXTRA_DATA_INDEX: int
VideoReaderProps_PROP_RAW_PACKAGES_BASE_INDEX: int
VIDEO_READER_PROPS_PROP_RAW_PACKAGES_BASE_INDEX: int
VideoReaderProps_PROP_NUMBER_OF_RAW_PACKAGES_SINCE_LAST_GRAB: int
VIDEO_READER_PROPS_PROP_NUMBER_OF_RAW_PACKAGES_SINCE_LAST_GRAB: int
VideoReaderProps_PROP_RAW_MODE: int
VIDEO_READER_PROPS_PROP_RAW_MODE: int
VideoReaderProps_PROP_LRF_HAS_KEY_FRAME: int
VIDEO_READER_PROPS_PROP_LRF_HAS_KEY_FRAME: int
VideoReaderProps_PROP_COLOR_FORMAT: int
VIDEO_READER_PROPS_PROP_COLOR_FORMAT: int
VideoReaderProps_PROP_UDP_SOURCE: int
VIDEO_READER_PROPS_PROP_UDP_SOURCE: int
VideoReaderProps_PROP_ALLOW_FRAME_DROP: int
VIDEO_READER_PROPS_PROP_ALLOW_FRAME_DROP: int
VideoReaderProps_PROP_NOT_SUPPORTED: int
VIDEO_READER_PROPS_PROP_NOT_SUPPORTED: int
VideoReaderProps = int
"""One of [VideoReaderProps_PROP_DECODED_FRAME_IDX, VIDEO_READER_PROPS_PROP_DECODED_FRAME_IDX, VideoReaderProps_PROP_EXTRA_DATA_INDEX, VIDEO_READER_PROPS_PROP_EXTRA_DATA_INDEX, VideoReaderProps_PROP_RAW_PACKAGES_BASE_INDEX, VIDEO_READER_PROPS_PROP_RAW_PACKAGES_BASE_INDEX, VideoReaderProps_PROP_NUMBER_OF_RAW_PACKAGES_SINCE_LAST_GRAB, VIDEO_READER_PROPS_PROP_NUMBER_OF_RAW_PACKAGES_SINCE_LAST_GRAB, VideoReaderProps_PROP_RAW_MODE, VIDEO_READER_PROPS_PROP_RAW_MODE, VideoReaderProps_PROP_LRF_HAS_KEY_FRAME, VIDEO_READER_PROPS_PROP_LRF_HAS_KEY_FRAME, VideoReaderProps_PROP_COLOR_FORMAT, VIDEO_READER_PROPS_PROP_COLOR_FORMAT, VideoReaderProps_PROP_UDP_SOURCE, VIDEO_READER_PROPS_PROP_UDP_SOURCE, VideoReaderProps_PROP_ALLOW_FRAME_DROP, VIDEO_READER_PROPS_PROP_ALLOW_FRAME_DROP, VideoReaderProps_PROP_NOT_SUPPORTED, VIDEO_READER_PROPS_PROP_NOT_SUPPORTED]"""



# Classes
class EncodeQp:
    qpInterP: int
    qpInterB: int
    qpIntra: int

class EncoderParams:
    nvPreset: EncodePreset
    tuningInfo: EncodeTuningInfo
    encodingProfile: EncodeProfile
    rateControlMode: EncodeParamsRcMode
    multiPassEncoding: EncodeMultiPass
    constQp: EncodeQp
    averageBitRate: int
    maxBitRate: int
    targetQuality: int
    gopLength: int
    idrPeriod: int

    # Functions
    def __init__(self) -> None: ...


class EncoderCallback:
    ...

class VideoWriter:
    # Functions
    @_typing.overload
    def write(self, frame: cv2.typing.MatLike) -> None: ...
    @_typing.overload
    def write(self, frame: cv2.cuda.GpuMat) -> None: ...
    @_typing.overload
    def write(self, frame: cv2.UMat) -> None: ...

    def getEncoderParams(self) -> EncoderParams: ...

    def release(self) -> None: ...


class FormatInfo:
    codec: Codec
    chromaFormat: ChromaFormat
    nBitDepthMinus8: int
    nBitDepthChromaMinus8: int
    ulWidth: int
    ulHeight: int
    width: int
    height: int
    displayArea: cv2.typing.Rect
    valid: bool
    fps: float
    ulNumDecodeSurfaces: int
    deinterlaceMode: DeinterlaceMode
    targetSz: cv2.typing.Size
    srcRoi: cv2.typing.Rect
    targetRoi: cv2.typing.Rect
    videoFullRangeFlag: bool
    enableHistogram: bool
    nCounterBitDepth: int
    nMaxHistogramBins: int

    # Functions
    def __init__(self) -> None: ...


class VideoReader:
    # Functions
    def nextFrame(self, frame: cv2.cuda.GpuMat | None = ..., stream: cv2.cuda.Stream = ...) -> tuple[bool, cv2.cuda.GpuMat]: ...

    def nextFrameWithHist(self, frame: cv2.cuda.GpuMat | None = ..., histogram: cv2.cuda.GpuMat | None = ..., stream: cv2.cuda.Stream = ...) -> tuple[bool, cv2.cuda.GpuMat, cv2.cuda.GpuMat]: ...

    def format(self) -> FormatInfo: ...

    def grab(self, stream: cv2.cuda.Stream = ...) -> bool: ...

    @_typing.overload
    def retrieve(self, idx: int, frame: cv2.typing.MatLike | None = ...) -> tuple[bool, cv2.typing.MatLike]: ...
    @_typing.overload
    def retrieve(self, frame: cv2.cuda.GpuMat | None = ...) -> tuple[bool, cv2.cuda.GpuMat]: ...

    def setVideoReaderProps(self, propertyId: VideoReaderProps, propertyVal: float) -> bool: ...

    def set(self, colorFormat: ColorFormat) -> bool: ...

    def getVideoReaderProps(self, propertyId: VideoReaderProps, propertyValIn: float = ...) -> tuple[bool, float]: ...

    def get(self, propertyId: int) -> tuple[bool, float]: ...


class RawVideoSource:
    ...

class VideoReaderInitParams:
    udpSource: bool
    allowFrameDrop: bool
    minNumDecodeSurfaces: int
    rawMode: bool
    targetSz: cv2.typing.Size
    srcRoi: cv2.typing.Rect
    targetRoi: cv2.typing.Rect
    enableHistogram: bool
    firstFrameIdx: int

    # Functions
    def __init__(self) -> None: ...



# Functions
def MapHist(hist: cv2.cuda.GpuMat, histFull: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...

@_typing.overload
def createVideoReader(filename: str, sourceParams: _typing.Sequence[int] = ..., params: VideoReaderInitParams = ...) -> VideoReader: ...
@_typing.overload
def createVideoReader(source: RawVideoSource, params: VideoReaderInitParams = ...) -> VideoReader: ...

@_typing.overload
def createVideoWriter(fileName: str, frameSize: cv2.typing.Size, codec: Codec = ..., fps: float = ..., colorFormat: ColorFormat = ..., encoderCallback: EncoderCallback = ..., stream: cv2.cuda.Stream = ...) -> VideoWriter: ...
@_typing.overload
def createVideoWriter(fileName: str, frameSize: cv2.typing.Size, codec: Codec, fps: float, colorFormat: ColorFormat, params: EncoderParams, encoderCallback: EncoderCallback = ..., stream: cv2.cuda.Stream = ...) -> VideoWriter: ...


