# bot.py
import os
import random

import discord
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy import insert
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound
import pymysql

import shlex

import sys

from datetime import datetime
import dateutil
from dateutil import parser

import difflib

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
CHANNEL_MONITOR = os.getenv('DISCORD_CHANNEL')
DB_SERVER = os.getenv('DB_SERVER')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_DB = os.getenv('DB_DB')


# connect to DB
db_connection_str = 'mysql+pymysql://'+DB_USER+':'+DB_PASS+'@'+DB_SERVER+'/'+DB_DB
db_connection = create_engine(db_connection_str, pool_recycle=3600)
connection = db_connection.connect()





intents = discord.Intents.all()
intents.members = True
intents.messages = True

client = discord.Client(intents=intents)

def get_player_absences(member_id, member_name):
    # get player current absences
    sql = text("""SELECT cap.date_start, cap.date_end, cac.code, cac.description as code_desc, cap.description
            FROM cal_attendance_plans cap
            LEFT JOIN cal_attendance_codes cac ON cap.type = cac.code
            WHERE 
            cap.del = 0
            AND (cap.date_end > CURDATE())
            AND cap.member_id = :mid
            ORDER BY date_start asc""")
    result = connection.execute(sql, {'mid' : member_id})
    rows = result.fetchall()
    
    #### Create the initial embed object ####
    embed=discord.Embed(title="LMC Attendance", url="https://facutvivas.com/lmc_raid_log/index.php/welcome/attendance_calendar", color=0x109319)

    # Add author, thumbnail, fields, and footer to the embed
    embed.add_field(name="Absences for " + member_name, value="", inline=False)
    
    if len(rows) == 0:
        embed.add_field(name="No absences scheduled", value="", inline=False)
    else:
        for row in rows:
            datestart_fmt = row[0].strftime('%m/%d/%Y')
            dateend_fmt = row[1].strftime('%m/%d/%Y')
            msg =  datestart_fmt + " - " + dateend_fmt + " : " + row[4]
            embed.add_field(name=row[3], value=msg, inline=False)

    embed.set_footer(text="LMC Attendance Bot")
    
    return embed
    
def get_help_msg(title, msg):
    #### Create the initial embed object ####
    embed=discord.Embed(title="LMC Attendance", url="https://facutvivas.com/lmc_raid_log/index.php/welcome/attendance_calendar", color=0x109319)

    # Add author, thumbnail, fields, and footer to the embed
    
    embed.add_field(name=title, value=msg, inline=False)
    embed.set_footer(text="LMC Attendance Bot")
    
    return embed


@client.event
async def on_ready():
    for guild in client.guilds:
        if guild.name == GUILD:
            break

    print(
        f'{client.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})\n'
    )

    members = '\n - '.join([member.name for member in guild.members])
    print(f'Guild Members:\n - {members}')
    # members = [member.name for member in guild.members]
    # for member in members:
        
    
    
@client.event
async def on_message(message):
    author = message.author.name
    channel = message.channel.name
    content = message.content
    
    if author == client.user:
        # print("bot message")
        return
        
    if channel != CHANNEL_MONITOR:
        # print("Wrong channel", channel, CHANNEL_MONITOR)
        # print('\n'.join(difflib.ndiff([channel], [CHANNEL_MONITOR])))
        return
    
    if not content.startswith('$'):
        return
        
    # print(message.author.name, message.channel, message.content)
    
    # -- $character charactername
    if content.startswith('$character'):
        params = shlex.split(content)
        
        if len(params) != 2:
            out_msg = """
Character command should be as follows:
$character charactername
        """
            await message.channel.send(out_msg)
            return
            
        character = params[1]
        
        await message.channel.send(character)
        return
    
    # -- handle not known
    # sql = text("""SELECT m.name, m.member_id
                # FROM members m
                # WHERE 
                # m.del = 0
                # AND m.discord_name LIKE :dn""")
    # result = connection.execute(sql, {'dn' : author})
    # rowtest = result.scalar()
            
    # if rowtest == None:
        # out_msg = """
# I don't recognize you.  Set your channel with the command:\n
# $character charactername
        # """
        # await message.channel.send(out_msg)
        # return
    
    # -- $absent set character datestart dateend description
    if content.startswith('$absent') or content.startswith('$preferbench'):
        params = shlex.split(content)
        
        title = "Attendance Commands"
        msg = """
Attendance commands should be as follows:
$absent set character datestart dateend description
$preferbench set character datestart dateend description
$absent clear character
        """
        
        if len(params) < 3:
            help_msg = msg
            help_embed = get_help_msg(title, help_msg)
            await message.channel.send(embed=help_embed)
            return
            
        command = params[0]
        cmd_type = params[1]
        character = params[2]
        
        # check if char is found
        sql = text("""SELECT m.name, m.member_id
                    FROM members m
                    WHERE 
                    m.del = 0
                    AND m.name LIKE :dn""")
        result = connection.execute(sql, {'dn' : character})
        
        try:
            charrow = result.one()
        except (NoResultFound, MultipleResultsFound) as e:
            help_msg = "Could not find the character " + character + ".\n" + msg
            help_embed = get_help_msg(title, help_msg)
            await message.channel.send(embed=help_embed)
            return
        
        member_id = charrow[1]
        
        print("Found",character,str(member_id))
        
        # handle setting
        if cmd_type == "set":
            try:
                datestart = parser.parse(params[3])
                dateend = parser.parse(params[4])
            except dateutil.parser.ParserError:
                help_msg = "I did not recognize your date format.\n" + msg
                help_embed = get_help_msg(title, help_msg)
                await message.channel.send(embed=help_embed)
                return
            datestart_fmt = datestart.strftime('%Y-%m-%d')
            dateend_fmt = dateend.strftime('%Y-%m-%d')
            reason = params[5]
            
            type = "AB" if command == "$absent" else "PB"
            
            #update DB
            sql = text("""INSERT INTO cal_attendance_plans (member_id, date_start, date_end, type, description)
                    VALUES (:mid, :ds, :de, :ty, :desc)
                    ON DUPLICATE KEY UPDATE type=:ty, description=:desc, del=0""")
                    
            # print(sql)
            
            sql_params = {
                'mid' : member_id,
                'ds' : datestart_fmt,
                'de' : dateend_fmt,
                'ty' : type,
                'desc' : reason,
            }
            
            id = connection.execute(sql, sql_params)
            connection.commit()
            
            print("Attendance Added  = ",id.rowcount, character, sql_params)
            
            absence_embed = get_player_absences(member_id, character)            
            await message.channel.send(embed=absence_embed)
            return
        
        # handle clearing
        if cmd_type == "clear":
            #update DB
            sql = text("""UPDATE cal_attendance_plans 
                    SET del = 1
                    WHERE member_id = :mid 
                    AND (date_end > CURDATE())""")
                    
            # print(sql)
            
            sql_params = {
                'mid' : member_id,
            }
            
            id = connection.execute(sql, sql_params)
            connection.commit()
            
            print("Attendance cleared for", character, sql_params)
        
            absence_embed = get_player_absences(member_id, character)            
            await message.channel.send(embed=absence_embed)
            return
        
    # if it got here, misformatted send help msg
    title = "Bad Command"
    msg = """
Attendance commands should be as follows:
$absent set character datestart dateend description
$preferbench set character datestart dateend description
$absent clear character
    """
    help_embed = get_help_msg(title, msg)
    await message.channel.send(embed=help_embed)
    return

client.run(TOKEN)
