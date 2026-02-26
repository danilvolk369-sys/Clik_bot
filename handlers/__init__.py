# ======================================================
# HANDLERS PACKAGE — КликТохн v1.0.0
# ======================================================

from .common import router as common_router
from .user import router as user_router
from .shop import router as shop_router
from .chat import router as chat_router
from .pvp import router as pvp_router
from .owner import router as owner_router
from .admin import router as admin_router
from .nft import router as nft_router
from .trade import router as trade_router
from .history import router as history_router

__all__ = [
    "common_router",
    "user_router",
    "shop_router",
    "chat_router",
    "pvp_router",
    "owner_router",
    "admin_router",
    "nft_router",
    "trade_router",
    "history_router",
]
