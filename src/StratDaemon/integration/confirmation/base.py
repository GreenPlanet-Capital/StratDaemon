
class BaseConfirmation:
    def init_confirmation(self, uid: str) -> None:
        raise NotImplementedError
    
    def check_confirmation(self, uid: str) -> bool:
        raise NotImplementedError
    
    def delete_confirmation(self, uid: str) -> None:
        raise NotImplementedError