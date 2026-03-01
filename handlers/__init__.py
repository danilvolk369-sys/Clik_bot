# handlers/__init__.py
from handlers.common import router as common_router
from handlers.user import router as user_router
from handlers.shop import router as shop_router
from handlers.pvp import router as pvp_router
from handlers.nft import router as nft_router
from handlers.trade import router as trade_router
from handlers.owner import router as owner_router
from handlers.admin import router as admin_router
from handlers.chat import router as chat_router
from handlers.history import router as history_router

all_routers = [
    common_router,
    owner_router,    # /admin — до admin, чтобы owner-only перехватывал
    admin_router,
    user_router,
    shop_router,
    pvp_router,
    nft_router,
    trade_router,
    chat_router,
    history_router,
]
