from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext

from aiogram.types.message import ContentType
from aiogram import Dispatcher, Bot, types
from aiogram.types import LabeledPrice
from aiogram.utils import executor

from configGPT import *
from ai_funcs import *
from db_funcs import *
import configGPT

import threading
import asyncio


loop = asyncio.get_event_loop()
ud = {}
storage = MemoryStorage()
bot = Bot(TOKEN)
dp = Dispatcher(bot, storage=storage)

class GptStates(StatesGroup):
    business_type = State()
    question = State()
    membership = State()
    payment_type = State()
    prompt_asking = State()
    ai_dialogue = State()

async def pay_func(message: types.Message, apitoken):
    if apitoken.split(':')[1] == 'TEST':
        await bot.send_message(message.chat.id, "Тестовый платеж!!!")

    await bot.send_invoice(message.chat.id,
                           title=price_txts[ud[message.from_id]['lang']][0], # 0
                           description=price_txts[ud[message.from_id]['lang']][1], # 1
                           provider_token=apitoken,
                           currency="uzs",
                           photo_url="https://www.aroged.com/wp-content/uploads/2022/06/Telegram-has-a-premium-subscription.jpg",
                           photo_width=416,
                           photo_height=234,
                           photo_size=416,
                           is_flexible=False,
                           prices=[LabeledPrice(label=price_txts[ud[message.from_id]['lang']][2], amount=16000*100)], # 2
                           start_parameter="one-month-subscription",
                           payload="test-invoice-payload")

@dp.message_handler(commands=['give', 'take'])
async def manipulatePrem_func(message: types.Message):
    # if message.from_id != ADMINID: return
    if message.from_id != 798330024: return

    uid = message.text.split(' ') #* uid[0] = /give or /take | uid[1] - [users id] | uid[2] - [username]

    if '/take' in uid[0]:
        try: 
            deleteUser(int(uid[1]))
            await bot.send_message(message.from_id, 'done')
        except Exception as e:
            await bot.send_message(message.from_id, f'failed to take prem due this problem: {e}')

    elif '/give' in uid[0]:
        if len(uid) != 3:
            await bot.send_message(message.from_id, 'invalid command')
            return
        try: 
            insertNewPaidUser(uid[1], uid[2])
            await bot.send_message(message.from_id, 'done')
        except Exception as e:
            await bot.send_message(message.from_id, f'failed to give prem due this problem: {e}')

@dp.message_handler(commands='db')
async def getDB(message: types.Message):
    # if message.from_id != ADMINID: return
    if message.from_id != 798330024: return

    with open(DB_PATH, 'rb') as file:
        await bot.send_document(message.from_id, file)

@dp.pre_checkout_query_handler(lambda query: True)
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    global ud

    pmnt = message.successful_payment.to_python()

    ud[message.from_id]['paid'] = True
    ud[message.from_id]['freeqs'] = True

    try:insertNewPaidUser(message.from_id, message.from_user)
    except Exception as e: await bot.send_message(receipt_channel_id, f'adding @{message.from_username} to db failed')

    await bot.send_message(receipt_channel_id, pmnt)

    await bot.send_message(message.from_id, successful_payment_msg[ud[message.from_id]['lang']])

async def login(message):
    global ud
    #* is user is new
    if ud.get(message.from_id) == None:
        ud[message.from_id] = {
            'lang': None,
            'freeqs': 1,
            'paid': True,
            'context': None,
            'answers': ''
        }

async def setContext_func(uid, text):
    ud[uid]['context'] = text

@dp.message_handler(commands='lang')
async def selectLanguage_func(message: types.Message):
    await bot.send_message(message.from_id, 'Нажмите /ru, чтобы выбрать русский язык\n\nO\'zbek tilini tanlash uchun /uz tugmasini bosing')

@dp.message_handler(commands=['ru', 'uz'])
async def setLanguage_func(message: types.Message):
    if message.chat.type != 'private': return

    #* adding language settings to user 
    ud[message.from_id]['lang'] = message.text.replace('/', '')

    #* greeting user with specified language
    await bot.send_message(message.from_id, welcome_msg[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))

async def ai_callback_func(uid, data):
    ud[uid]['answer'] = data

