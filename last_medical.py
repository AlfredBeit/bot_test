import os
import asyncio
import logging
import fitz  # PyMuPDF
import nest_asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from groq import Groq
import openai


# === CONFIGURATION ===
bot = Bot(token=os.getenv("API_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
openai.api_key =  os.getenv("openai_token")
# === FSM STATE ===
class CompareStates(StatesGroup):
    waiting_for_pdfs = State()

user_files = {}

# === PDF TEXT EXTRACTION ===
def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            text += page.get_text() + "\n"
    return text

# === GROQ COMPARISON ===
def compare_texts(text1, text2):
    prompt = f"""
    
    Ты — медицинский помощник. Сравни лабораторные анализы пациента. Ты общаешься на русском языке.
    
    Представь результат в виде структурированного, оформленного текста без markdown  и  без html разметки. 
    НЕ ПРОПУСКАЙ показатели, отчитывайся по всем показателям. Если в одном файле несколько страниц, просматривай все.
    
    Отвечай строго по шаблону вне зависимости от формата исходных даных:
                    Название анализа: из первого PDF-файла.  
                    

                    Дата взятия материала: дата из первого PDF-файла. 

                    показатель: значение (Референсный интервал: )
                    показатель: значение (Референсный интервал: )
                    ... (выведи все показатели) 
               
                    Название анализа: из второго PDF-файла.  

                    Дата взятия материала: дата из второго PDF-файла. 

                 
                    показатель: значение (Референсный интервал: )
                    показатель: значение (Референсный интервал: )
                    ... (выведи все показатели)
                    Резюме: твое экспертное краткое резюме по динамике.

    Анализ 1:
    {text1}
    
    Анализ 2:
    {text2}
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Ты врач общей практики, отвечаешь на русском языке."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# === COMMAND START ===
@dp.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли два PDF-файла с анализами (по одному сообщению на файл).")
    user_files[message.from_user.id] = []
    await state.set_state(CompareStates.waiting_for_pdfs)

# === PDF RECEIVED ===
@dp.message(CompareStates.waiting_for_pdfs)
async def pdf_received(message: types.Message, state: FSMContext):
    if not message.document:
        await message.answer("⚠️ Пожалуйста, отправь PDF-файл.")
        return

    user_id = message.from_user.id
    file = await bot.download(message.document)
    file_path = f"user_{user_id}_{len(user_files[user_id]) + 1}.pdf"
    with open(file_path, "wb") as f:
        f.write(file.read())
    user_files[user_id].append(file_path)

    if len(user_files[user_id]) < 2:
        await message.answer("✅ Файл получен. Жду ещё один PDF.")
    else:
        await message.answer("🔍 Сравниваю анализы...")

        # --- Обработка PDF и сравнение
        text1 = extract_text_from_pdf(user_files[user_id][0])
        text2 = extract_text_from_pdf(user_files[user_id][1])
        result = compare_texts(text1, text2)

        await message.answer("📊 Вот результат сравнения анализов:\n\n" + result)

        # --- Очистка файлов
        for path in user_files[user_id]:
            os.remove(path)
        user_files[user_id] = []
        await state.clear()

if __name__ == "__main__":
    nest_asyncio.apply()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dp.start_polling(bot))







