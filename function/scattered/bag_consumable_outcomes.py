"""按原始道具图案保存背包消耗品的使用结果。"""

from hashlib import sha256
import json
import os
from tempfile import NamedTemporaryFile
from threading import Lock

from function.globals.get_paths import PATHS


OUTCOME_FILENAME = "bag_consumable_outcomes.json"
NO_REWARD, SINGLE_REWARD, MULTIPLE_REWARDS = "none", "single", "multiple"
OUTCOMES = (NO_REWARD, SINGLE_REWARD, MULTIPLE_REWARDS)
_LOCK = Lock()
_CURRENT = {}


def icon_digest(image):
    """散列解码后的图案，文件名、PNG 压缩和不透明 Alpha 通道不影响结果。"""
    if image.shape[2] == 4 and (image[:, :, 3] == 255).all():
        image = image[:, :, :3]
    return sha256(f"{image.shape}:{image.dtype}:".encode("ascii") + image.tobytes()).hexdigest()


def _read_outcomes(path):
    """读取每个图案对应的所有已知结果。"""
    from function.globals.log import CUS_LOGGER

    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or set(data) != set(OUTCOMES) or any(
                not isinstance(values, list) for values in data.values()):
            raise ValueError("需要三组图案哈希列表")
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        CUS_LOGGER.warning(f"[背包] [使用结果] 无法读取 {path}：{error}，使用可用记录继续识别")
        return {}
    result = {}
    for outcome, digests in data.items():
        for digest in digests:
            if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                continue
            result.setdefault(digest, set()).add(outcome)
    return result


def _merge_outcomes(*sources):
    """合并内置、内存和磁盘记录；同图案在各处学到的结果都要保留。"""
    entries = {}
    for source in sources:
        for digest, outcomes in source.items():
            entries.setdefault(digest, set()).update(outcomes)
    return entries


class BagConsumableOutcomes:
    """两位玩家共用当前学习结果，提交时合并文件并原子替换。"""

    def __init__(self):
        self.path = os.path.join(PATHS["logs"], OUTCOME_FILENAME)
        self.template_path = os.path.join(PATHS["root"], "resource", "template", OUTCOME_FILENAME)
        with _LOCK:
            missing = not os.path.isfile(self.path)
            saved = _read_outcomes(self.path)
            entries = _merge_outcomes(_read_outcomes(self.template_path), _CURRENT.get(self.path, {}),
                                      saved)
            _CURRENT[self.path] = entries
            if missing or entries != saved:
                self._save(entries)

    def get(self, digest):
        """返回已知结果的只读集合，尚未学习时集合为空。"""
        with _LOCK:
            return frozenset(_CURRENT[self.path].get(digest, ()))

    def learn(self, digest, outcome):
        """追加扣减已确认的观察结果，保留同一哈希已有的其他结果。"""
        with _LOCK:
            entries = _CURRENT[self.path]
            if outcome in entries.get(digest, ()):
                return
            entries = _merge_outcomes(entries, _read_outcomes(self.path))
            entries.setdefault(digest, set()).add(outcome)
            _CURRENT[self.path] = entries
            self._save(entries)

    def _save(self, entries):
        """先写同目录临时文件；写盘失败时保留内存学习结果和上一次完整文件。"""
        from function.globals.log import CUS_LOGGER

        data = {outcome: sorted(digest for digest, known in entries.items() if outcome in known)
                for outcome in OUTCOMES}
        folder = os.path.dirname(self.path)
        temp_path = None
        try:
            os.makedirs(folder, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder, delete=False) as stream:
                temp_path = stream.name
                json.dump(data, stream, indent=2)
                stream.write("\n")
            os.replace(temp_path, self.path)
        except OSError as error:
            CUS_LOGGER.warning(f"[背包] [使用结果] 无法保存 {self.path}：{error}，本次运行继续使用内存记录")
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as error:
                    CUS_LOGGER.warning(f"[背包] [使用结果] 无法清理临时文件 {temp_path}：{error}")
