import uuid
import random
import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ForceReply
)
from telebot.apihelper import ApiTelegramException

API_KEY = **ПОДСТАВИТЬ СВОЙ КОД**
nim_bot = telebot.TeleBot(API_KEY)

game_sessions = {}
pending_inline_games = {}

original_callback_answer = nim_bot.answer_callback_query


def safe_callback_response(callback_id, text=None, **kwargs):
    try:
        return original_callback_answer(callback_id, text=text, **kwargs)
    except ApiTelegramException:
        return None


nim_bot.answer_callback_query = safe_callback_response


def generate_pile_buttons(heaps, session_id, is_inline=False):
    button_layout = InlineKeyboardMarkup()
    for heap_idx, stones in enumerate(heaps):
        row_buttons = []
        for take_count in range(1, stones + 1):
            if is_inline:
                cb_data = f"inline!,{heap_idx},{take_count}"
            else:
                cb_data = f"{heap_idx},{take_count},{session_id}"
            btn = InlineKeyboardButton(str(take_count), callback_data=cb_data)
            row_buttons.append(btn)
            if len(row_buttons) >= 8:
                button_layout.row(*row_buttons)
                row_buttons = []
        if row_buttons:
            button_layout.row(*row_buttons)
    return button_layout


def calculate_best_move(heaps, mistake_probability=0):
    xor_total = 0
    for stones in heaps:
        xor_total ^= stones
    for idx, stones in enumerate(heaps):
        target = stones ^ xor_total
        if target < stones:
            return idx, stones - target

    non_empty_heaps = [i for i, s in enumerate(heaps) if s > 0]
    chosen_idx = random.choice(non_empty_heaps)
    return chosen_idx, random.randint(1, heaps[chosen_idx])


@nim_bot.message_handler(commands=['start'])
def handle_start_command(message):
    if message.chat.type != 'private':
        return
    menu_markup = InlineKeyboardMarkup().row(
        InlineKeyboardButton("Классика", callback_data="gm_classic"),
        InlineKeyboardButton("Кастомный", callback_data="gm_custom")
    )
    nim_bot.send_message(message.chat.id, "Добро пожаловать в игру Ним! 👋\nВыберите режим игры или введите /info для справки.", reply_markup=menu_markup)


@nim_bot.message_handler(commands=['info'])
def show_info(message):
    info_text = """ℹ️ Информация об игре Ним:

Ним — классическая математическая игра, впервые описанная Ч. Бутоном в 1901 году.
В ней требуется по очереди убирать любое положительное число камней из одной кучи.
Выигрывает тот, кто заберёт последний камень.

🔑 Суть стратегии:
- Представьте размеры куч в двоичном виде.
- Выигрышная позиция определяется тем, что побитовое XOR всех куч не равен нулю.
- При каждом ходе стремитесь оставить оппонента в положении, где XOR равен нулю.

Помимо чистой логики, в более сложных вариантах используется комбинаторный анализ —
метод, позволяющий объединять несколько независимых игр в одну.

📌 Команды:
/start - начать одиночную игру против бота
/newgame - начать парную игру в группе
/info - показать эту справку"""
    nim_bot.send_message(message.chat.id, info_text)


@nim_bot.callback_query_handler(func=lambda c: c.data.startswith('gm_'))
def handle_mode_choice(callback):
    nim_bot.delete_message(callback.message.chat.id, callback.message.message_id)
    game_mode = callback.data.split('_', 1)[1]
    chat_id = callback.message.chat.id

    if game_mode == 'classic':
        standard_heaps = [3, 5, 7]
        game_sessions[chat_id] = {'heaps': standard_heaps, 'turn': 'player'}
        prompt_difficulty_level(chat_id)
    else:
        request = nim_bot.send_message(
            chat_id,
            "Введите через пробел размеры куч (пример: 2 4 6 8). Ответьте на это сообщение."
        )
        nim_bot.register_next_step_handler(request, process_custom_heaps_private)


def process_custom_heaps_private(message):
    chat_id = message.chat.id
    try:
        custom_heaps = list(map(int, message.text.split()))
        assert all(h > 0 for h in custom_heaps) and len(custom_heaps) > 0
    except:
        error_msg = nim_bot.reply_to(message, "Неверный формат. Пример: 2 4 6")
        nim_bot.register_next_step_handler(error_msg, process_custom_heaps_private)
        return

    game_sessions[chat_id] = {'heaps': custom_heaps, 'turn': 'player'}
    prompt_difficulty_level(chat_id)


