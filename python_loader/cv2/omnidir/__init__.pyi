__all__: list[str] = []

import cv2
import cv2.typing
import typing as _typing


# Enumerations
CALIB_USE_GUESS: int
CALIB_FIX_SKEW: int
CALIB_FIX_K1: int
CALIB_FIX_K2: int
CALIB_FIX_P1: int
CALIB_FIX_P2: int
CALIB_FIX_XI: int
CALIB_FIX_GAMMA: int
CALIB_FIX_CENTER: int
RECTIFY_PERSPECTIVE: int
RECTIFY_CYLINDRICAL: int
RECTIFY_LONGLATI: int
RECTIFY_STEREOGRAPHIC: int
XYZRGB: int
XYZ: int



# Functions
@_typing.overload
def calibrate(objectPoints: _typing.Sequence[cv2.typing.MatLike], imagePoints: _typing.Sequence[cv2.typing.MatLike], size: cv2.typing.Size, K: cv2.typing.MatLike, xi: cv2.typing.MatLike, D: cv2.typing.MatLike, flags: int, criteria: cv2.typing.TermCriteria, rvecs: _typing.Sequence[cv2.typing.MatLike] | None = ..., tvecs: _typing.Sequence[cv2.typing.MatLike] | None = ..., idx: cv2.typing.MatLike | None = ...) -> tuple[float, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, _typing.Sequence[cv2.typing.MatLike], _typing.Sequence[cv2.typing.MatLike], cv2.typing.MatLike]: ...
@_typing.overload
def calibrate(objectPoints: _typing.Sequence[cv2.UMat], imagePoints: _typing.Sequence[cv2.UMat], size: cv2.typing.Size, K: cv2.UMat, xi: cv2.UMat, D: cv2.UMat, flags: int, criteria: cv2.typing.TermCriteria, rvecs: _typing.Sequence[cv2.UMat] | None = ..., tvecs: _typing.Sequence[cv2.UMat] | None = ..., idx: cv2.UMat | None = ...) -> tuple[float, cv2.UMat, cv2.UMat, cv2.UMat, _typing.Sequence[cv2.UMat], _typing.Sequence[cv2.UMat], cv2.UMat]: ...

