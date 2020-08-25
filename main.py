import logging, threading, base64, config
import geopy.distance
from geopy.geocoders import Nominatim
from decimal import Decimal
import mysql.connector
import urllib.request, json
from io import BytesIO
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, CallbackQueryHandler)
from telegram.utils.request import Request

logging.basicConfig(filename=config.logfile,
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
token = config.main_token
updater = Updater(token, use_context=True)

logger = logging.getLogger(__name__)


def printnum(val):
    return '{:,}'.format(val).replace(',', ' ')

def encode_unicode(s):
    return base64.b64encode(s.encode()).decode()

def decode_unicode(s):
    return base64.b64decode(s.encode()).decode()

def remove_exponent(d):
    if d:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    else:
        return None

def db_execute_get_more(sql, data = None, commit=False, getrowid=False):
    global dbcfg;
    try:
        cnx = mysql.connector.connect(**config.dbcfg)
    except mysql.connector.Error as err:
        return False
    else:
        cursor = cnx.cursor()
        if data is None:
            cursor.execute(sql)
        else:
            cursor.execute(sql, data)
        if commit:
            cnx.commit()
            if getrowid:
                i = cursor.lastrowid
                cursor.close()
                cnx.close()
                return i
            cursor.close()
            cnx.close()
            return True
        res = cursor.fetchall()
        cursor.close()
        cnx.close()
        return res

def db_execute_multi(sql, datas):
    global dbcfg;
    try:
        cnx = mysql.connector.connect(**config.dbcfg)
    except mysql.connector.Error as err:
        return False
    else:
        cursor = cnx.cursor()
        for i in range(len(datas)):
            cursor.execute(sql, datas[i])
        cnx.commit()
        cursor.close()
        cnx.close()


sql = "SELECT * from words"
words = db_execute_get_more(sql)

CHOOSING, SEARCHING_CHOICE, DELIVERY_CHOICE, LANGUAGE_CHOICE, \
LOCATION_CHOICE, SAVING_NAME, SAVING_PHONE, SAVING_PHONE_INIT, \
SAVING_REGION, SETTINGS_LANGUAGE, ORDER_MAIN_CHOICE, \
ORDER_PRODUCTS_CHOICE, ORDER_PRODUCT_NUMBERS, ORDERING, \
ORDER_LOCATION_CHOICE, ORDER_LOCATION_MANUAL_CHOICE, CONFIRM_ORDER, SAVING_EXTRA_NOTE, SAVING_EXTRA_PHONE = range(19)

start_keyboard = [['🇺🇿 O\'zbekcha'],['🇷🇺 Русский']]
start_markup = ReplyKeyboardMarkup(start_keyboard, one_time_keyboard=True,  resize_keyboard=True)


def do_nothing(update, context):
    pass

def echo(update, context):
    conv_handler.handle_update(update, dp, ((update.message.from_user.id, update.message.from_user.id), MessageHandler(Filters.text, start), None), context)
    return LANGUAGE_CHOICE

def start(update, context):
    show_start_message(update, context)
    return LANGUAGE_CHOICE

def check_availability(update, context):
    sql='SELECT textvalue_uz, textvalue_ru FROM flugel_bot.settings where keyword="is_available" or keyword="is_not_available_reason"'
    res = db_execute_get_more(sql)
    status = int(res[0][0])
    if status:    
        sql='select (DATE_FORMAT(now(), "%H:%i")>(SELECT textvalue_uz FROM flugel_bot.settings where keyword="start_time") and \
    DATE_FORMAT(now(), "%H:%i")<(SELECT textvalue_uz FROM flugel_bot.settings where keyword="end_time")), \
    (SELECT textvalue_uz FROM flugel_bot.settings where keyword="start_time"), \
    (SELECT textvalue_uz FROM flugel_bot.settings where keyword="end_time");'
        res = db_execute_get_more(sql)
        if res[0][0]:
            return True
        else:
            if context.user_data['lang']=='uzbek':
                update.effective_message.reply_text("Ish vaqtimiz soat {} dan {} gacha. Hozir buyurtma qabul qilinmaydi. Noqulaylik uchun uzr so'raymiz.".format(res[0][1], res[0][2]))
            elif context.user_data['lang']=='russian':
                update.effective_message.reply_text("Мы работаем от {} до {}. На данный момент заказы не принимаются. Приносим свои извинения за доставленные неудобства.".format(res[0][1], res[0][2]))
            return False
    else:
        if context.user_data['lang']=='uzbek':
            update.effective_message.reply_text(res[1][0])
        elif context.user_data['lang']=='russian':
            update.effective_message.reply_text(res[1][1])
        return False        
    
def send_news():
    global updater
    msgs=[]
    sql = "SELECT message, image, id from news where issent=0"
    res = db_execute_get_more(sql)
    sql = "UPDATE news SET issent=1 WHERE issent=0"
    db_execute_get_more(sql, None, True)
    if res:
        sql = "SELECT DISTINCT userid from users where userid IS NOT NULL"
        chatids = db_execute_get_more(sql)
        for i in res:
            for j in chatids:
                try:
                    if i[1] and i[0]:
                        msg = updater.bot.send_photo(j[0], photo=BytesIO(i[1]), caption=i[0], parse_mode='HTML')
                    elif i[1]:
                        msg = updater.bot.send_photo(j[0], photo=BytesIO(i[1]))
                    elif i[0]:
                        msg = updater.bot.send_message(j[0], text=i[0], parse_mode='HTML')
                except:
                    pass
                else:
                    msgs.append([j[0], msg.message_id])
        sql = "INSERT INTO news_delete (messageid, data) VALUES(%s, %s)"
        data=(i[2], json.dumps(msgs))
        db_execute_get_more(sql, data, True)
    
def delete_news():
    sql = "SELECT id, data from news_delete where status=1"
    res = db_execute_get_more(sql)
    if res:
        for i in res:
            del_id=i[0]
            data = json.loads(i[1])
            for j in data:
                updater.bot.delete_message(j[0], j[1])
            sql = "UPDATE news_delete SET status=2 where id=%s"
            data=(del_id, )
            db_execute_get_more(sql, data, True)
def set_timer():
    due = 20
    threading.Timer(due, set_timer).start()
    send_news()
    delete_news()

def show_start_message(update, context):
    update.message.reply_text(
        "Restoranning onlayn xizmatiga xush kelibsiz. Tilni tanlang:\nДобро пожаловать в онлайн сервис ресторана. Выберите язык:",
        reply_markup=start_markup)

def tr(s, context):
    for word in words:
        if word[1]==s:
            if context.user_data['lang'] == "russian":
                return word[3]
            elif context.user_data['lang'] == "uzbek":
                return word[2]
    return "Not found"

def setPhoneKeyboard(update, context):
    sql = "SELECT count(*) as cnt FROM users WHERE userid=%s"
    data = (update.message.from_user.id, )
    res = db_execute_get_more(sql, data)
    if not (res[0][0]):
        sql = "INSERT INTO users(userid, name) VALUES (%s, %s)"
        data = (update.message.from_user.id, encode_unicode(update.message.from_user.full_name))
        db_execute_get_more(sql, data, True)
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(tr('phone_entering', context), request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text(tr('phone_enter', context), reply_markup=reply_markup)
    return SAVING_PHONE_INIT

def uzbek_choice(update, context):
    context.user_data['lang']="uzbek"
    return setPhoneKeyboard(update, context)

def russian_choice(update, context):
    context.user_data['lang']="russian"
    return setPhoneKeyboard(update, context)

def add_user_phone_init(update, context):
    sql = "UPDATE users SET phone = %s WHERE userid = %s"
    data = (update.message.contact.phone_number, update.message.from_user.id)
    db_execute_get_more(sql, data, True)
    return main_choice(update, context)

def main_choice(update, context):
    choice_keyboard = [['🛎 '+tr('order', context)],[tr('info', context)], ['⚙️ ' + tr('options', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(tr('make_order', context), reply_markup=choice_markup)
    return CHOOSING

def chooseback_choice(update, context):
    return setPhoneKeyboard(update, context)

def phoneback_choice(update, context):
    show_start_message(update, context)
    return LANGUAGE_CHOICE

def uzbek_settings_choice(update, context):
    context.user_data['lang']="uzbek"
    return settings_choice(update, context)

def russian_settings_choice(update, context):
    context.user_data['lang']="russian"
    return settings_choice(update, context)

def add_user_phone(update, context):
    sql = "UPDATE users SET phone = %s WHERE userid = %s"
    data = (update.message.contact.phone_number, update.message.from_user.id)
    db_execute_get_more(sql, data, True)
    update.message.reply_text(tr('info_saved', context));
    return settings_choice(update, context)

def add_user_name(update, context):
    text = encode_unicode(update.message.text)
    if len(text)>=256:
        update.message.reply_text(tr('too_long', context))
    else:
        sql = "UPDATE users SET name = %s WHERE userid = %s"
        data = (text, update.message.from_user.id)
        db_execute_get_more(sql, data, True)
        return settings_choice(update, context)

def name_settings_choice(update, context):
    keyboard=[['⬅️ '+tr('back', context)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.message.reply_text(tr('name_enter', context), reply_markup=reply_markup);
    return SAVING_NAME

def settings_choice(update, context):
    show_status(update, context)
    return LOCATION_CHOICE

def order_choice(update, context):
    if check_availability(update, context):
        context.user_data['acquired']=[]
        context.user_data['address'] = ""
        context.user_data['deliveryfee'] = 0
        keyboard = [['🚙 ' +tr('delivery', context), '🏃 '+tr('selfdelivery', context)], ['⬅️ '+tr('back', context)]]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        update.message.reply_text(tr('deliver_product', context), reply_markup=markup)
        return DELIVERY_CHOICE
        

def show_order_main_choice(update, context):
    keyboard = [['📥 '+tr('basket', context), '🍴 '+tr('menu', context)]]
    keys = []
    if context.user_data['lang']=='uzbek':
        sql = "SELECT id, uzbek from categories"
    elif context.user_data['lang']=='russian':
        sql = "SELECT id, russian from categories"
    result = db_execute_get_more(sql)
    for i in range(len(result)):
        keys.append(str(result[i][1]))
    for i in range(0, len(keys), 2):
        try:
            keyboard.append([keys[i], keys[i+1]])
        except:
            keyboard.append([keys[i]])
    keyboard.append(['⬅️ '+tr('back', context)])
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.message.reply_text(tr('do_order', context), reply_markup=markup)
    return ORDER_MAIN_CHOICE

def order_selfdelivery_choice(update, context):
    context.user_data['deliverytype']=1
    return show_order_main_choice(update, context)

def order_delivery_choice(update, context):
    context.user_data['deliverytype']=0
    return order_location_choice(update, context)

def order_location_choice(update, context):
    if 'latitude' in context.user_data:
        del context.user_data['latitude']
    if 'longitude' in context.user_data:
        del context.user_data['longitude']
    if 'orientation' in context.user_data:
        del context.user_data['orientation']
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton('📍 '+tr('location_entering', context), request_location=True), tr('location_entering_manual', context)], ['⬅️ '+tr('back', context)]], one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(tr('location_enter', context), reply_markup=reply_markup)
    return ORDER_LOCATION_CHOICE

def order_location_manual_choice(update, context):
    reply_markup = ReplyKeyboardMarkup([['⬅️ '+tr('back', context)]], one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(tr('orientation_entering', context), reply_markup=reply_markup)
    return ORDER_LOCATION_MANUAL_CHOICE

def order_location_auto_save(update, context):
    loc = update.message.location
    destlat = loc.latitude
    destlong = loc.longitude
    context.user_data['latitude']=loc.latitude
    context.user_data['longitude']=loc.longitude
    sql = "SELECT textvalue_uz from settings where keyword = 'delivery_startfee' or keyword='delivery_unitfee' or keyword='location' or keyword='delivery_startdist'"
    result = db_execute_get_more(sql)
    startfee = float(result[0][0])
    unitfee = float(result[1][0])
    loc = json.loads(result[2][0])
    startdist = float(result[3][0])
    srclat = loc['latitude']
    srclong = loc['longitude']
    src = (srclat, srclong)
    dest = (destlat, destlong)
    distance = geopy.distance.distance(src, dest).km
    locator = Nominatim(user_agent='myGeocoder')
    context.user_data['address'] = locator.reverse(str(destlat)+', '+str(destlong)).address
    if distance > startdist:
        context.user_data['deliveryfee'] = round(float(startfee)+float(unitfee)*round((distance-startdist), 1))
    else:
        context.user_data['deliveryfee'] = round(float(startfee))
    update.message.reply_text(tr('your_address', context)+' '+context.user_data['address'])
    update.message.reply_text(tr('approximate_delivery_fee', context)+' '+str(context.user_data['deliveryfee'])+' '+tr('som', context))
    return show_order_main_choice(update, context)

def order_location_manual_save(update, context):
    text = update.message.text
    if len(text)>=512:
        update.message.reply_text(tr('too_long', context))
        return order_location_manual_choice(update, context)
    context.user_data['orientation']=text
    sql = "SELECT textvalue_uz from settings where keyword = 'delivery_startfee' or keyword='delivery_unitfee' or keyword='delivery_startdist'"
    result = db_execute_get_more(sql)
    startfee = result[0][0]
    unitfee = result[1][0]
    startdist = result[2][0]
    if context.user_data['lang']=="uzbek":
        update.message.reply_text("Yetkazib berish xizmati {0} km ichida {1} so'm. Undan uzoq manzillarga har 1 km uchun {2} so'mdan qo'shiladi.".format(startdist, startfee, unitfee))
    elif context.user_data['lang']=="russian":
        update.message.reply_text("Стоимость доставки {0} сум в области {1} км. Если адрес вне зоны, то {2} сум от каждого километра.".format(startfee, startdist, unitfee))
    return show_order_main_choice(update, context)

def order_menu_choice(update, context):
    show_setting('menu_location', update, context)
#    update.message.reply_photo(open("Front.jpg", 'rb'))
#    update.message.reply_photo(open("Back.jpg", 'rb'))
    return show_order_main_choice(update, context)

def show_product_list(update, context, text):
    if context.user_data['lang']=='uzbek':
        sql = "SELECT uzbek from products where categoryid in (select id from categories where uzbek=%s)"
    elif context.user_data['lang']=='russian':
        sql = "SELECT russian from products where categoryid in (select id from categories where russian=%s)"
    keys = []
    keyboard = []
    result = db_execute_get_more(sql, (text, ))
    if result:
        for i in range(len(result)):
            keys.append(str(result[i][0]))
        keyboard.append(['⬅️ '+tr('back', context)])
        for i in range(0, len(keys), 2):
            try:
                keyboard.append([keys[i], keys[i+1]])
            except:
                keyboard.append([keys[i]])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        update.message.reply_text(tr('choose_product', context), reply_markup=markup)
        return ORDER_PRODUCTS_CHOICE

def order_list_products(update, context):
    context.user_data['last_category']=update.message.text
    return show_product_list(update, context, context.user_data['last_category'])

def order_list_products_back(update, context):
    return show_product_list(update, context, context.user_data['last_category'])

def order_basket_choice(update, context):
    if check_availability(update, context):
        inlinekeys = []
        keyboard = []
        inline = []
        t=""
        keyboard.append(['🚀 '+tr('doing_order', context), tr('delete', context)])
        keyboard.append(['⬅️ '+tr('back', context)])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
        acquired = context.user_data['acquired']
        if acquired:
            total = 0
            for i in range(len(acquired)):
                key = acquired[i][0]
                value = acquired[i][1]
                price = acquired[i][2]
                maxcount = acquired[i][3]
                total+=value*price
                t+='<b>'+key+'</b>'+'\n'
                t+=str(value)+' x '+str(printnum(remove_exponent(price)))+' = '+str(printnum(remove_exponent(value*price))) +' '+tr('som', context)+'\n'
                data={}
                data['action']='view'
                data['id'] = i
                inlinekeys.append(InlineKeyboardButton(key+": "+str(value), callback_data=json.dumps(data)))
                data={}
                data['action']='add'
                data['id'] = i
                inlinekeys.append(InlineKeyboardButton("➕", callback_data=json.dumps(data)))
                data={}
                data['action']='reduce'
                data['id'] = i
                inlinekeys.append(InlineKeyboardButton("➖", callback_data=json.dumps(data)))
                data={}
                data['action']='delete'
                data['id'] = i
                inlinekeys.append(InlineKeyboardButton("❌", callback_data=json.dumps(data)))
            for i in range(0, len(inlinekeys), 4):
                inline.append([inlinekeys[i]])
                inline.append([inlinekeys[i+1], inlinekeys[i+2], inlinekeys[i+3]])
            inlinemarkup=InlineKeyboardMarkup(inline)
            s=""
            if context.user_data['address']:
                s+=tr('your_address', context)+' '+str(context.user_data['address'])+'\n'
                s+=tr('approximate_delivery_fee', context)+' '+str(context.user_data['deliveryfee'])+' '+tr('som', context)
            else:
                if 'orientation' in context.user_data:
                    s+=tr('your_address', context)+' '+str(context.user_data['orientation'])
            s+='\n\n'

            s+=tr('spendings', context)+'\n' + t
            s+='\n'
            s+='<b>'+tr('overall', context)+' ' + str(printnum(remove_exponent(total))) +' '+tr('som', context) + '</b>'
            update.effective_message.reply_html(s, reply_markup=markup)
            s=tr('your_basket', context)
            update.effective_message.reply_text(s, reply_markup=inlinemarkup)
        else:
            update.effective_message.reply_text(tr('no_product', context), reply_markup=markup)
        return ORDERING

def manage_acquired(update, context):
    query = update.callback_query
    query.answer()
    data = json.loads(query.data)
    try:
        if data['action']=='view':
            s = get_product_text_and_photo(context.user_data['acquired'][int(data['id'])][0], update, context)
            update.effective_message.reply_html(s)
        elif data['action']=='reduce':
            product = context.user_data['acquired'][int(data['id'])]
            product[1]-=1
            if product[1]==0:
                context.user_data['acquired'].pop(int(data['id']))
        elif data['action']=='delete':
            context.user_data['acquired'].pop(int(data['id']))
        elif data['action']=='add':
            product = context.user_data['acquired'][int(data['id'])]
            if product[1]>=product[3]:
                update.effective_message.reply_text(tr('product_overflow', context)+str(product[3]))
            else:
                product[1]+=1
    except IndexError:
        pass
    return order_basket_choice(update, context)

def confirm_order(update, context):
    s = ""
    if 'extra_note' in context.user_data:
        s+=tr('extra_note', context) + ': ' + context.user_data['extra_note']+'\n'
    else:
        s+=tr('extra_note', context) + ': ' + tr('not_entered', context)+'\n'
    if 'extra_phone' in context.user_data:
        s+=tr('extra_phone', context) + ': ' + context.user_data['extra_phone']+'\n'
    else:
        s+=tr('extra_phone', context) + ': ' + tr('not_entered', context)+'\n'
    s+='\n'
    s+=tr('choose_action', context)
    keyboard=[]
    if 'extra_note' not in context.user_data:
        keyboard.append([InlineKeyboardButton(tr('extra_note', context), callback_data="extra_note")])
    if 'extra_phone' not in context.user_data:
        keyboard.append([InlineKeyboardButton(tr('extra_phone', context), callback_data="extra_phone")])
    keyboard.append([InlineKeyboardButton("❌ "+tr('cancel', context), callback_data="cancel"), InlineKeyboardButton("💾 "+tr('save', context), callback_data="save")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_message.reply_text(s, reply_markup=reply_markup)
    return CONFIRM_ORDER

def cancel_choice(update, context):
    clear_context_add(context)
    update.effective_message.reply_text(text=tr('information_cancelled', context))
    return main_choice(update, context)

def clear_context_add(context):
    if 'extra_note' in context.user_data:
        del context.user_data['extra_note']
    if 'extra_phone' in context.user_data:
        del context.user_data['extra_phone']

def save_choice(update, context):
    return order(update, context)

def save_extra_note(update, context):
    query = update.callback_query
    query.answer()
    keyboard=[['⬅️ '+tr('back', context)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(text=tr('enter_extra_note', context), reply_markup=reply_markup)
    return SAVING_EXTRA_NOTE

def add_extra_note(update, context):
    context.user_data['extra_note'] = update.message.text
    return confirm_order(update, context)

def save_extra_phone(update, context):
    query = update.callback_query
    query.answer()
    keyboard=[['⬅️ '+tr('back', context)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.effective_message.reply_text(text=tr('enter_extra_phone', context), reply_markup=reply_markup)
    return SAVING_EXTRA_PHONE

def add_extra_phone(update, context):
    context.user_data['extra_phone'] = update.message.text
    return confirm_order(update, context)

def order(update, context):
    if check_availability(update, context):
        query = update.callback_query
        query.answer
        if context.user_data['acquired']:
            if 'extra_note' not in context.user_data:
                context.user_data['extra_note'] = ""
            if 'extra_phone' not in context.user_data:
                context.user_data['extra_phone'] = ""
            sql = "SELECT id from users where userid=%s"
            data = (query.from_user.id, )
            result = db_execute_get_more(sql, data)
            if ('latitude' in context.user_data) and ('longitude' in context.user_data):
                sql = "INSERT into orders (userid, longitude, latitude, orientation, deliverytype, extra_note, extra_phone) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                data = (result[0][0], context.user_data['longitude'], context.user_data['latitude'], encode_unicode(context.user_data['address']), context.user_data['deliverytype'], context.user_data['extra_note'], context.user_data['extra_phone'])
            elif ('orientation' in context.user_data):
                sql = "INSERT into orders (userid, orientation, deliverytype, extra_note, extra_phone) VALUES (%s, %s, %s, %s, %s)"
                data = (result[0][0], encode_unicode(context.user_data['orientation']), context.user_data['deliverytype'], context.user_data['extra_note'], context.user_data['extra_phone'])
            else:
                sql = "INSERT into orders (userid, deliverytype, extra_note, extra_phone) VALUES (%s, %s, %s, %s)"
                data = (result[0][0], context.user_data['deliverytype'], context.user_data['extra_note'], context.user_data['extra_phone'])
            result = db_execute_get_more(sql, data, True, True)
            sql = "INSERT into ordered_products (productid, value, orderid) VALUES ((SELECT id from products WHERE {} = %s), %s, %s)".format(context.user_data['lang'])
            datas=[]
            for i in context.user_data['acquired']:
                data=(i[0], i[1], result)
                datas.append(data)
            db_execute_multi(sql, datas)
            sql = "SELECT textvalue_uz from settings where keyword = 'phone'"
            ph = db_execute_get_more(sql)[0][0]
            sql = "SELECT orders.id as id, name, date, phone, longitude, latitude, orientation, deliverytype from orders \
    left join users on orders.userid=users.userid \
    WHERE orders.id=%s"
            data = (result, )
            order = db_execute_get_more(sql, data)[0]
            sql = "select (select uzbek from products where products.id = productid) as uzbek, value, (select price from products where products.id = productid) as price \
    from ordered_products where orderid = %s"
            data = (result, )
            ordered_products = db_execute_get_more(sql, data)
            s = getorder(update, order, ordered_products)
            sql = "SELECT userid from users where sendorder=1"
            users_to_send = db_execute_get_more(sql)
            for i in users_to_send:
                if order[4] and order[5]:
                    updater.bot.send_location(i[0], order[5], order[4])
                updater.bot.send_message(i[0], s, parse_mode='HTML')
            update.effective_message.reply_html(tr('order_successful', context).format(result, ph))
            clear_context_add(context)
            return main_choice(update, context)
        else:
            return order_basket_choice(update, context)
    else:
        return order_basket_choice(update, context)


def getorder(update, order, ordered_products):
    s = ""
    if order[0]:
        s += 'Buyurtma raqami: ' + str(order[0]) +'\n'
    if order[1]:
        s += 'Buyurtmachining nomi: ' + decode_unicode(order[1]) +'\n'
    if order[2]:
        s += 'Buyurtma sanasi: ' + str(order[2]) +'\n'
    if order[3]:
        s += 'Buyurtmachining telefon raqami: <b>' + order[3] +'</b>\n'
    if order[6]:
        s += 'Buyurtmachining manzili: <b>' + decode_unicode(order[6]) +'</b>\n'
    s += 'Qanday yetkaziladi: ' + ('Olib ketish' if order[7] else '<b>Yetkazib berish</b>')  + '\n\n'
    s += 'Xarajatlar:\n'
    overall = 0
    for i in ordered_products:
        overall +=i[1]*i[2]
        s+=i[0]+': '+str(i[1])+' x '+str(remove_exponent(i[2]))+' = '+ str(remove_exponent(i[1]*i[2])) +' so\'m\n'
    s+='\n'
    s+="<b>Jami: "+str(remove_exponent(overall))+" so\'m</b>"
    return s

def order_delete_basket_choice(update, context):
    if context.user_data['acquired']:
        context.user_data['acquired']=[]
        update.message.reply_text(tr('basket_emptied', context))
    return order_basket_choice(update, context)

def order_product_numbers(update, context):
    if int(update.message.text)>context.user_data['maxcount']:
        update.message.reply_text(tr('product_overflow', context)+str(context.user_data['maxcount']))
    else:
        for i in context.user_data['acquired']:
            if i[0] == context.user_data['last_product']:
                i[1] += int(update.message.text)
                update.message.reply_text(tr('product_added', context))
                return show_order_main_choice(update, context)
        context.user_data['acquired'].append([context.user_data['last_product'], int(update.message.text), context.user_data['lastfee'], context.user_data['maxcount']])
        update.message.reply_text(tr('product_added', context))
        return show_order_main_choice(update, context)


def order_product_keyboard(update, context):
    keyboard=[['⬅️ '+tr('back', context)], ['1', '2', '3'],['4', '5', '6'],['7', '8', '9']]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,  resize_keyboard=True)
    s=get_product_text_and_photo(update.message.text, update, context, True)
    if s:
        update.message.reply_html(s)
        s=tr('enter_quantity', context)
        update.message.reply_html(s, reply_markup=markup)
        return ORDER_PRODUCT_NUMBERS
    else:
        update.message.reply_text(tr('invalid', context))
        return ORDER_PRODUCTS_CHOICE

def order_product(update, context):
    context.user_data['last_product']=update.message.text

    return order_product_keyboard(update, context)
def get_product_text_and_photo(text, update, context, getmaxcount=False):
    if context.user_data['lang']=='uzbek':
        sql = "SELECT uzbek, desc_uz, image, price, maxcount from products where uzbek=%s"
    elif context.user_data['lang']=='russian':
        sql = "SELECT russian, desc_ru, image, price, maxcount from products where russian=%s"
    data = (text, )
    results = db_execute_get_more(sql, data)
    if results:
        result = results[0]
        s='<b>'+result[0]+'</b>'+':\n\n'
        if result[1]:
            s+=result[1]+'\n'
        if result[3]:
            s+=tr('price', context)+' '+str(printnum(remove_exponent(result[3])))+' '+tr('som', context)
            context.user_data['lastfee'] = result[3]
        if result[2]:
            photo = result[2]
            update.effective_message.reply_photo(BytesIO(photo))
        if getmaxcount:
            if result[4]:
                context.user_data['maxcount'] = int(result[4])
            else:
                context.user_data['maxcount'] = 100
        return s
    else:
        return None

def show_setting(s, update, context):
    sql = "SELECT textvalue_uz, textvalue_ru, type, blobvalue from settings where keyword='{}'".format(s)
    res = db_execute_get_more(sql)[0]
    if context.user_data['lang']=='uzbek':
        value = res[0]
    elif context.user_data['lang']=='russian':
        if res[1]:
            value = res[1]
        else:
            value = res[0]
    t = res[2]
    blobvalue = res[3]
    if t==0:
        update.message.reply_text(value);
    elif t==1:
        j = json.loads(value)
        longitude = j['longitude']
        latitude = j['latitude']
        content = j['content']
        update.message.reply_text(content);
        update.message.reply_location(longitude, latitude)
    elif t==2:
        if value:
            update.message.reply_text(value);
        if blobvalue:
            update.message.reply_photo(BytesIO(blobvalue));

def about_choice(update, context):
    show_setting('about_content', update, context)
    return main_choice(update, context)

def phone_choice(update, context):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(tr('phone_entering', context), request_contact=True)]],  resize_keyboard=True)
    update.message.reply_text(tr('phone_enter', context), reply_markup=reply_markup)
    return SAVING_PHONE

def language_settings_choice(update, context):
    update.message.reply_text(tr('choose_lang', context), reply_markup=start_markup)
    return SETTINGS_LANGUAGE


def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    print(list(context))
    try:
        update.effective_message.reply_text(tr('error', context))
    except:
        pass

def show_status(update, context):
    sql = "SELECT id, phone, name FROM users WHERE userid=(%s)".format(context.user_data['lang'])
    data = (update.message.from_user.id, )
    res = db_execute_get_more(sql, data)
    s=""
    if (res[0][1]):
        s += tr('your_phone', context)+' '+res[0][1]
    else:
        s += tr('your_phone', context)+' '+tr('not_entered', context)
    s+='\n'
    if (res[0][2]):
        s += tr('your_name', context)+' '+decode_unicode(res[0][2])
    else:
        s += tr('your_name', context)+' '+tr('not_entered', context)
    s+='\n'
    s+='\n'
    s+=tr('change_info', context)
    choice_keyboard = [['⬅️ '+tr('back', context)], [tr('phone_change', context)], [tr('name_change', context)], [tr('language_change', context)]]
    choice_markup = ReplyKeyboardMarkup(choice_keyboard, one_time_keyboard=True,  resize_keyboard=True)
    update.message.reply_text(s, reply_markup=choice_markup)

def cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! I hope we can talk again some day.',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


dp = updater.dispatcher

conv_handler = ConversationHandler(
    entry_points=[
# MessageHandler(Filters.regex('^🇺🇿 O\'zbekcha$'),
#                                  uzbek_choice),
#    MessageHandler(Filters.regex('^🇷🇺 Русский'),
#            russian_choice),
    CommandHandler('start', start)],
    states={
        LANGUAGE_CHOICE: [MessageHandler(Filters.regex('^🇺🇿 O\'zbekcha$'),
                                  uzbek_choice),
                   MessageHandler(Filters.regex('^🇷🇺 Русский'),
                            russian_choice),
                   MessageHandler(Filters.all, do_nothing)
                            ],
        CHOOSING: [MessageHandler(Filters.regex('^🛎 Buyurtma$'),
                                  order_choice),
                   MessageHandler(Filters.regex('^🛎 Заказать$'),
                                  order_choice),
                   MessageHandler(Filters.regex('^Axborot$'),
                                  about_choice),
                   MessageHandler(Filters.regex('^Информация$'),
                                  about_choice),
                   MessageHandler(Filters.regex('^⚙️ Sozlanmalar$'),
                                  settings_choice),
                   MessageHandler(Filters.regex('^⚙️ Настройки$'),
                                  settings_choice),
                   MessageHandler(Filters.all, do_nothing)],
        LOCATION_CHOICE:[
                   MessageHandler(Filters.regex('^Telefon raqamini o\'zgartirish$'),
                                  phone_choice),
                   MessageHandler(Filters.regex('^Изменить номер телефона$'),
                                  phone_choice),
                   MessageHandler(Filters.regex('^Ismni o\'zgartirish$'),
                                  name_settings_choice),
                   MessageHandler(Filters.regex('^Изменить имя$'),
                                  name_settings_choice),
                   MessageHandler(Filters.regex('^Tilni o\'zgartirish$'),
                                  language_settings_choice),
                   MessageHandler(Filters.regex('^Изменить язык$'),
                                  language_settings_choice),
                   MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  main_choice),
                   MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  main_choice),
                   MessageHandler(Filters.all, do_nothing)
        ],
        SETTINGS_LANGUAGE: [MessageHandler(Filters.regex('^🇺🇿 O\'zbekcha$'),
                                  uzbek_settings_choice),
                   MessageHandler(Filters.regex('^🇷🇺 Русский'),
                            russian_settings_choice),
                MessageHandler(Filters.all, do_nothing)
                            ],
        SAVING_PHONE: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                      settings_choice),
           MessageHandler(Filters.regex('^⬅️ Назад$'),
                      settings_choice),
           MessageHandler(Filters.contact, add_user_phone),
           MessageHandler(Filters.all, do_nothing)],
        SAVING_PHONE_INIT: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                      start),
           MessageHandler(Filters.regex('^⬅️ Назад$'),
                      start),
           MessageHandler(Filters.contact, add_user_phone_init),
           MessageHandler(Filters.all, do_nothing)],
        SAVING_NAME: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                      settings_choice),
           MessageHandler(Filters.regex('^⬅️ Назад$'),
                      settings_choice),
           MessageHandler(Filters.text, add_user_name),
           MessageHandler(Filters.all, do_nothing)
           ],
        ORDER_LOCATION_CHOICE: [
                            MessageHandler(Filters.regex('^Qo\'lda kiritish$'),
                                  order_location_manual_choice),
                            MessageHandler(Filters.regex('^Ручное введение$'),
                                  order_location_manual_choice),
                            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  order_choice),
                            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  order_choice),
                            MessageHandler(Filters.location,
                                  order_location_auto_save),
                            MessageHandler(Filters.all, do_nothing)
                        ],
        ORDER_LOCATION_MANUAL_CHOICE: [
                            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  order_location_choice),
                            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  order_location_choice),
                            MessageHandler(Filters.text,
                                  order_location_manual_save),
                            MessageHandler(Filters.all, do_nothing)

                        ],
        ORDER_MAIN_CHOICE: [
                            MessageHandler(Filters.regex('^📥 Savatcha$'),
                                  order_basket_choice),
                            MessageHandler(Filters.regex('^📥 Корзинка$'),
                                  order_basket_choice),
                            MessageHandler(Filters.regex('^🍴 Menyu$'),
                                  order_menu_choice),
                            MessageHandler(Filters.regex('^🍴 Меню$'),
                                  order_menu_choice),
                            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  order_choice),
                            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  order_choice),
                            MessageHandler(Filters.text,
                                  order_list_products),
                            MessageHandler(Filters.all, do_nothing)

                        ],
        ORDER_PRODUCTS_CHOICE: [
                            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  show_order_main_choice),
                            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  show_order_main_choice),
                            MessageHandler(Filters.text,
                                  order_product),
                            MessageHandler(Filters.all, do_nothing)

                        ],
        ORDER_PRODUCT_NUMBERS: [
                            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  order_list_products_back),
                            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  order_list_products_back),
                            MessageHandler(Filters.regex('^[1-9]\d*$'),
                                  order_product_numbers),
                            MessageHandler(Filters.all, do_nothing)
                        ],
        ORDERING:[
                CallbackQueryHandler(manage_acquired),
                MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  show_order_main_choice),
                MessageHandler(Filters.regex('^O\'chirish$'),
                                  order_delete_basket_choice),
                MessageHandler(Filters.regex('^Очистить$'),
                                  order_delete_basket_choice),
                MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  show_order_main_choice),
                MessageHandler(Filters.regex('^🚀 Сделать заказ$'),
                                  confirm_order),
                MessageHandler(Filters.regex('^🚀 Buyurtma qilish$'),
                                  confirm_order),
                MessageHandler(Filters.all, do_nothing)
                ],
        CONFIRM_ORDER: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  order_basket_choice),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  order_basket_choice),
                      CallbackQueryHandler(save_extra_note, pattern='^extra_note$'),
                      CallbackQueryHandler(save_extra_phone, pattern='^extra_phone$'),
                      CallbackQueryHandler(cancel_choice, pattern='^cancel$'),
                      CallbackQueryHandler(save_choice, pattern='^save$'),
                      MessageHandler(Filters.all, do_nothing)],
        SAVING_EXTRA_NOTE: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  confirm_order),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  confirm_order),
                      MessageHandler(Filters.text, add_extra_note),
                      MessageHandler(Filters.all, do_nothing)],
        SAVING_EXTRA_PHONE: [MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  confirm_order),
                      MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  confirm_order),
                      MessageHandler(Filters.text, add_extra_phone),
                      MessageHandler(Filters.all, do_nothing)],
        DELIVERY_CHOICE: [
            MessageHandler(Filters.regex('^🚙 Yetkazib berish$'),
                                  order_delivery_choice),
            MessageHandler(Filters.regex('^🚙 Доставка$'),
                                  order_delivery_choice),
            MessageHandler(Filters.regex('^🏃 Olib ketish$'),
                                  order_selfdelivery_choice),
            MessageHandler(Filters.regex('^🏃 Самовывоз$'),
                                  order_selfdelivery_choice),
            MessageHandler(Filters.regex('^⬅️ Orqaga$'),
                                  main_choice),
            MessageHandler(Filters.regex('^⬅️ Назад$'),
                                  main_choice),
            MessageHandler(Filters.all, do_nothing)]

    },
    fallbacks=[MessageHandler(Filters.regex('^Done$'), cancel)],
    allow_reentry = True)
dp.add_handler(conv_handler)
dp.add_handler(MessageHandler(Filters.all, echo))
dp.add_error_handler(error)
set_timer()
updater.start_polling()
updater.idle()