def prompt_difficulty_level(chat_id):
    difficulty_markup = InlineKeyboardMarkup().row(
        InlineKeyboardButton("Легко", callback_data="dl_easy"),
        InlineKeyboardButton("Средне", callback_data="dl_medium"),
        InlineKeyboardButton("Сложно", callback_data="dl_hard")
    )
    nim_bot.send_message(chat_id, "Выберите уровень сложности:", reply_markup=difficulty_markup)


@nim_bot.callback_query_handler(func=lambda c: c.data.startswith('dl_'))
def handle_difficulty_choice(callback):
    chat_id = callback.message.chat.id
    difficulty = callback.data.split('_', 1)[1]
    nim_bot.delete_message(chat_id, callback.message.message_id)

    difficulty_map = {'easy': 0.5, 'medium': 0.3, 'hard': 0.05}
    game_sessions[chat_id]['error_chance'] = difficulty_map.get(difficulty, 0)
    display_private_game(chat_id)


def display_private_game(chat_id):
    current_session = game_sessions[chat_id]
    buttons = generate_pile_buttons(current_session['heaps'], session_id=chat_id, is_inline=False)
    nim_bot.send_message(chat_id, "Ваш ход:", reply_markup=buttons)


@nim_bot.callback_query_handler(
    func=lambda c: c.message and c.message.chat.type == 'private' and ',' in c.data
)
def process_private_turn(callback):
    chat_id = callback.message.chat.id
    current_session = game_sessions.get(chat_id)
    if not current_session or current_session['turn'] != 'player':
        safe_callback_response(callback.id, "Сейчас не ваш ход.")
        return

    heap_str, take_str, _ = callback.data.split(',')
    heap_idx, stones_taken = int(heap_str), int(take_str)
    current_session['heaps'][heap_idx] -= stones_taken
    move_description = f"Вы сняли {stones_taken} из кучи {heap_idx + 1}."

    if sum(current_session['heaps']) == 0:
        nim_bot.edit_message_text(f"{move_description}\nВы выиграли!", chat_id, callback.message.message_id)
        del game_sessions[chat_id]
        return

    bot_heap, bot_take = calculate_best_move(current_session['heaps'], current_session.get('error_chance', 0))
    current_session['heaps'][bot_heap] -= bot_take
    move_description += f"\nБот снял {bot_take} из кучи {bot_heap + 1}."

    if sum(current_session['heaps']) == 0:
        nim_bot.edit_message_text(f"{move_description}\nБот победил.", chat_id, callback.message.message_id)
        del game_sessions[chat_id]
        return

    current_session['turn'] = 'player'
    new_buttons = generate_pile_buttons(current_session['heaps'], session_id=chat_id, is_inline=False)
    nim_bot.edit_message_text(f"{move_description}\nВаш ход:", chat_id, callback.message.message_id, reply_markup=new_buttons)


@nim_bot.message_handler(commands=['newgame'])
def start_group_game(message):
    if message.chat.type == 'private':
        nim_bot.reply_to(message, "Напишите это в групповом чате, чтобы пригласить друга.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    mode_markup = InlineKeyboardMarkup().row(
        InlineKeyboardButton("Классика", callback_data=f"grp_classic_{user_id}"),
        InlineKeyboardButton("Кастомный", callback_data=f"grp_custom_{user_id}")
    )
    nim_bot.send_message(chat_id, f"{message.from_user.first_name} предлагает игру:", reply_markup=mode_markup)


@nim_bot.callback_query_handler(func=lambda c: c.data.startswith('grp_'))
def handle_group_mode(callback):
    chat_id = callback.message.chat.id
    parts = callback.data.split('_', 2)
    mode, creator_str = parts[1], parts[2]
    creator_id = int(creator_str)
    if callback.from_user.id != creator_id:
        safe_callback_response(callback.id, "Только создатель может выбрать режим.")
        return

    session_id = str(uuid.uuid4())

    if mode == 'classic':
        standard_heaps = [3, 5, 7]
        game_sessions[session_id] = {'heaps': standard_heaps, 'turn': 0, 'last_action': ''}
        send_join_request(chat_id, creator_id, session_id)
    else:
        prompt = nim_bot.send_message(
            chat_id,
            "Введите через пробел размеры куч (пример: 2 4 6). Ответьте на это сообщение."
        )
        nim_bot.register_next_step_handler(prompt, process_custom_heaps_group, creator_id, chat_id, session_id)


