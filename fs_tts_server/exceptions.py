class LogicError(Exception): ...


class ApiBaseException(Exception):
  def __init__(self, message: str, *, user_msg: str | None = None):
    super().__init__(message)
    self._user_msg = user_msg

  @property
  def user_msg(self) -> str:
    """fallback to raw msg"""
    return self._user_msg or str(self)


class NotExistInDBException(ApiBaseException):
  """data not exists in db"""


class InvalidUserInputException(ApiBaseException):
  """User input is invalid"""
