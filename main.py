import asyncio
import logging
import sys
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import openpyxl

TOKEN = "9266233542:AAHGZWWmW5NCJ5-iggfpsFob5PJ9VAAMrTE"
ADMIN_ID = 7680397179

bot = Bot(token=TOKEN)
dp = Dispatcher()

def db_start():
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            type TEXT, 
            text TEXT,
            status TEXT DEFAULT 'Korib chiqilmoqda',
            reply TEXT DEFAULT 'Hali javob berilmagan'
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS votes (user_id INTEGER PRIMARY KEY, direction TEXT)")
    
    try:
        cursor.execute("ALTER TABLE entries ADD COLUMN status TEXT DEFAULT 'Korib chiqilmoqda'")
        cursor.execute("ALTER TABLE entries ADD COLUMN reply TEXT DEFAULT 'Hali javob berilmagan'")
    except:
        pass
        
    conn.commit()
    conn.close()

db_start()

def add_user(user_id):
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def save_entry(user_id, entry_type, text):
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO entries (user_id, type, text) VALUES (?, ?, ?)", (user_id, entry_type, text))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def get_entry_by_id(entry_id):
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, type, text, status, reply FROM entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_entry_reply(entry_id, reply_text):
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE entries SET status = 'Javob berildi', reply = ? WHERE id = ?", (reply_text, entry_id))
    conn.commit()
    conn.close()

def save_vote(user_id, direction):
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO votes (user_id, direction) VALUES (?, ?)", (user_id, direction))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM entries")
    total_entries = cursor.fetchone()[0]
    cursor.execute("SELECT direction, COUNT(*) FROM votes GROUP BY direction")
    votes_data = cursor.fetchall()
    conn.close()
    return total_users, total_entries, votes_data

def generate_excel_report():
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, type, text, status, reply FROM entries")
    rows = cursor.fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Murojaatlar"
    ws.append(["ID", "User ID", "Bolim", "Matn", "Holati", "Javob"])
    for row in rows:
        ws.append(row)
    file_path = "murojaatlar_hisoboti.xlsx"
    wb.save(file_path)
    return file_path

class FormState(StatesGroup):
    waiting_for_text = State()
    waiting_for_check_id = State()
    waiting_for_admin_reply = State()

class BroadcastState(StatesGroup):
    waiting_for_broadcast_text = State()

user_entry_type = {}
admin_reply_target = {}

