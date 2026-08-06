from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ALLOWED_JUDGES
from db import get_connection
from services import (
    add_match_result,
    format_table,
    get_player_names,
    get_player_stats,
    normalize_name,
    start_tournament,
)

REGISTER_NAME, RESULT_WINNER, RESULT_LOSER, RESULT_SCORE = range(4)


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Регистрация", callback_data="register"),
            InlineKeyboardButton("Игроки", callback_data="players"),
        ],
        [
            InlineKeyboardButton("Таблица", callback_data="table"),
            InlineKeyboardButton("Статистика", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("Начать турнир", callback_data="start_tournament"),
            InlineKeyboardButton("Результат матча", callback_data="result"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Отмена", callback_data="cancel")]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Привет! Я помогу вести теннисный турнир.\n"
        "Используйте:\n"
        "• /register_player Имя — добавить игрока\n"
        "• /players — список игроков\n"
        "• /result Победитель Проигравший 6:3 7:5 — внести результат матча\n"
        "• /table — турнирная таблица\n"
        "• /stats — общая статистика\n"
        "• /help — подсказка"
    )
    await update.message.reply_text(message, reply_markup=build_main_menu_keyboard())


async def register_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /register_player Имя")
        return

    name = normalize_name(" ".join(context.args))
    connection = get_connection()
    try:
        from services import ensure_player

        ensure_player(connection, name)
    except ValueError as error:
        await update.message.reply_text(str(error))
        return
    finally:
        connection.close()

    await update.message.reply_text(f"Игрок добавлен: {name}", reply_markup=build_main_menu_keyboard())


async def show_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    connection = get_connection()
    rows = connection.execute("SELECT name FROM players ORDER BY name ASC").fetchall()
    connection.close()

    if not rows:
        await update.message.reply_text("Пока нет зарегистрированных игроков", reply_markup=build_main_menu_keyboard())
        return

    players_list = "\n".join(f"• {row['name']}" for row in rows)
    await update.message.reply_text(f"Список игроков:\n{players_list}", reply_markup=build_main_menu_keyboard())


async def report_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if ALLOWED_JUDGES and user_id not in ALLOWED_JUDGES:
        await update.message.reply_text("Только судьи могут добавлять результаты матча")
        return

    if len(context.args) < 3:
        await update.message.reply_text("Использование: /result Победитель Проигравший 6:3 7:5")
        return

    winner_name = normalize_name(context.args[0])
    loser_name = normalize_name(context.args[1])
    score_text = " ".join(context.args[2:])

    try:
        result_text = add_match_result(winner_name, loser_name, score_text, update.effective_user.full_name)
    except ValueError as error:
        await update.message.reply_text(f"Ошибка: {error}")
        return

    await update.message.reply_text(f"✅ {result_text}\n\n{format_table()}")


async def show_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(format_table(), reply_markup=build_main_menu_keyboard())


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = get_player_stats()
    if not rows:
        await update.message.reply_text("Пока нет статистики")
        return

    lines = ["Статистика игроков:"]
    for row in rows:
        lines.append(
            f"• {row['name']}: В-{row['wins']} П-{row['losses']} | Сеты {row['sets_won']}-{row['sets_lost']} | Геймы {row['games_won']}-{row['games_lost']}"
        )
    await update.message.reply_text("\n".join(lines), reply_markup=build_main_menu_keyboard())


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "Введите имя игрока:", reply_markup=build_cancel_keyboard()
        )
    else:
        await update.message.reply_text(
            "Введите имя игрока:", reply_markup=build_cancel_keyboard()
        )
    return REGISTER_NAME


async def receive_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = normalize_name(update.message.text)
    connection = get_connection()
    try:
        from services import ensure_player

        ensure_player(connection, name)
    except ValueError as error:
        await update.message.reply_text(str(error), reply_markup=build_cancel_keyboard())
        return REGISTER_NAME
    finally:
        connection.close()

    await update.message.reply_text(
        f"Игрок добавлен: {name}", reply_markup=build_main_menu_keyboard()
    )
    return ConversationHandler.END


async def start_result_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        players = get_player_names()
        if len(players) < 2:
            await query.edit_message_text(
                "Для ввода результата нужно минимум 2 игрока. Добавьте сначала игроков.",
                reply_markup=build_main_menu_keyboard(),
            )
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(name, callback_data=name)] for name in players
        ]
        await query.edit_message_text(
            "Выберите победителя:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text(
            "Выберите победителя:", reply_markup=build_cancel_keyboard()
        )
    return RESULT_WINNER


