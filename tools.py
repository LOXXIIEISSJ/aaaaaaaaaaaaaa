import os
import random
import uuid
import smtplib
from email.mime.text import MIMEText
import yaml

def cRandPwd():
    z = ''
    for x in range(random.randrange(10, 20)):
        z += random.choice([
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C',
            'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P',
            'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'a', 'b', 'c',
            'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p',
            'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '!', '@', '#',
            '$', '%', '^', '&', '*'
        ])
    return z

def CreateUUID():
    return uuid.uuid4().hex

def sendEmail(to, content, title):
  return "Currently disabled"
  # msg = MIMEText(content, 'html')
  # msg['Subject'] = title
  # port = 587
  # email = os.environ['email']
  # password = os.environ['password']

  # with smtplib.SMTP('smtp-mail.outlook.com', port) as server:
  #     server.starttls()
  #     server.login(email, password)
  #     server.sendmail(email, to, msg.as_string())

def GetSettings():
  with open('settings.yaml', 'r') as file:
    return yaml.safe_load(file)

import datetime
import math
def days_between(d1):
    if d1 == None: return "n.d"
    d2 = datetime.datetime.utcnow()
    secs = (d2 - d1).total_seconds()
    mins = math.floor(secs / 60)
    hours = math.floor(mins / 60)
    days = math.floor(hours / 24)
    months = math.floor(days / 30)
    years = math.floor(months / 12)

    if abs(mins) < 6:
        return "Currently online"
    if abs(hours) < 1:
        return 'Active ' + str(round(mins)) + ' minute(s) ago'
    if abs(days) < 1:
        return 'Active ' + str(round(hours)) + ' hour(s)'
    if abs(months) < 1:
        return 'Active ' + str(round(days)) + ' day(s)'
    if abs(years) < 1:
        return 'Active ' + str(round(months)) + ' month(s)'
    if abs(years) > 1:
        return 'Active ' + str(round(years)) + ' year(s)'