@_typing.overload
def initUndistortRectifyMap(K: cv2.typing.MatLike, D: cv2.typing.MatLike, xi: cv2.typing.MatLike, R: cv2.typing.MatLike, P: cv2.typing.MatLike, size: cv2.typing.Size, m1type: int, flags: int, map1: cv2.typing.MatLike | None = ..., map2: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def initUndistortRectifyMap(K: cv2.UMat, D: cv2.UMat, xi: cv2.UMat, R: cv2.UMat, P: cv2.UMat, size: cv2.typing.Size, m1type: int, flags: int, map1: cv2.UMat | None = ..., map2: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def projectPoints(objectPoints: cv2.typing.MatLike, rvec: cv2.typing.MatLike, tvec: cv2.typing.MatLike, K: cv2.typing.MatLike, xi: float, D: cv2.typing.MatLike, imagePoints: cv2.typing.MatLike | None = ..., jacobian: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def projectPoints(objectPoints: cv2.UMat, rvec: cv2.UMat, tvec: cv2.UMat, K: cv2.UMat, xi: float, D: cv2.UMat, imagePoints: cv2.UMat | None = ..., jacobian: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def stereoCalibrate(objectPoints: _typing.Sequence[cv2.typing.MatLike], imagePoints1: _typing.Sequence[cv2.typing.MatLike], imagePoints2: _typing.Sequence[cv2.typing.MatLike], imageSize1: cv2.typing.Size, imageSize2: cv2.typing.Size, K1: cv2.typing.MatLike, xi1: cv2.typing.MatLike, D1: cv2.typing.MatLike, K2: cv2.typing.MatLike, xi2: cv2.typing.MatLike, D2: cv2.typing.MatLike, flags: int, criteria: cv2.typing.TermCriteria, rvec: cv2.typing.MatLike | None = ..., tvec: cv2.typing.MatLike | None = ..., rvecsL: _typing.Sequence[cv2.typing.MatLike] | None = ..., tvecsL: _typing.Sequence[cv2.typing.MatLike] | None = ..., idx: cv2.typing.MatLike | None = ...) -> tuple[float, _typing.Sequence[cv2.typing.MatLike], _typing.Sequence[cv2.typing.MatLike], _typing.Sequence[cv2.typing.MatLike], cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, _typing.Sequence[cv2.typing.MatLike], _typing.Sequence[cv2.typing.MatLike], cv2.typing.MatLike]: ...
@_typing.overload
def stereoCalibrate(objectPoints: _typing.Sequence[cv2.UMat], imagePoints1: _typing.Sequence[cv2.UMat], imagePoints2: _typing.Sequence[cv2.UMat], imageSize1: cv2.typing.Size, imageSize2: cv2.typing.Size, K1: cv2.UMat, xi1: cv2.UMat, D1: cv2.UMat, K2: cv2.UMat, xi2: cv2.UMat, D2: cv2.UMat, flags: int, criteria: cv2.typing.TermCriteria, rvec: cv2.UMat | None = ..., tvec: cv2.UMat | None = ..., rvecsL: _typing.Sequence[cv2.UMat] | None = ..., tvecsL: _typing.Sequence[cv2.UMat] | None = ..., idx: cv2.UMat | None = ...) -> tuple[float, _typing.Sequence[cv2.UMat], _typing.Sequence[cv2.UMat], _typing.Sequence[cv2.UMat], cv2.UMat, cv2.UMat, cv2.UMat, cv2.UMat, cv2.UMat, cv2.UMat, cv2.UMat, cv2.UMat, _typing.Sequence[cv2.UMat], _typing.Sequence[cv2.UMat], cv2.UMat]: ...

@_typing.overload
def stereoReconstruct(image1: cv2.typing.MatLike, image2: cv2.typing.MatLike, K1: cv2.typing.MatLike, D1: cv2.typing.MatLike, xi1: cv2.typing.MatLike, K2: cv2.typing.MatLike, D2: cv2.typing.MatLike, xi2: cv2.typing.MatLike, R: cv2.typing.MatLike, T: cv2.typing.MatLike, flag: int, numDisparities: int, SADWindowSize: int, disparity: cv2.typing.MatLike | None = ..., image1Rec: cv2.typing.MatLike | None = ..., image2Rec: cv2.typing.MatLike | None = ..., newSize: cv2.typing.Size = ..., Knew: cv2.typing.MatLike | None = ..., pointCloud: cv2.typing.MatLike | None = ..., pointType: int = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def stereoReconstruct(image1: cv2.UMat, image2: cv2.UMat, K1: cv2.UMat, D1: cv2.UMat, xi1: cv2.UMat, K2: cv2.UMat, D2: cv2.UMat, xi2: cv2.UMat, R: cv2.UMat, T: cv2.UMat, flag: int, numDisparities: int, SADWindowSize: int, disparity: cv2.UMat | None = ..., image1Rec: cv2.UMat | None = ..., image2Rec: cv2.UMat | None = ..., newSize: cv2.typing.Size = ..., Knew: cv2.UMat | None = ..., pointCloud: cv2.UMat | None = ..., pointType: int = ...) -> tuple[cv2.UMat, cv2.UMat, cv2.UMat, cv2.UMat]: ...

@_typing.overload
def stereoRectify(R: cv2.typing.MatLike, T: cv2.typing.MatLike, R1: cv2.typing.MatLike | None = ..., R2: cv2.typing.MatLike | None = ...) -> tuple[cv2.typing.MatLike, cv2.typing.MatLike]: ...
@_typing.overload
def stereoRectify(R: cv2.UMat, T: cv2.UMat, R1: cv2.UMat | None = ..., R2: cv2.UMat | None = ...) -> tuple[cv2.UMat, cv2.UMat]: ...

@_typing.overload
def undistortImage(distorted: cv2.typing.MatLike, K: cv2.typing.MatLike, D: cv2.typing.MatLike, xi: cv2.typing.MatLike, flags: int, undistorted: cv2.typing.MatLike | None = ..., Knew: cv2.typing.MatLike | None = ..., new_size: cv2.typing.Size = ..., R: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def undistortImage(distorted: cv2.UMat, K: cv2.UMat, D: cv2.UMat, xi: cv2.UMat, flags: int, undistorted: cv2.UMat | None = ..., Knew: cv2.UMat | None = ..., new_size: cv2.typing.Size = ..., R: cv2.UMat | None = ...) -> cv2.UMat: ...

@_typing.overload
def undistortPoints(distorted: cv2.typing.MatLike, K: cv2.typing.MatLike, D: cv2.typing.MatLike, xi: cv2.typing.MatLike, R: cv2.typing.MatLike, undistorted: cv2.typing.MatLike | None = ...) -> cv2.typing.MatLike: ...
@_typing.overload
def undistortPoints(distorted: cv2.UMat, K: cv2.UMat, D: cv2.UMat, xi: cv2.UMat, R: cv2.UMat, undistorted: cv2.UMat | None = ...) -> cv2.UMat: ...


