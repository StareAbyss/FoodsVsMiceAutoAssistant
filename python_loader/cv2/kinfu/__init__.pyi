__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


from cv2.kinfu import detail as detail


# Enumerations
VolumeType_TSDF: int
VOLUME_TYPE_TSDF: int
VolumeType_HASHTSDF: int
VOLUME_TYPE_HASHTSDF: int
VolumeType_COLOREDTSDF: int
VOLUME_TYPE_COLOREDTSDF: int
VolumeType = int
"""One of [VolumeType_TSDF, VOLUME_TYPE_TSDF, VolumeType_HASHTSDF, VOLUME_TYPE_HASHTSDF, VolumeType_COLOREDTSDF, VOLUME_TYPE_COLOREDTSDF]"""



# Classes
class Params:
    frameSize: cv2.typing.Size
    volumeType: VolumeType
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


class KinFu:
    # Functions
    @classmethod
    def create(cls, _params: Params) -> KinFu: ...

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


class Volume:
    ...

class VolumeParams:
    type: VolumeType
    resolution: cv2.typing.Vec3i
    voxelSize: float
    tsdfTruncDist: float
    maxWeight: int
    depthTruncThreshold: float
    raycastStepFactor: float

    # Functions
    @classmethod
    def defaultParams(cls, _volumeType: VolumeType) -> VolumeParams: ...

    @classmethod
    def coarseParams(cls, _volumeType: VolumeType) -> VolumeParams: ...



# Functions
def makeVolume(_volumeType: VolumeType, _voxelSize: float, _pose: cv2.typing.Matx44f, _raycastStepFactor: float, _truncDist: float, _maxWeight: int, _truncateThreshold: float, _resolution: cv2.typing.Vec3i) -> Volume: ...


