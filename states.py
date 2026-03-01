# ======================================================
# СОСТОЯНИЯ (FSM) — КликТохн v1.0.1
# ======================================================
from aiogram.fsm.state import State, StatesGroup


class ChatStates(StatesGroup):
    searching = State()
    in_chat = State()


class PVPStates(StatesGroup):
    waiting_bet = State()


class SupportStates(StatesGroup):
    waiting_complaint = State()
    waiting_problem = State()
    waiting_reply = State()


# ━━━━━━━━━━━━━━━━━━━ Панель владельца ━━━━━━━━━━━━━━━━━━━
class OwnerStates(StatesGroup):
    waiting_ban_id = State()
    waiting_ban_duration = State()
    waiting_unban_id = State()
    waiting_give = State()
    waiting_take = State()
    waiting_broadcast = State()
    waiting_ticket_reply = State()
    # НФТ
    nft_name = State()
    nft_rarity = State()
    nft_income = State()
    nft_price = State()
    nft_confirm = State()
    # Авто-НФТ (удалено)
    auto_nft_count = State()
    auto_nft_confirm = State()
    # Быстрое НФТ
    quick_nft_name = State()
    quick_nft_count = State()
    # Настройки
    waiting_setting_value = State()
    # Сброс участника
    waiting_reset_user_id = State()
    # Выдать/снять НФТ
    waiting_give_nft_user = State()
    waiting_give_nft_id = State()
    waiting_take_nft_user = State()
    # Поиск участника
    waiting_user_search_id = State()
    # Логи
    waiting_log_user_id = State()
    # Сообщение покупателю по заказу
    payment_msg_to_user = State()
    # Написать участнику (из профиля)
    msg_to_user = State()
    # Добавить значение (клики/доход/сила/ёмкость/слот)
    waiting_add_value = State()


# ━━━━━━━━━━━━━━━━━━━ Панель администратора ━━━━━━━━━━━━━━━━━━━
class AdminStates(StatesGroup):
    waiting_key = State()
    waiting_ban_id = State()
    waiting_ban_duration = State()
    waiting_unban_id = State()
    waiting_ticket_reply = State()
    waiting_give = State()
    waiting_take = State()
    waiting_broadcast = State()
    waiting_reset_user_id = State()
    nft_name = State()
    nft_rarity = State()
    nft_income = State()
    nft_price = State()
    nft_confirm = State()
    waiting_user_search_id = State()
    # Написать участнику (из профиля)
    msg_to_user = State()
    # Добавить значение (клики/доход/сила/ёмкость/слот)
    waiting_add_value = State()
    # Быстрое НФТ
    quick_nft_name = State()
    quick_nft_count = State()
    # Настройки
    waiting_setting_value = State()
    # Логи
    waiting_log_user_id = State()
    # Сообщение покупателю по заказу
    payment_msg_to_user = State()


# ━━━━━━━━━━━━━━━━━━━ Ивенты ━━━━━━━━━━━━━━━━━━━
class EventStates(StatesGroup):
    waiting_name = State()
    waiting_nft_name = State()
    waiting_rarity = State()
    waiting_income = State()
    waiting_bet = State()
    waiting_duration = State()
    waiting_max_participants = State()
    confirm = State()


class EventBidStates(StatesGroup):
    waiting_bid = State()


class DialogStates(StatesGroup):
    """Пользователь отвечает на сообщение админа/владельца."""
    user_replying = State()


# ━━━━━━━━━━━━━━━━━━━ Продажа НФТ ━━━━━━━━━━━━━━━━━━━
class SellNFTStates(StatesGroup):
    waiting_price = State()


# ━━━━━━━━━━━━━━━━━━━ История / Жалобы ━━━━━━━━━━━━━━━━━━━
class HistoryStates(StatesGroup):
    browsing = State()


class ComplaintStates(StatesGroup):
    waiting_reason = State()
    admin_comment = State()


# ━━━━━━━━━━━━━━━━━━━ Обмен НФТ ━━━━━━━━━━━━━━━━━━━
class TradeStates(StatesGroup):
    select_my_nfts = State()       # выбор своих НФТ (1-5)
    enter_click_price = State()
    confirm_create = State()
    propose_select_nfts = State()  # покупатель выбирает НФТ
    confirm_propose = State()


# ━━━━━━━━━━━━━━━━━━━ Оплата ━━━━━━━━━━━━━━━━━━━
class PaymentStates(StatesGroup):
    waiting_fio = State()        # шаг 1: ввод ФИО отправителя
    waiting_screenshot = State() # шаг 2: скриншот чека
    confirming = State()         # подтверждение перед отправкой
    reply_to_owner = State()     # пользователь отвечает владельцу по заказу


# ━━━━━━━━━━━━━━━━━━━ Админ-права ━━━━━━━━━━━━━━━━━━━
class AdminPermStates(StatesGroup):
    editing = State()

