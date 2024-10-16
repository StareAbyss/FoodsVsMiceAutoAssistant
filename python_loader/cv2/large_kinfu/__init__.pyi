__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Classes
class Params:
    frameSize: cv2.typing.Size
    intr: cv2.typing.Matx33f
    rgb_intr: cv2.typing.Matx33f
    depthFactor: float
    bilateral_sigma_depth: float
    bilateral_sigma_spatial: float
    bilateral_kernel_size: int
    pyramidLevels: int
    tsdf_min_camera_movement: float
    lightPose: cv2.typing.Vec3f
    icpDistThresh: float
    icpAngleThresh: float
    icpIterations: _typing.Sequence[int]
    truncateThreshold: float

    # Functions
    @classmethod
    def defaultParams(cls) -> Params: ...

    @classmethod
    def coarseParams(cls) -> Params: ...

    @classmethod
    def hashTSDFParams(cls, isCoarse: bool) -> Params: ...


class LargeKinfu:
    # Functions
    @classmethod
    def create(cls, _params: Params) -> LargeKinfu: ...

    @_typing.overload
    def render(self, image: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def render(self, image: cv2.UMat | None = ...) -> cv2.UMat: ...
    @_typing.overload
    def render(self, cameraPose: cv2.typing.Matx44f, image: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def render(self, cameraPose: cv2.typing.Matx44f, image: cv2.UMat | None = ...) -> cv2.UMat: ...

    @_typing.overload
    def getCloud(self, points: cv2.typing.MatLike | None = ..., normals: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
    @_typing.overload
    def getCloud(self, points: cv2.UMat | None = ..., normals: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

    @_typing.overload
    def getPoints(self, points: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def getPoints(self, points: cv2.UMat | None = ...) -> cv2.UMat: ...

    @_typing.overload
    def getNormals(self, points: cv2.typing.MatLike, normals: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def getNormals(self, points: cv2.UMat, normals: cv2.UMat | None = ...) -> cv2.UMat: ...

    def reset(self) -> None: ...

    @_typing.overload
    def update(self, depth: cv2.typing.MatLike) -> bool: ...
    @_typing.overload
    def update(self, depth: cv2.UMat) -> bool: ...



