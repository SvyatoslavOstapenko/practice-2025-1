import logging
import os
import random
import io
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes
)

# Настройки
TOKEN = "7940460925:AAG3YzhTVOKyiWnUp970Rb9hqTf1dls7myg"
ADMIN_ID = 754033812

# Состояния бота
MAIN_MENU, PLAYING_SOUND_GAME, PLAYING_WORD_GAME, WAITING_PHOTO = range(4)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Данные для игр
SOUNDS = {
    "🚗 Автомобиль": "sounds/car_horn.mp3",
    "🚨 Сирена": "sounds/siren.mp3",
    "🐦 Птицы": "sounds/birds.mp3"
}

WORDS = {
    "Животные": ["слон", "жираф", "панда"],
    "Техника": ["телефон", "ноутбук", "наушники"]
}

# Меню
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🎮 Угадай звук", callback_data='sound_game')],
        [InlineKeyboardButton("🔠 Угадай слово", callback_data='word_game')],
        [InlineKeyboardButton("📷 Распознать текст", callback_data='recognize_text')],
        [InlineKeyboardButton("🆘 Помощь", callback_data='help')]
    ]
    return InlineKeyboardMarkup(keyboard)

### Основные обработчики ###
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Выберите игру или функцию:",
        reply_markup=get_main_menu()
    )
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'sound_game':
        return await start_sound_game(update, context)
    elif query.data == 'word_game':
        return await start_word_game(update, context)
    elif query.data == 'recognize_text':
        await query.edit_message_text("📷 Отправьте фото с текстом")
        return WAITING_PHOTO
    elif query.data == 'help':
        await query.edit_message_text("🆘 Помощь отправлена администратору")
        await context.bot.send_message(ADMIN_ID, f"Пользователь {update.effective_user.full_name} запросил помощь")
    elif query.data == 'back':
        await query.edit_message_text("Главное меню:", reply_markup=get_main_menu())
    
    return MAIN_MENU

### Игра "Угадай звук" ###
async def start_sound_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['game'] = {
        'type': 'sound',
        'score': 0,
        'round': 1,
        'total_rounds': 3
    }
    return await play_sound_round(update, context)

async def play_sound_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game = context.user_data['game']
    sound_name, sound_file = random.choice(list(SOUNDS.items()))
    
    with open(sound_file, 'rb') as f:
        await update.callback_query.message.reply_audio(audio=f)
    
    options = random.sample(list(SOUNDS.keys()), 3)
    if sound_name not in options:
        options[0] = sound_name
    
    keyboard = [
        [InlineKeyboardButton(opt, callback_data=f"sound_{opt}")] for opt in options
    ]
    keyboard.append([InlineKeyboardButton("🏁 Завершить", callback_data='end_game')])
    
    await update.callback_query.edit_message_text(
        f"🔊 Раунд {game['round']}/3. Что это за звук?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    context.user_data['correct_answer'] = sound_name
    return PLAYING_SOUND_GAME

async def check_sound_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_answer = query.data.replace("sound_", "")
    game = context.user_data['game']
    
    if user_answer == context.user_data['correct_answer']:
        game['score'] += 1
        result = "✅ Верно!"
    else:
        result = f"❌ Неверно! Правильный ответ: {context.user_data['correct_answer']}"
    
    game['round'] += 1
    
    if game['round'] > game['total_rounds']:
        return await end_game(update, context)
    
    await query.edit_message_text(
        f"{result}\nСчет: {game['score']}/{game['round']-1}\n\nГотовы к следующему раунду?",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Продолжить", callback_data='next_round')]])
    )
    return PLAYING_SOUND_GAME

### Игра "Угадай слово" ###
async def start_word_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = random.choice(list(WORDS.keys()))
    word = random.choice(WORDS[category])
    
    context.user_data['game'] = {
        'type': 'word',
        'word': word,
        'hints_used': 0,
        'letters_guessed': []
    }
    
    await update.callback_query.edit_message_text(
        f"📚 Категория: {category}\n"
        f"🔡 Слово: {'_ ' * len(word)}\n"
        f"❔ Угадайте букву или всё слово",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Подсказка", callback_data='hint')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')]
        ])
    )
    return PLAYING_WORD_GAME

async def handle_word_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game = context.user_data['game']
    user_input = update.message.text.lower()
    
    if user_input == game['word']:
        await update.message.reply_text(f"🎉 Верно! Это слово '{game['word']}'")
        return await end_game(update, context)
    
    if len(user_input) == 1 and user_input.isalpha():
        if user_input in game['word']:
            if user_input not in game['letters_guessed']:
                game['letters_guessed'].append(user_input)
            await update.message.reply_text(f"✅ Буква '{user_input}' есть в слове!")
        else:
            await update.message.reply_text(f"❌ Буквы '{user_input}' нет в слове")
    
    masked_word = ' '.join(
        letter if letter in game['letters_guessed'] else '_'
        for letter in game['word']
    )
    await update.message.reply_text(
        f"Слово: {masked_word}\n"
        f"Использовано подсказок: {game['hints_used']}/3",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Подсказка", callback_data='hint')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')]
        ])
    )
    return PLAYING_WORD_GAME

async def give_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = context.user_data['game']
    
    if game['hints_used'] < 3:
        game['hints_used'] += 1
        hidden_letters = [letter for letter in game['word'] if letter not in game['letters_guessed']]
        hint_letter = random.choice(hidden_letters)
        game['letters_guessed'].append(hint_letter)
        
        masked_word = ' '.join(
            letter if letter in game['letters_guessed'] else '_'
            for letter in game['word']
        )
        
        await query.edit_message_text(
            f"💡 Подсказка: буква '{hint_letter}'\n"
            f"Слово: {masked_word}\n"
            f"Использовано подсказок: {game['hints_used']}/3",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💡 Подсказка", callback_data='hint')],
                [InlineKeyboardButton("🔙 Назад", callback_data='back')]
            ])
        )
    else:
        await query.answer("Вы использовали все подсказки!", show_alert=True)
    
    return PLAYING_WORD_GAME

### Распознавание текста ###
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo_file = await update.message.photo[-1].get_file()
        img_data = io.BytesIO()
        await photo_file.download_to_memory(img_data)
        
        img = Image.open(img_data).convert('L')
        img.save("temp.jpg")
        
        with open("temp.jpg", 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption="📄 Попробуйте выделить текст:",
                has_spoiler=True
            )
        
        os.remove("temp.jpg")
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text("❌ Не удалось обработать фото")
    
    await update.message.reply_text("Главное меню:", reply_markup=get_main_menu())
    return MAIN_MENU

### Общие функции ###
async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game = context.user_data['game']
    if game['type'] == 'sound':
        await update.callback_query.edit_message_text(
            f"🎉 Игра окончена! Ваш результат: {game['score']}/{game['total_rounds']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        )
    else:
        await update.callback_query.edit_message_text(
            "🎉 Игра окончена!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data='back')]])
        )
    return MAIN_MENU

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(handle_main_menu)],
            PLAYING_SOUND_GAME: [
                CallbackQueryHandler(check_sound_answer, pattern='^sound_'),
                CallbackQueryHandler(end_game, pattern='^end_game$'),
                CallbackQueryHandler(play_sound_round, pattern='^next_round$')
            ],
            PLAYING_WORD_GAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word_guess),
                CallbackQueryHandler(give_hint, pattern='^hint$'),
                CallbackQueryHandler(handle_main_menu, pattern='^back$')
            ],
            WAITING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo),
                CallbackQueryHandler(handle_main_menu, pattern='^back$')
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("До свидания!"))]
    )
    
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == '__main__':
    main()