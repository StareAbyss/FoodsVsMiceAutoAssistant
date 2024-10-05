__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Classes
class WeChatQRCode:
    # Functions
    def __init__(self, detector_prototxt_path: str = ..., detector_caffe_model_path: str = ..., super_resolution_prototxt_path: str = ..., super_resolution_caffe_model_path: str = ...) -> None: ...

    @_typing.overload
    def detectAndDecode(self, img: cv2.typing.MatLike, points: _typing.Sequence[cv2.typing.MatLike] | None = ...) -> tuple[_typing.Sequence[str], _typing.Sequence[cv2.typing.MatLike]]: ...
    @_typing.overload
    def detectAndDecode(self, img: cv2.UMat, points: _typing.Sequence[cv2.UMat] | None = ...) -> tuple[_typing.Sequence[str], _typing.Sequence[cv2.UMat]]: ...

    def setScaleFactor(self, _scalingFactor: float) -> None: ...

    def getScaleFactor(self) -> float: ...



