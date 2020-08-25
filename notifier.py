#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, base64, json, config
from decimal import Decimal
from io import BytesIO
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import mysql.connector

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

def remove_exponent(d):
    if d:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    else:
        return None
        
def encode_unicode(s):
    return base64.b64encode(s.encode()).decode()

def decode_unicode(s):
    if s:
        return base64.b64decode(s.encode()).decode()
    else:
        return ""

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
        
def start(update, context):
    update.message.reply_text('Parolni kiriting:')

def verify(update, context):
    sql="SELECT textvalue_uz from settings where keyword='notify_pass'"
    res = db_execute_get_more(sql)
    if res[0][0]:
        if str(res[0][0])==str(update.message.text):
            sql = "SELECT count(*) as cnt FROM staff WHERE userid=%s"
            data = (update.message.from_user.id, )
            res = db_execute_get_more(sql, data)
            if not (res[0][0]):
                sql = "INSERT INTO staff(userid, name) VALUES (%s, %s)"
                data = (update.message.from_user.id, encode_unicode(update.message.from_user.full_name))
                db_execute_get_more(sql, data, True)
            set_timer(update, context)
        else:
            update.message.reply_text("Xato parol")
    else:
        update.message.reply_text("Ulanishda xatolik")
            
            
def alarm(context):
    job = context.job
    sql = "SELECT sm.id, o.id, o.date, \
o.longitude, o.latitude, o.orientation, \
o.extra_phone, m.message, \
m.image, u.name, u.phone from staffmessage as sm \
left join orders as o on sm.orderid=o.id \
left join messages as m on sm.messageid=m.id \
left join staff as s on sm.staffid=s.id \
left join users as u on o.userid = u.id \
where s.userid=%s and TIME_TO_SEC(TIMEDIFF(NOW(), m.date))<8"
    data = (job.context, )
    res = db_execute_get_more(sql, data)
    if res:
        for i in res:
            j=0
            smid = i[j]
            j+=1
            oid = i[j]
            j+=1
            odate = i[j]
            j+=1
            olong = i[j]
            j+=1
            olat = i[j]
            j+=1
            oorient = decode_unicode(i[j])
            j+=1
            oextraphone = i[j]
            j+=1
            mmessage = i[j]
            j+=1
            mphoto = i[j]
            j+=1
            uname = decode_unicode(i[j])
            j+=1
            uphone = i[j]
            s ="Buyurtmachi haqida:" + '\n'
            s+="Buyurtma raqami: "+str(oid)+ '\n'
            s+="Buyurtma vaqti: "+str(odate)+ '\n'
            s+="Buyurtmachi manzili: "+str(oorient)+ '\n'
            s+="Buyurtmachi raqami: "+str(uphone)+ '\n'
            if oextraphone:
                s+="Buyurtmachining ikkinchi raqami: "+str(oextraphone)
            sql = "select (select uzbek from products where products.id = productid) as uzbek, value, (select price from products where products.id = productid) as price \
    from ordered_products where orderid = %s"
            data = (oid, )
            ordered_products = db_execute_get_more(sql, data)
            s += 'Xarajatlar:\n'
            s+='\n'
            overall = 0
            for i in ordered_products:
                overall +=i[1]*i[2]
                s+=i[0]+': '+str(i[1])+' x '+str(remove_exponent(i[2]))+' = '+ str(remove_exponent(i[1]*i[2])) +' so\'m\n'
            s+='\n'            
            s+="<b>Jami: "+str(remove_exponent(overall))+" so\'m</b>"            
            context.bot.send_message(job.context, text=s, parse_mode='HTML')
            
            if olat and olong:
                context.bot.send_location(job.context, float(olat), float(olong))            
            if mmessage:
                s="Admin tomondan qo'shimcha xabar: "+str(mmessage)+ '\n'
                context.bot.send_message(job.context, text=s)
            if mphoto:
                context.bot.send_photo(job.context, photo=BytesIO(mphoto), caption="Admin tomondan qo'shimcha rasm")
            
def set_timer(update, context):
    chat_id = update.message.chat_id
    due = 8
    if 'job' in context.chat_data:
        update.message.reply_text('Qayta ulanish...')
        old_job = context.chat_data['job']
        old_job.schedule_removal()
    new_job = context.job_queue.run_repeating(alarm, due, context=chat_id)
    context.chat_data['job'] = new_job
    update.message.reply_text('Muvaffaqiyatli ulanildi')

def main():
    updater = Updater(config.notify_token, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start,
                                  pass_args=True,
                                  pass_job_queue=True,
                                  pass_chat_data=True))
    dp.add_handler(MessageHandler(Filters.text, verify))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
