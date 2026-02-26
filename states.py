# ======================================================
# СОСТОЯНИЯ (FSM) — КликТохн v1.0.0
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
    waiting_reply = State()         # ответ пользователя на тикет (диалог)


# ─── Панель владельца ───
class OwnerStates(StatesGroup):
    waiting_ban_id = State()
    waiting_ban_duration = State()  # выбор срока бана
    waiting_unban_id = State()
    waiting_give = State()          # ждём "ID кол-во"
    waiting_broadcast = State()     # ждём текст рассылки
    waiting_ticket_reply = State()  # ответ владельца на тикет
    # Создание НФТ — пошагово
    nft_name = State()
    nft_rarity = State()
    nft_income = State()
    nft_price = State()
    nft_confirm = State()           # превью → опубликовать / отменить
    # Настройки — ввод нового значения
    waiting_setting_value = State()
    # Сброс данных участника
    waiting_reset_user_id = State()


# ─── Панель администратора ───
class AdminStates(StatesGroup):
    waiting_key = State()           # ввод ключа активации
    waiting_ban_id = State()
    waiting_ban_duration = State()  # выбор срока бана
    waiting_unban_id = State()
    waiting_ticket_reply = State()  # ответ на тикет (диалог)
    # Новые возможности админа
    waiting_give = State()          # выдать клики (ID кол-во)
    waiting_broadcast = State()     # рассылка
    waiting_reset_user_id = State() # сброс данных
    nft_name = State()              # создание НФТ
    nft_rarity = State()
    nft_income = State()
    nft_price = State()
    nft_confirm = State()


# ─── Ивенты ───
class EventStates(StatesGroup):
    waiting_name = State()          # название аукциона
    waiting_nft_name = State()      # название НФТ-приза
    waiting_rarity = State()        # редкость НФТ (1-10)
    waiting_income = State()        # доход в час
    waiting_bet = State()           # минимальная ставка
    waiting_duration = State()      # длительность
    confirm = State()               # подтверждение


class EventBidStates(StatesGroup):
    waiting_bid = State()           # ввод суммы ставки


# ─── Продажа НФТ ───
class SellNFTStates(StatesGroup):
    waiting_price = State()


# ─── История / Жалобы ───
class HistoryStates(StatesGroup):
    browsing = State()              # просмотр списка

class ComplaintStates(StatesGroup):
    waiting_reason = State()        # ввод причины жалобы
    admin_comment = State()         # админ пишет комментарий


# ─── Обмен НФТ (доска обменов) ───
class TradeStates(StatesGroup):
    select_my_nft = State()         # выбор своего НФТ для обмена
    choose_want_type = State()      # что хотите: клики / 1-3 НФТ
    enter_click_price = State()     # ввод суммы кликов
    confirm_create = State()        # подтверждение публикации
    propose_select_nfts = State()   # выбор НФТ для предложения
    confirm_propose = State()       # подтверждение предложения