def process_custom_heaps_group(message, creator_id, chat_id, session_id):
    try:
        custom_heaps = list(map(int, message.text.split()))
        assert all(h > 0 for h in custom_heaps) and len(custom_heaps) > 0
    except:
        error_reply = nim_bot.reply_to(message, "Неверный ввод. Пример: 2 4 6")
        nim_bot.register_next_step_handler(error_reply, process_custom_heaps_group, creator_id, chat_id, session_id)
        return

    game_sessions[session_id] = {'heaps': custom_heaps, 'turn': 0, 'last_action': ''}
    send_join_request(chat_id, creator_id, session_id)


def send_join_request(chat_id, creator_id, session_id):
    join_markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Присоединиться", callback_data=f"join_{creator_id}_{session_id}")
    )
    nim_bot.send_message(chat_id, "Ждём второго игрока...", reply_markup=join_markup)


@nim_bot.callback_query_handler(func=lambda c: c.data.startswith('join_'))
def join_group_game(callback):
    _, creator_str, session_id = callback.data.split('_', 2)
    creator_id = int(creator_str)
    chat_id = callback.message.chat.id

    if callback.from_user.id == creator_id:
        return safe_callback_response(callback.id, "Создатель не может присоединиться сам.")

    current_session = game_sessions.get(session_id)
    if not current_session or 'participants' in current_session:
        return safe_callback_response(callback.id, "Игра недоступна.")

    current_session['participants'] = [creator_id, callback.from_user.id]
    update_group_display(chat_id, callback.message.message_id, session_id)


def update_group_display(chat_id, msg_id, session_id):
    current_session = game_sessions[session_id]
    buttons = generate_pile_buttons(current_session['heaps'], session_id=session_id, is_inline=False)
    current_player_idx = current_session['turn']
    player_id = current_session['participants'][current_player_idx]
    player_name = nim_bot.get_chat_member(chat_id, player_id).user.first_name
    status_text = f"{current_session['last_action']}\nХод: {player_name}" if current_session['last_action'] else f"Ход: {player_name}"
    nim_bot.edit_message_text(status_text, chat_id, msg_id, reply_markup=buttons)


@nim_bot.callback_query_handler(
    func=lambda c: c.message and c.message.chat.type != 'private' and ',' in c.data
)
def process_group_turn(callback):
    heap_str, take_str, session_id = callback.data.split(',')
    current_session = game_sessions.get(session_id)
    chat_id = callback.message.chat.id
    if not current_session:
        return safe_callback_response(callback.id, "Игра завершена.")

    expected_player = current_session['participants'][current_session['turn']]
    if callback.from_user.id != expected_player:
        return safe_callback_response(callback.id, "Сейчас не ваш ход.")

    heap_idx, stones_taken = int(heap_str), int(take_str)
    current_session['heaps'][heap_idx] -= stones_taken
    player_name = callback.from_user.first_name
    current_session['last_action'] = f"{player_name} снял(а) {stones_taken} из кучи {heap_idx + 1}."

    if sum(current_session['heaps']) == 0:
        nim_bot.edit_message_text(f"{current_session['last_action']}\n🏆 Победитель: {player_name}", chat_id, callback.message.message_id)
        del game_sessions[session_id]
        return

    current_session['turn'] ^= 1
    update_group_display(chat_id, callback.message.message_id, session_id)


@nim_bot.inline_handler(func=lambda q: True)
def handle_inline_request(query):
    session_id = str(uuid.uuid4())
    results = []
    for mode, title in (('classic', '🎯 Классика'), ('custom', '⚙️ Кастом')):
        content = InputTextMessageContent(f"Игра NIM ({title})")
        join_btn = InlineKeyboardButton("Присоединиться", callback_data=f"{query.from_user.id}_#_{mode}_{session_id}")
        markup = InlineKeyboardMarkup().add(join_btn)
        results.append(InlineQueryResultArticle(
            id=f"{mode}_{session_id}",
            title=title,
            input_message_content=content,
            reply_markup=markup
        ))
    nim_bot.answer_inline_query(query.id, results)