def getAnswerFromAI(chatid, q, c, save=False):
    if save:
        asyncio.run_coroutine_threadsafe(
            ai_callback_func(chatid, askAi_func(q, c)),
            loop
        )
    else:
        asyncio.run_coroutine_threadsafe(
            bot.send_message(
                chat_id = chatid,
                text = askAi_func(q, c),
                parse_mode='Markdown'
            ),
            loop
        )

@dp.message_handler(commands='start')
async def welcome(message: types.Message):
    if message.chat.type != 'private': return
    await login(message)
    try: await bot.send_message(message.from_id, welcome_msg[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
    except KeyError: await selectLanguage_func(message)

#TODO make it trans-languaged
@dp.message_handler(content_types='text')
async def main(message: types.Message):
    if message.chat.type != 'private': return

    if ud[message.from_id].get('lang') == None:
        await selectLanguage_func(message)
        return

    ulang = ud[message.from_id]['lang']

    if message.text == cancel_btn[ulang][1]:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ulang))

    #* handling first button from main_menu
    elif message.text == main_menu_lang_list[ulang][0]:
        await bot.send_message(message.from_id, prompt_questions[0], parse_mode='html', reply_markup=getBackBtn(ulang))
        await GptStates.prompt_asking.set()

    #* handling second button from main_menu
    elif message.text == main_menu_lang_list[ulang][1]:
        await bot.send_message(message.from_id, business_type_msg[ulang], reply_markup=getBackBtn(ulang))
        await GptStates.business_type.set()

    #* handling third button from main_menu
    elif message.text == main_menu_lang_list[ulang][2]:
        #* if user has the membership
        if ud[message.from_id]['paid']:
            await bot.send_message(message.from_id, free_dialogue_waiting_for_question[ulang], reply_markup=getBackBtn(ulang))
            await GptStates.ai_dialogue.set()

        elif not ud[message.from_id]['paid']:
            await bot.send_message(message.from_id, cant_have_dialogue[ulang], reply_markup=getMainMenu(ulang))

    #* handling fourth button from main_menu
    elif message.text == main_menu_lang_list[ulang][3]:
        await bot.send_message(message.from_id, userarea_txt[ulang], reply_markup=getUserAreaMenu(ulang))

    elif message.text == userarea_menu_lang_list[ulang][0]:
        if ud[message.from_id]['paid']:
            await bot.send_message(message.from_id, already_have_membership[ulang])
        else:
            await bot.send_message(message.from_id, payment_choice_msg[ulang], reply_markup=getPaymentTypes(ulang))
            await GptStates.payment_type.set()

    elif message.text == userarea_menu_lang_list[ulang][1]:
        await bot.send_message(message.from_id, manager_info[ulang])

    elif message.text == userarea_menu_lang_list[ulang][2]:
        await bot.send_message(message.from_id, about_msg[ulang])

    #* if user entered something else
    else:
        await bot.send_message(message.from_id, unknown[ulang])

@dp.message_handler(state=GptStates.ai_dialogue)
async def handleDialogue_func(message: types.Message, state: FSMContext):
    await state.update_data(umsg = message.text)
    data = await state.get_data()

    if message.text in ['/lang', '/start', 'отмена', 'назад', 'bekor qilish', 'orqaga']:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
        await state.finish()
        return
    else:
        x = threading.Thread(target=getAnswerFromAI, args=(message.from_id, data['umsg'], fdc))
        x.start()

@dp.message_handler(state=GptStates.prompt_asking)
async def askPromptQuestions_func(message: types.Message, state: FSMContext):
    await state.update_data(answer = message.text)
    data = await state.get_data()

    if message.text in ['/lang', '/start', 'отмена', 'назад', 'bekor qilish', 'orqaga']:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
        await state.finish()
        return
    else:
        if not bool(ud[message.from_id]['answers']):
            ud[message.from_id]['answers'] = data['answer']
        else:
            ud[message.from_id]['answers'] = f"{ud[message.from_id]['answers']};{data['answer']}"

        steps_done = ud[message.from_id]['answers'].count(';')

        print(steps_done)
        print(ud[message.from_id]['answers'])

        if steps_done != 11:
            await bot.send_message(message.from_id, prompt_questions[steps_done+1], parse_mode='html')
            await GptStates.prompt_asking.set()
        
        elif steps_done == 11:
            if ud[message.from_id]['lang'] == 'ru': 
                configGPT.pbadc += 'ответ дай на русском языке'
            else: 
                configGPT.pbadc += 'ответ дай на узбекском языке'
            x = threading.Thread(target=getAnswerFromAI, args=(message.from_id, 'questions: {0}\n\nanswers: {1}'.format(pqs, ud[message.from_id]["answers"].replace(";", "\n")), pbadc))
            x.start()

            await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']])
            ud[message.from_id]['answers'] = ''
            await state.finish()
            return

