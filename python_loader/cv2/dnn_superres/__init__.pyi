__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Classes
class DnnSuperResImpl:
    # Functions
    @classmethod
    def create(cls) -> DnnSuperResImpl: ...

    def readModel(self, path: str) -> None: ...

    def setModel(self, algo: str, scale: int) -> None: ...

    def setPreferableBackend(self, backendId: int) -> None: ...

    def setPreferableTarget(self, targetId: int) -> None: ...

    @_typing.overload
    def upsample(self, img: cv2.typing.MatLike, result: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def upsample(self, img: cv2.UMat, result: cv2.UMat | None = ...) -> cv2.UMat: ...

    @_typing.overload
    def upsampleMultioutput(self, img: cv2.typing.MatLike, imgs_new: _typing.Sequence[cv2.typing.MatLike], scale_factors: _typing.Sequence[int], node_names: _typing.Sequence[str]) -> None: ...
    @_typing.overload
    def upsampleMultioutput(self, img: cv2.UMat, imgs_new: _typing.Sequence[cv2.typing.MatLike], scale_factors: _typing.Sequence[int], node_names: _typing.Sequence[str]) -> None: ...

    def getScale(self) -> int: ...

    def getAlgorithm(self) -> str: ...