MOTIVATIONS = [
    "🚀 Bugungi qilgan kichik harakatingiz — ertangi katta muvaffaqiyatingiz poydevori!",
    "📚 Ilm olish — igna bilan quduq qazishdek gap, harakatdan to'xtamang!",
    "💡 Har bir xato — bu yangi tajriba va muvaffaqiyat sari tashlangan qadam.",
    "✨ Bugun boshqalardan ko'ra aqlliroq bo'lishga harakat qiling, kechagi o'zingizdan ko'ra emas!",
    "🎯 Maqsad sari qo'yilgan har bir kichik qadam sizni cho'qqiga yaqinlashtiradi.",
    "🌟 Imkoniyatlarni kutmang, ularni o'zingiz yarating!",
    "💪 Taslim bo'lish uchun hali juda erta, oldinda seni buyuk marralar kutmoqda!",
    "🔥 Bilim — bu eng kuchli qurol. Undan to'g'ri foydalanishni o'rgan!",
    "🏆 G'oliblar hech qachon taslim bo'lmaydi, taslim bo'lganlar hech qachon g'olib bo'lmaydi!",
    "💡 Bugungi o'qigan har bir sahifang — kelajaging uchun qo'yilgan g'ishtdir!",
    "🌟 Orzularingiz sari qat'iyat bilan odimlang!",
    "🔥 Har bir tong — bu yangi imkoniyat va yangi g'alaba demakdir.",
    "💡 O'zingizga ishoning, chunki siz o'ylaganingizdan ko'ra kuchliroqsiz.",
    "🚀 Katta maqsadlarga erishish kichik odimlardan boshlanadi.",
    "📚 Kitob — bu bilim bulog'i, undan doimo ichib turishni unutmang.",
    "✨ Harakatdagi barakani hech qachon unutm.",
    "💪 Qiyinchiliklar sizni sindirish uchun emas, balki chiniqtirish uchun keladi.",
    "🏆 Muvaffaqiyat — bu to'xtovsiz harakat natijasidir.",
    "💡 Bugungi mehnat — ertangi farovon hayot garovidir.",
    "🌟 Har bir kun o'ziga xos imkoniyatlarni taqdim etadi.",
    "🚀 Intilish bor joyda albatta natija bo'ladi.",
    "📚 Ilm — insonning eng yaqin do'stidir.",
    "✨ O'z ustingizda ishlashdan hech qachon charchamang.",
    "💪 Mag'lubiyatdan qo'rqmang, qo'rqinchning o'zi eng katta mag'lubiyatdir.",
    "🏆 Har bir urinish sizni maqsadga yaqinlashtiradi.",
    "💡 Har bir inson o'z taqdirining memordir.",
    "🌟 Bugungi sabr — ertangi muvaffaqiyat kalitidir.",
    "🚀 Orzularingiz ortidan quvishdan aslo to'xtamang.",
    "📚 Har bir o'qitilgan dars — aqlni charxlaydigan olmosdir.",
    "✨ Hayotdagi eng go'zal narsa — bu erishilgan maqsad lazzatidir.",
    "💪 Kuchli bo'lish — muammolardan qochish emas, ularni yengishdir.",
    "🏆 Har bir yangi kun — yangi imkoniyatlar sahifasi.",
    "💡 O'zingizga bo'lgan ishonch barcha eshiklarni ochadi.",
    "🌟 Harakat qilgan inson hech qachon yutqazmaydi.",
    "🚀 Kelajagingiz bugungi tanlovlaringizga bog'liq.",
    "📚 Kitobxonlik — tafakkurni kengaytiradigan buyuk yo'l.",
    "✨ Sabr va matonat barcha qiyinchiliklarni yengadi.",
    "💪 O'z salohiyatingizni ro'yobga chiqarishdan qo'rqmang.",
    "🏆 G'alaba shashtini hech qachon yo'qotmang.",
    "💡 Har bir to'siq — bu yangi cho'qqiga chiqish uchun poydevor.",
    "🌟 Dunyoni o'zgartirmoqchimisan? O'zingdan boshla!",
    "🚀 Har bir qadam — muvaffaqiyat sari tashlangan ishonchli iz.",
    "📚 Ilm yo'lida chekilgan zahmat — ertangi nurdir.",
    "✨ Yaxshi niyat — yarim saodat.",
    "💪 Har qanday qiyinchilik ortida yengillik bor.",
    "🏆 Maqsadsiz kema hech qanday shamoldan foyda ko'rmaydi.",
    "💡 O'qish, o'rganish va izlanish — muvaffaqiyat kaliti.",
    "🌟 Bugungi shijoat — ertangi muvaffaqiyat bayrog'i.",
    "🚀 Orzularingizga yetishish uchun bugundan harakatni boshlang.",
    "📚 Har bir o'rganilgan bilim — hayotdagi eng katta boylik.",
    "✨ Har bir inson o'z baxtining bunyodkoridir.",
    "💪 Taslim bo'lish oson, kurashish esa jasorat talab qiladi.",
    "🏆 Har bir g'alaba o'ziga bo'lgan ishonchni mustahkamlaydi.",
    "💡 Bilimli insonning yo'li doimo yorug' bo'ladi.",
    "🌟 O'zingizga ishoning, qolgani o'z-o'zidan keladi.",
    "🚀 Harakat — bu hayot mazmuni.",
    "📚 Kitoblar dunyoni tanitishning eng yaxshi vositasidir.",
    "✨ Sabrli bo'ling, eng yaxshi narsalar o'z vaqtida keladi.",
    "💪 Qiyinchiliklar sizni yanada bardoshli qiladi.",
    "🏆 Har bir yutuq ortida mashaqqatli mehnat yotadi.",
    "💡 Tafakkuringizni kengaytiring, dunyo qarashingiz o'zgaradi.",
    "🌟 Har bir tong sizga yangi imkoniyatlar olib keladi.",
    "🚀 O'z maqsadingiz sari qat'iy olg'a qadam tashlang.",
    "📚 Ilm va odob — insonning eng go'zal ziynati.",
    "✨ Har bir yaxshi niyat albatta o'z mukofotini oladi.",
    "💪 Mag'lubiyatdan saboq chiqara olgan kishi g'olibdir.",
    "🏆 Har bir bosqich — bu sizning o'sishishingizdir.",
    "💡 O'zingizni boshqalar bilan emas, kechagi o'zingiz bilan taqqoslang.",
    "🌟 Hayotda faqat oldinga qarab yashang.",
    "🚀 Shijoatingiz hech qachon so'nmasin.",
    "📚 Bilim olish hech qachon kech emas.",
    "✨ Har bir lahzadan unumli foydalanishni o'rganing.",
    "💪 Har qanday to'siqni yengib o'tish kuchiga egasiz.",
    "🏆 Muvaffaqiyat tasodif emas, u izchil mehnat natijasidir.",
    "💡 Har bir o'quv kuni — yangi zafarlar sari qadam.",
    "🌟 O'zingizni kashf eting va imkoniyatlaringizni ro'yobga chiqaring.",
    "🚀 Harakatdan to'xtamang, muvaffaqiyat yaqin!",
    "📚 Kitob o'qish — aqlni boyitishning eng sara yo'lidir.",
    "✨ Qalbimizdagi ezgulik dunyoni go'zallashtiradi.",
    "💪 Kuchli iroda har qanday qoyani eritadi.",
    "🏆 G'alaba sari intilishning o'zi katta baxtdir.",
    "💡 Har bir xato — bu mukammallikka erishish yo'lidagi darsdir.",
    "🌟 O'ziga ishongan inson har qanday cho'qqini zabt etadi.",
    "🚀 Bugungi harakat — ertangi farovonlik.",
    "📚 Ilm — bu bitmas-tuganmas xazina.",
    "✨ Yaxshilik qilishdan charchamang.",
    "💪 Sabr — qiyinchiliklarni yenguvchi eng buyuk qalqon.",
    "🏆 Har bir urinish sizni yanada tajribali qiladi.",
    "💡 O'zingizga bo'lgan ishonch — har qanday ishning yarmi.",
    "🌟 Kelajagingiz porloq bo'lishini istasangiz, bugun harakat qiling.",
    "🚀 Maqsadingiz sari ishonch bilan qadam tashlang.",
    "📚 Har bir sahifa — yangi olam.",
    "✨ Hayot qiziq va imkoniyatlarga to'la.",
    "💪 Har qanday qiyin vaziyatdan chiqish yo'li bor.",
    "🏆 Muvaffaqiyat zinapoyasidan dadil ko'tariling.",
    "💡 Bilim va aqlni hech kim sizdan tortib ololmaydi.",
    "🌟 Bugungi kuningiz kechagidan yaxshiroq bo'lsin.",
    "🚀 O'z yo'lingizdan adashmang va olg'a intiling.",
    "📚 Kitob — sadoqatli do'st va maslahatchi.",
    "✨ Ezgu niyatlar bilan boshlangan har bir ish barokatli bo'ladi.",
    "💪 Har qanday og'riq va qiyinchilik sizni kuchliroq qiladi.",
    "🏆 G'oliblar doim izlanishda bo'lishadi.",
    "💡 O'zingizni qadrlang va salohiyatingizga ishoning.",
    "🌟 Har bir tong — yangi sahifa, uni yaxshi amallar bilan to'ldiring.",
    "🚀 O'z kelajagingizning me'mori o'zingizsiz.",
    "📚 Ilm yo'li — nurli va saodatli yo'ldir.",
    "✨ Har bir qilingan yaxshilik o'zingizga qaytadi.",
    "💪 Matonat va shijoat har qanday devorni yiqitadi.",
    "🏆 Maqsadsiz yashash — mazmunsiz yashashdir, katta maqsad qo'ying.",
    "💡 O'qish va izlanish — yoshlikning eng asosiy vazifasidir.",
    "🌟 Har bir inson o'z baxtining ustasidir.",
    "🚀 Harakatdan to'xtagan kishi ortda qoladi.",
    "📚 Har bir bilim — qo'lingizdagi oltin kalit.",
    "✨ Qiyinchiliklar vaqtinchadir, erishilgan natija abadiydir.",
    "💪 O'z qobiliyatingizga shubha qilmang.",
    "🏆 Muvaffaqiyat — bu har kuni takrorlanadigan kichik g'alabalar yig'indisi.",
    "💡 Aqlli va bilimli bo'lish — har doim zamonaviy.",
    "🌟 O'zingizga bo'lgan ishonchni hech qachon yo'qotmang.",
    "🚀 Shijoatli qadamlar muvaffaqiyatga eltadi.",
    "📚 Kitob mutolaasi fikrlashni kengaytiradi.",
    "✨ Hayotimizdagi har bir lahza qadrlidir.",
    "💪 Kuchli iroda egasi barcha qiyinchiliklarni yengadi.",
    "🏆 G'alaba shashtini oxirigacha saqlang.",
    "💡 Har bir yangi bilim — hayotdagi yangi imkoniyat.",
    "🌟 O'z ustingizda ishlashdan zavqlaning.",
    "🚀 Intiluvchanlik barcha eshiklarni ochadi.",
    "📚 Ilm — insonni ulug'laydigan buyuk kuch.",
    "✨ Ezgulik har doim g'alaba qozonadi.",
    "💪 Sabr va qat'iyat bilan barcha marralarga yetish mumkin.",
    "🏆 Maqsadingiz sari ishonch bilan olg'a!",
    "💡 O'zingizga ishoning va orzularingizdan voz kechmang.",
    "🌟 Har bir tong yangi umidlarni olib keladi.",
    "🚀 Hayotda doimo oldinga qarab yashang.",
    "📚 Bilim olgan inson hech qachon qoqilmaydi.",
    "✨ Yaxshi o'ylangan harakat muvaffaqiyat kalitidir.",
    "💪 Qiyinchiliklar oldida taslim bo'lmang.",
    "🏆 Muvaffaqiyat zavqini his qilish uchun kurashing.",
    "💡 Har bir dars — hayot uchun muhim saboq.",
    "🌟 O'z salohiyatingizni to'liq namoyon eting.",
    "🚀 Shijoatingiz so'nmasin, marralar yaqin.",
    "📚 Kitob — aqlni boyituvchi eng buyuk tabib.",
    "✨ Har bir inson o'z hayotining qahramonidir.",
    "💪 Matonatli insonlar har doim g'alaba qozonishadi.",
    "🏆 Katta muvaffaqiyatlar kichik qadamlardan boshlanadi.",
    "💡 Bilimli yoshlar — yurt kelajagi va tayanchi.",
    "🌟 O'zingizga bo'lgan ishonch — kuchingiz manbai.",
    "🚀 Harakatdan to'xtamang, zafarlar sizni kutmoqda!",
    "📚 Ilm va zakovat — eng buyuk qurol.",
    "✨ Ezgu maqsadlar sari birgalikda odimlaymiz."
]
current_quote_index = 0

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✍️ Anonim Murojaat", callback_data="type_murojaat"),
            InlineKeyboardButton(text="💡 Taklif va Fikrlar", callback_data="type_fikr")
        ],
        [
            InlineKeyboardButton(text="🎉 Tadbirlar (Ovoz)", callback_data="menu_tadbirlar"),
            InlineKeyboardButton(text="🔍 Murojaat holati", callback_data="check_status")
        ],
        [
            InlineKeyboardButton(text="🌟 Motivatsiya", callback_data="motivation"),
            InlineKeyboardButton(text="📞 Bog'lanish", callback_data="contact")
        ]
    ])

