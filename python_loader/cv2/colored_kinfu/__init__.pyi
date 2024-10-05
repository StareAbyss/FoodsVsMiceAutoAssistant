__all__: list[str] = []

import cv2
import cv2.kinfu
import cv2.typing
import typing as _typing


# Classes
class Params:
    frameSize: cv2.typing.Size
    rgb_frameSize: cv2.typing.Size
    volumeType: cv2.kinfu.VolumeType
    intr: cv2.typing.Matx33f
    rgb_intr: cv2.typing.Matx33f
    depthFactor: float
    bilateral_sigma_depth: float
    bilateral_sigma_spatial: float
    bilateral_kernel_size: int
    pyramidLevels: int
    volumeDims: cv2.typing.Vec3i
    voxelSize: float
    tsdf_min_camera_movement: float
    tsdf_trunc_dist: float
    tsdf_max_weight: int
    raycast_step_factor: float
    lightPose: cv2.typing.Vec3f
    icpDistThresh: float
    icpAngleThresh: float
    icpIterations: _typing.Sequence[int]
    truncateThreshold: float

    # Functions
    @_typing.overload
    def __init__(self) -> None: ...
    @_typing.overload
    def __init__(self, volumeInitialPoseRot: cv2.typing.Matx33f, volumeInitialPoseTransl: cv2.typing.Vec3f) -> None: ...
    @_typing.overload
    def __init__(self, volumeInitialPose: cv2.typing.Matx44f) -> None: ...

    @_typing.overload
    def setInitialVolumePose(self, R: cv2.typing.Matx33f, t: cv2.typing.Vec3f) -> None: ...
    @_typing.overload
    def setInitialVolumePose(self, homogen_tf: cv2.typing.Matx44f) -> None: ...

    @classmethod
    def defaultParams(cls) -> Params: ...

    @classmethod
    def coarseParams(cls) -> Params: ...

    @classmethod
    def hashTSDFParams(cls, isCoarse: bool) -> Params: ...

    @classmethod
    def coloredTSDFParams(cls, isCoarse: bool) -> Params: ...


class ColoredKinFu:
    # Functions
    @classmethod
    def create(cls, _params: Params) -> ColoredKinFu: ...

    @_typing.overload
    def render(self, image: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def render(self, image: cv2.UMat | None = ...) -> cv2.UMat: ...
    @_typing.overload
    def render(self, cameraPose: cv2.typing.Matx44f, image: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
    @_typing.overload
    def render(self, cameraPose: cv2.typing.Matx44f, image: cv2.UMat | None = ...) -> cv2.UMat: ...

    @_typing.overload
    def getCloud(self, points: cv2.typing.MatLike | None = ..., normals: cv2.typing.MatLike | None = ..., colors: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike]: ...
    @_typing.overload
    def getCloud(self, points: cv2.UMat | None = ..., normals: cv2.UMat | None = ..., colors: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat, cv2.UMat]: ...

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
    def update(self, depth: cv2.typing.MatLike, rgb: cv2.typing.MatLike) -> bool: ...
    @_typing.overload
    def update(self, depth: cv2.UMat, rgb: cv2.UMat) -> bool: ...



