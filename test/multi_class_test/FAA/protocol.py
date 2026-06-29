from typing import Protocol, Any


class FAAProtocol(Protocol):
    common_property: str

    def utils_method(self) -> Any:
        pass

    def base_method(self) -> Any:
        pass

    def battle_method(self) -> Any:
        pass