async def choose_winner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    winner_name = query.data
    context.user_data["result"] = {"winner": winner_name}

    players = [name for name in get_player_names() if name != winner_name]
    keyboard = [
        [InlineKeyboardButton(name, callback_data=name)] for name in players
    ]
    await query.edit_message_text(
        f"Победитель: {winner_name}\nВыберите проигравшего:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return RESULT_LOSER


async def choose_loser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    loser_name = query.data
    result_data = context.user_data.get("result", {})
    winner_name = result_data.get("winner")

    if loser_name == winner_name:
        await query.edit_message_text(
            "Победитель и проигравший не могут совпадать. Выберите другого проигравшего.",
            reply_markup=build_cancel_keyboard(),
        )
        return RESULT_LOSER

    result_data["loser"] = loser_name
    context.user_data["result"] = result_data
    await query.edit_message_text(
        f"Победитель: {winner_name}\nПроигравший: {loser_name}\nВведите счёт, например 6:3 7:5",
        reply_markup=build_cancel_keyboard(),
    )
    return RESULT_SCORE


async def receive_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    result_data = context.user_data.get("result", {})
    winner_name = result_data.get("winner")
    loser_name = result_data.get("loser")

    if not winner_name or not loser_name:
        await update.message.reply_text(
            "Сначала выберите победителя и проигравшего.", reply_markup=build_main_menu_keyboard()
        )
        return ConversationHandler.END

    try:
        result_text = add_match_result(
            winner_name, loser_name, text, update.effective_user.full_name
        )
    except ValueError as error:
        await update.message.reply_text(str(error), reply_markup=build_cancel_keyboard())
        return RESULT_SCORE

    await update.message.reply_text(
        f"✅ {result_text}\n\n{format_table()}", reply_markup=build_main_menu_keyboard()
    )
    return ConversationHandler.END


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Действие отменено.", reply_markup=build_main_menu_keyboard())
    else:
        await update.message.reply_text(
            "Действие отменено.", reply_markup=build_main_menu_keyboard()
        )
    return ConversationHandler.END


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()

    action = query.data or ""
    if action == "players":
        await show_players(update, context)
    elif action == "table":
        await show_table(update, context)
    elif action == "stats":
        await show_stats(update, context)
    elif action == "start_tournament":
        try:
            message = start_tournament()
        except ValueError as error:
            await query.edit_message_text(str(error), reply_markup=build_main_menu_keyboard())
            return
        await query.edit_message_text(message, reply_markup=build_main_menu_keyboard())
    else:
        await query.edit_message_text("Неизвестное действие")


async def start_tournament_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message = start_tournament()
    except ValueError as error:
        await update.message.reply_text(str(error), reply_markup=build_main_menu_keyboard())
        return

    await update.message.reply_text(message, reply_markup=build_main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "• /start — приветствие\n"
        "• /register_player Имя — добавить игрока\n"
        "• /players — список игроков\n"
        "• /start_tournament — начать турнир\n"
        "• /result Победитель Проигравший 6:3 7:5 — результат матча\n"
        "• /table — турнирная таблица\n"
        "• /stats — статистика игроков"
    )


def build_handlers() -> list:
    conversation_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_registration, pattern="^register$"),
            CallbackQueryHandler(start_result_flow, pattern="^result$"),
        ],
        states={
            REGISTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_registration)
            ],
            RESULT_WINNER: [
                CallbackQueryHandler(choose_winner, pattern="^[^cancel].*")
            ],
            RESULT_LOSER: [
                CallbackQueryHandler(choose_loser, pattern="^[^cancel].*")
            ],
            RESULT_SCORE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_score)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_action, pattern="^cancel$"),
            CommandHandler("cancel", cancel_action),
        ],
        allow_reentry=True,
    )

    return [
        CommandHandler("start", start),
        CommandHandler("register_player", register_player),
        CommandHandler("register", register_player),
        CommandHandler("players", show_players),
        CommandHandler("start_tournament", start_tournament_command),
        CommandHandler("result", report_result),
        CommandHandler("table", show_table),
        CommandHandler("stats", show_stats),
        CommandHandler("help", help_command),
        conversation_handler,
        CallbackQueryHandler(handle_callback, pattern="^(players|table|stats|start_tournament)$"),
    ]
