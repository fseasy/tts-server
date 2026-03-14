import traceback
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession
from supertokens_python.recipe.session import SessionContainer
from supertokens_python.recipe.session.asyncio import refresh_session
from supertokens_python.recipe.session.framework.fastapi import verify_session
from supertokens_python.recipe.userroles import UserRoleClaim

from docgate import config
from docgate.exceptions import InvalidUserInputException, LogicError
from docgate.jwt_verification import verify_jwt
from docgate.logics import CreateDbUserLogic, PrepaidCodeLogic, UserPermissionLogic
from docgate.models import PayLog
from docgate.repositories import async_create_prepaid_code, async_get_user, get_db_async_session
from docgate.supertokens_config import StRole
from docgate.supertokens_utils import (
    async_create_password_reset_link,
    async_get_user as get_st_user,
    async_manually_verify_email,
)

# We define the routers to group api endpoints and support future expansion.
user_router = APIRouter(prefix="/user", tags=["User"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
internal_auth_router = APIRouter(prefix="/internal-auth", tags=["InternalAuth"])


logger = config.LOGGER


@user_router.get("/get-supertokens-info")
async def get_current_st_user_info(session: SessionContainer = Depends(verify_session())) -> StUserResult:
    uid = session.user_id
    import time

    t = time.perf_counter()
    print(f"Enter get-supertokens-info: {time.perf_counter() - t:.2f}")
    try:
        user = await get_st_user(uid)
        print(f"get get-supertokens-info result: {time.perf_counter() - t:.2f}")
    except Exception as e:
        err = f"[api]: get-supertokens-info fail: uid={uid}, err={e}, stack={traceback.format_exc()}"
        logger.error(f"{err}", extra={"user_id": uid})
        return StUserResult(error=err, user=None)
    if not user:
        logger.info(f"[api]: get-supertokens-info get None user, uid={uid}", extra={"user_id": uid})
        return StUserResult(error=None, user=None)
    return StUserResult(error=None, user=user.to_json())