@dp.message_handler(state=GptStates.business_type)
async def chooseBusinessType_func(message: types.Message, state: FSMContext):
    await state.update_data(btype = message.text)
    data = await state.get_data()

    if message.text in ['/lang', '/start', 'отмена', 'назад', 'bekor qilish', 'orqaga']:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
        await state.finish()
        return
    else:
        if data['btype'] == 'маркетплейсы':
            await bot.send_message(message.from_id, 'some text...')
            await bot.send_message(message.from_id, marketplace_qna[ud[message.from_id]['lang']])
            await GptStates.question.set()

        elif data['btype'] == 'партнёрская программа':
            await bot.send_message(message.from_id, membership_msg[ud[message.from_id]['lang']])
            await GptStates.membership.set()

        else:
            await bot.send_message(message.from_id, invalid_question_msg[ud[message.from_id]['lang']])
            await GptStates.business_type.set()

@dp.message_handler(state=GptStates.membership)
async def handleMembership_func(message: types.Message, state: FSMContext):
    await state.update_data(phone = message.text)
    data = await state.get_data()

    if message.text in ['/lang', '/start', 'отмена', 'назад', 'bekor qilish', 'orqaga']:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
        await state.finish()
        return
    else:
        phone = data['phone']\
            .replace('-', '')\
            .replace('+', '')\
            .replace('(', '')\
            .replace(')', '')\
            .replace(' ', '')

        if phone.isnumeric():
            await bot.send_message(receipt_channel_id, f'NEW PHONE NUMBER\n{phone}')
            await bot.send_message(message.from_id, f"", reply_markup=getMainMenu(ud[message.from_id]['lang']))
        else:
            await bot.send_message(message.from_id, invalid_phone_num[ud[message.from_id]['lang']])

@dp.message_handler(state=GptStates.payment_type)
async def setPaymentType_func(message: types.Message, state: FSMContext):
    await state.update_data(pt = message.text) #? pt - Payment Type
    data = await state.get_data()

    if message.text in ['/lang', '/start', 'отмена', 'назад', 'bekor qilish', 'orqaga']:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
        await state.finish()
        return
    else:
        if data['pt'] in ['CLICK', 'Paycom']:
            await state.finish()
            await pay_func(message, payment_apis[data['pt']])

@dp.message_handler(state=GptStates.question)
async def answerTheQuestion_func(message: types.Message, state: FSMContext):
    await state.update_data(q = message.text)
    data = await state.get_data()

    if message.text in ['/lang', '/start', 'отмена', 'назад', 'bekor qilish', 'orqaga']:
        await bot.send_message(message.from_id, mm_return[ud[message.from_id]['lang']], reply_markup=getMainMenu(ud[message.from_id]['lang']))
        await state.finish()
        return
    else:
        #* if user has no free questions
        if not ud[message.from_id]['freeqs']:
            await bot.send_message(message.from_id, membership_propose[ud[message.from_id]['lang']])
        else:
            x = threading.Thread(target=getAnswerFromAI, args=(message.from_id, data['q'], atqc, True))
            x.start()

        #* if user has 1 free question and asked a relevant question
        if ud[message.from_id]['answer'] not in pnq['n'] and ud[message.from_id]['freeqs']:
            await bot.send_message(message.from_id, ud[message.from_id]['answer'])
            #* if user didn't subscribe for our bot
            if not ud[message.from_id]['paid']:
                ud[message.from_id]['freeqs'] = False
                await bot.send_message(message.from_id, membership_propose[ud[message.from_id]['lang']])
            ud[message.from_id]['answer'] = ''

        #* if user asked a non relevant question
        else:
            await bot.send_message(message.from_id, invalid_question_msg[ud[message.from_id]['lang']])
            await GptStates.question.set()

executor.start_polling(dp)
#| coded by c0dem