from fastapi import APIRouter, Depends

from ..integrations import configured_adapters
from ..security.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("")
def list_integrations(actor: AuthenticatedUser = Depends(get_current_user)):
    return [adapter.fetch_status() for adapter in configured_adapters()]