def get_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Elon yuborish", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="📁 Excel hisobot", callback_data="admin_excel")
        ]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer(
        f"Assalomu alaykum, <b>{message.from_user.first_name}</b>! 👋\n\n🤖 <b>@Ishonch_49bot</b> — barcha murojaat va ovozlar to'liq <b>anonim</b> qabul qilinadi.",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "menu_tadbirlar")
async def process_tadbirlar_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    add_user(callback.from_user.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚽ Sport", callback_data="vote_Sport"),
            InlineKeyboardButton(text="🎨 Ijod", callback_data="vote_Ijod")
        ],
        [
            InlineKeyboardButton(text="🧠 Zakovat", callback_data="vote_Zakovat"),
            InlineKeyboardButton(text="🚀 Fan", callback_data="vote_Fan")
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")
        ]
    ])
    await callback.message.edit_text("🎉 Qaysi yonalishdagi tadbirlarga ovoz berasiz?", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("vote_"))
async def process_voting(callback: CallbackQuery):
    add_user(callback.from_user.id)
    direction = callback.data.split("_")[1]
    save_vote(callback.from_user.id, direction)
    await callback.answer(f"✅ Ovozingiz '{direction}' yonalishiga qabul qilindi!", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text("🤖 Asosiy menyu:", reply_markup=get_main_menu())
    await callback.answer()

@dp.callback_query(F.data.in_({"type_murojaat", "type_fikr"}))
async def process_category(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    add_user(callback.from_user.id)
    
    titles = {
        "type_murojaat": "💬 Murojaat yoki shikoyatingizni yuboring:",
        "type_fikr": "💡 Taklif va goyalaringizni yozing:"
    }
    tag_names = {
        "type_murojaat": "Murojaat",
        "type_fikr": "Taklif"
    }
    
    user_entry_type[callback.from_user.id] = tag_names[callback.data]
    await callback.message.answer(titles[callback.data])
    await state.set_state(FormState.waiting_for_text)
    await callback.answer()

@dp.message(FormState.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
    add_user(message.from_user.id)
    e_type = user_entry_type.get(message.from_user.id, "Murojaat")
    
    entry_id = save_entry(message.from_user.id, e_type, message.text)
    
    await message.answer(
        f"✅ Xabaringiz qabul qilindi!\n\n🆔 Sizning raqamingiz: <b>#{entry_id}</b>",
        parse_mode="HTML"
    )
    
    admin_reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✍️ #{entry_id} ga javob yozish", callback_data=f"reply_to_{entry_id}")]
    ])
    
    await bot.send_message(
        ADMIN_ID, 
        f"🚨 Yangi xabar #{entry_id} ({e_type}):\n\n💬 {message.text}", 
        reply_markup=admin_reply_kb,
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data == "check_status")
async def start_check_status(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🔍 Tekshirmoqchi bolgan murojaat raqamini yuboring (masalan: 1):")
    await state.set_state(FormState.waiting_for_check_id)
    await callback.answer()

@dp.message(FormState.waiting_for_check_id)
async def process_check_id(message: Message, state: FSMContext):
    clean_id = message.text.replace("#", "").strip()
    if not clean_id.isdigit():
        await message.answer("❌ Faqat raqam kiriting:")
        return
        
    entry = get_entry_by_id(int(clean_id))
    if not entry:
        await message.answer("❌ Bunday raqamli murojaat topilmadi.")
        await state.clear()
        return
        
    e_id, _, e_type, e_text, status, reply = entry
    await message.answer(
        f"📄 Murojaat #{e_id}:\n\n📂 Bolim: {e_type}\n💬 Matn: {e_text}\n📊 Holati: {status}\n👮‍♂️ Javob: {reply}",
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data.startswith("reply_to_"))
async def admin_start_reply(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yoq!", show_alert=True)
        return
    entry_id = int(callback.data.split("_")[2])
    admin_reply_target[callback.from_user.id] = entry_id
    await callback.message.answer(f"✍️ #{entry_id} raqamli murojaat uchun javob yozing:")
    await state.set_state(FormState.waiting_for_admin_reply)
    await callback.answer()

@dp.message(FormState.waiting_for_admin_reply)
async def admin_send_reply(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    entry_id = admin_reply_target.get(message.from_user.id)
    entry = get_entry_by_id(entry_id)
    
    if entry:
        target_user_id = entry[1]
        update_entry_reply(entry_id, message.text)
        await message.answer(f"✅ #{entry_id} ga javob yuborildi!")
        try:
            await bot.send_message(
                target_user_id,
                f"🔔 Sizning #{entry_id} murojaatingizga javob keldi:\n\n👮‍♂️ {message.text}"
            )
        except:
            pass
    await state.clear()

@dp.callback_query(F.data == "motivation")
async def process_motivation(callback: CallbackQuery):
    add_user(callback.from_user.id)
    global current_quote_index
    quote = MOTIVATIONS[current_quote_index]
    current_quote_index = (current_quote_index + 1) % len(MOTIVATIONS)
    await callback.message.answer(f"🌟 Kun motivatsiyasi:\n\n{quote}")
    await callback.answer()

@dp.callback_query(F.data == "contact")
async def process_contact(callback: CallbackQuery):
    add_user(callback.from_user.id)
    await callback.message.answer("📞 Admin: @XolmirzayevImronbek")
    await callback.answer()

@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yoq!")
        return
    await state.clear()
    await message.answer("👨‍💻 Admin Panel:", reply_markup=get_admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yoq!", show_alert=True)
        return
    total_users, total_entries, votes_data = get_stats()
    votes_text = "".join([f"▫️ {v[0]}: {v[1]} ta\n" for v in votes_data]) or "Ovozlar yoq.\n"
    
    stats_msg = f"📊 Statistika:\n\n👥 Foydalanuvchilar: {total_users}\n📥 Xabarlar: {total_entries}\n\n🎉 Ovozlar:\n{votes_text}"
    await callback.message.answer(stats_msg, reply_markup=get_admin_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_excel")
async def admin_excel_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yoq!", show_alert=True)
        return
    file_path = generate_excel_report()
    document = FSInputFile(file_path)
    await callback.message.answer_document(document=document, caption="📁 Excel hisoboti")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yoq!", show_alert=True)
        return
    await callback.message.answer("📢 Elon matnini yuboring:")
    await state.set_state(BroadcastState.waiting_for_broadcast_text)
    await callback.answer()

@dp.message(BroadcastState.waiting_for_broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("school_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()
    conn.close()
    
    success = 0
    for u in all_users:
        uid = u[0]
        try:
            await bot.send_message(uid, f"📢 Elon:\n\n{message.text}")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Yuborildi: {success} ta", reply_markup=get_admin_menu())
    await state.clear()

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print("Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