@nim_bot.callback_query_handler(func=lambda c: '_#_' in c.data)
def join_inline_game(callback):
    parts = callback.data.split('_#_', 1)
    owner_str, tail = parts
    mode, session_id = tail.split('_', 1) if '_' in tail else (None, None)

    try:
        owner_id = int(owner_str)
    except ValueError:
        return safe_callback_response(callback.id, "Ошибка.")

    if callback.from_user.id == owner_id:
        return safe_callback_response(callback.id, "Ждём оппонента.")
    if session_id in game_sessions:
        return safe_callback_response(callback.id, "Игра уже началась.")

    try:
        owner_name = nim_bot.get_chat(owner_id).first_name
    except:
        owner_name = "Игрок 1"

    if mode == 'classic':
        standard_heaps = [3, 5, 7]
        game_sessions[session_id] = {
            'heaps': standard_heaps,
            'participants': [owner_id, callback.from_user.id],
            'turn': 0,
            'last_action': ''
        }
        buttons = generate_pile_buttons(standard_heaps, session_id=session_id, is_inline=True)
        nim_bot.edit_message_text(
            f"Старт! Первым ходит {owner_name}",
            inline_message_id=callback.inline_message_id,
            reply_markup=buttons
        )
    elif mode == 'custom':
        pending_inline_games[session_id] = {
            'owner': owner_id,
            'opponent': callback.from_user.id,
            'inline_id': callback.inline_message_id
        }
        nim_bot.send_message(
            owner_id,
            "⚙️ Введите размеры куч через пробел (пример: 2 4 6):",
            reply_markup=ForceReply()
        )


@nim_bot.message_handler(func=lambda m: m.reply_to_message and 'Введите размеры куч' in m.reply_to_message.text)
def process_inline_custom_heaps(message):
    try:
        custom_heaps = list(map(int, message.text.split()))
        assert all(h > 0 for h in custom_heaps) and len(custom_heaps) > 0
    except:
        nim_bot.reply_to(message, "❌ Неверный формат. Пример: 2 4 6")
        return

    user_id = message.from_user.id
    for session_id, data in list(pending_inline_games.items()):
        if data['owner'] == user_id:
            game_sessions[session_id] = {
                'heaps': custom_heaps,
                'participants': [data['owner'], data['opponent']],
                'turn': 0,
                'last_action': ''
            }
            buttons = generate_pile_buttons(custom_heaps, session_id=session_id, is_inline=True)
            nim_bot.edit_message_text(
                f"✅ Игра началась! Первым ходит {message.from_user.first_name}",
                inline_message_id=data['inline_id'],
                reply_markup=buttons
            )
            del pending_inline_games[session_id]
            break


@nim_bot.callback_query_handler(func=lambda c: c.data.startswith('inline!,'))
def process_inline_turn(callback):
    user_id = callback.from_user.id
    for session_id in game_sessions:
        if 'participants' in game_sessions[session_id] and user_id in game_sessions[session_id]['participants']:
            current_session = game_sessions[session_id]
            break
    else:
        return safe_callback_response(callback.id, "Игра не найдена.")

    if current_session['participants'][current_session['turn']] != user_id:
        return safe_callback_response(callback.id, "Сейчас не ваш ход.")

    _, heap_str, take_str = callback.data.split(',')
    heap_idx, stones_taken = int(heap_str), int(take_str)
    current_session['heaps'][heap_idx] -= stones_taken
    player_name = callback.from_user.first_name
    current_session['last_action'] = f"{player_name} снял(а) {stones_taken} из кучи {heap_idx + 1}."

    if sum(current_session['heaps']) == 0:
        nim_bot.edit_message_text(f"{current_session['last_action']}\n🏆 Победитель: {player_name}",
                               inline_message_id=callback.inline_message_id)
        del game_sessions[session_id]
        return

    current_session['turn'] ^= 1
    next_player_id = current_session['participants'][current_session['turn']]
    try:
        next_player = nim_bot.get_chat(next_player_id).first_name
    except:
        next_player = "Игрок 2"

    new_buttons = generate_pile_buttons(current_session['heaps'], session_id=session_id, is_inline=True)
    status_text = f"{current_session['last_action']}\nХод: {next_player}"
    nim_bot.edit_message_text(status_text, inline_message_id=callback.inline_message_id, reply_markup=new_buttons)


if __name__ == '__main__':
    nim_bot.polling()
