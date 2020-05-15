import discord
import asyncio
import logging
import cv2
import win32gui
import win32com.client
import traceback
import time
import numpy as np
import pyautogui
import configparser
import os
from PIL import ImageGrab
from discord.ext import commands, tasks
from datetime import datetime, date, timedelta
from tinydb import TinyDB, Query
from natsort import natsorted, ns
from matplotlib import pyplot as plt

db = TinyDB("db.json")
channel_query = Query()
prev_altar_exist = db.search(channel_query.prev_altar.exists())
if not prev_altar_exist:
    db.insert({"prev_altar": 0})

template = cv2.imread("title.png")
h, w = template.shape[:-1]
path = "D:\AeriaGames\\altar\\"
database_folder = "db"

bot = commands.Bot(command_prefix="!")
reset_hour = 11
reset_minute = 2
reset_second = 0
prediction_amount = 6


def template_matching(image1, image2):
    image1_height, image1_width, channel = image1.shape[::]
    image2_height, image2_witdh, channel = image2.shape[::]
    if (image1_height >= image2_height) and (image1_width >= image2_witdh):
        result = cv2.matchTemplate(image1, image2, cv2.TM_SQDIFF_NORMED)
    elif (image1_height <= image2_height) and (image1_width <= image2_witdh):
        result = cv2.matchTemplate(image2, image1, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    return 1 - min_val, min_loc


async def createprediction():
    try:
        d = datetime.today()
        result_list = []
        max_score = None
        width = 220
        height = 280
        dim = (width, height)

        files = os.listdir(database_folder)
        sortedfiles = natsorted(files, key=lambda y: y.lower())

        daily_image = cv2.imread(path + d.strftime("%d-%m-%Y") + ".png")
        daily_image_small = daily_image[63:339, 128:344]
        prev_altar = prev_altar_exist[0]["prev_altar"]

        def threshInv(image):
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            contours = []
            base_t_val = 100
            t_val = base_t_val
            while True:
                (T, threshInv) = cv2.threshold(gray, t_val, 255, cv2.THRESH_BINARY_INV)
                (cnts, _) = cv2.findContours(
                    threshInv.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                t_val = t_val + 1
                if len(cnts) < 50:
                    break
            for c in cnts:
                (x, y, w, h) = cv2.boundingRect(c)
                rec = image[y : y + h, x : x + w]
                rec_height, rec_width, channel = rec.shape[::]
                if rec_height < 25 or rec_width < 25 or len(cnts) < 42:
                    continue
                if rec_height < 34 or rec_width < 34:
                    rec = cv2.resize(rec, (34, 34), interpolation=cv2.INTER_CUBIC)
                elif rec_height > 34 or rec_width > 34:
                    rec = cv2.resize(rec, (34, 34), interpolation=cv2.INTER_AREA)
                contours.append(c)
            return contours

        def generate_prediction(current_image):
            image_names = []
            images = []
            max_height = 0
            total_width = 0
            for r in range(prediction_amount):
                filename = database_folder + "\\" + str(current_image + r + 1) + ".png"
                if (current_image + r + 1) > 633:
                    break
                image_names.append(filename)
            for name in image_names:
                image = cv2.imread(name)
                image_height, image_width, channel = image.shape[::]
                if image_height <= 280 or image_width <= 220:
                    image = cv2.resize(image, dim, interpolation=cv2.INTER_CUBIC)
                else:
                    image = cv2.resize(image, dim, interpolation=cv2.INTER_AREA)
                images.append(image)
                if images[-1].shape[0] > max_height:
                    max_height = images[-1].shape[0]
                total_width += images[-1].shape[1]
            current_x = 0
            final_image = np.zeros(
                (max_height, total_width + ((prediction_amount - 1) * 15), 3),
                dtype=np.uint8,
            )
            for image in images:
                final_image[
                    : image.shape[0], current_x : image.shape[1] + current_x, :
                ] = image
                current_x += image.shape[1] + 15
            cv2.imwrite("prediction.png", final_image)
            db.update(
                {"prev_altar": current_image}, channel_query.prev_altar == prev_altar
            )

        today_prediction_number = prev_altar + 1
        today_prediction_path = (
            database_folder + "\\" + str(today_prediction_number) + ".png"
        )
        today_prediction = cv2.imread(today_prediction_path)
        score, _ = template_matching(daily_image, today_prediction)
        if score >= 0.9 and prev_altar != 0:
            generate_prediction(today_prediction_number)
            print("Still in rotation")
            return 1
        else:
            for file in sortedfiles:
                filename = database_folder + "\\" + os.fsdecode(file)
                db_image = cv2.imread(filename)
                score, _ = template_matching(daily_image, db_image)

                if score >= 0.9:
                    # print("Confidence: ", score)
                    # print("Name: ", filename)
                    cnts1 = threshInv(daily_image_small)
                    cnts2 = threshInv(db_image)
                    x = 0
                    for i in range(len(cnts1)):
                        (x1, y1, w1, h1) = cv2.boundingRect(cnts1[i])
                        (x2, y2, w2, h2) = cv2.boundingRect(cnts2[i])
                        rec1 = daily_image_small[y1 : y1 + h1, x1 : x1 + w1]
                        rec2 = db_image[y2 : y2 + h2, x2 : x2 + w2]
                        score2, _ = template_matching(rec1, rec2)
                        if score2 >= 0.8:
                            x = i
                        else:
                            break
                    print("Confidence: ", score)
                    if x > 39:
                        print("SUCC: ", filename)
                        result_list.append(int(os.path.splitext(os.fsdecode(file))[0]))
                    else:
                        print("FAIL: ", filename)
                    print("-------------------")

            if len(result_list) != 0:
                generate_prediction(result_list[0])
                print("Rotation Changed")
                return 1
            else:
                return 0
    except:
        print(traceback.format_exc())


async def post_altar(channel_id, d):
    channel = bot.get_channel(channel_id)
    await channel.send(
        d.strftime("%d-%m-%Y"), file=discord.File("today_altar.png"),
    )


@tasks.loop(hours=24)
async def find_window():
    try:
        found = 0
        toplist, winlist = [], []

        def enum_cb(hwnd, results):
            winlist.append((hwnd, win32gui.GetWindowText(hwnd)))

        win32gui.EnumWindows(enum_cb, toplist)
        ee_window = [
            (hwnd, title) for hwnd, title in winlist if "eternal" in title.lower()
        ]
        for window in ee_window:
            if found == 1:
                break
            while found == 0:
                hwnd = window[0]
                pyautogui.press("alt")
                win32gui.SetForegroundWindow(hwnd)
                pyautogui.press("alt")
                bbox = win32gui.GetWindowRect(hwnd)
                await asyncio.sleep(1)
                img = ImageGrab.grab(bbox)
                opencv_img = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
                opencv_img_h, opencv_img_w = opencv_img.shape[:-1]
                if opencv_img_h == 768 and opencv_img_w == 1366:
                    score, min_loc = template_matching(opencv_img, template)
                    top_x = min_loc[0]
                    top_y = min_loc[1]
                    bottom_x = min_loc[0] + w
                    bottom_y = min_loc[1] + h
                    top_left = min_loc
                    bottom_right = (bottom_x, bottom_y)
                    # cv2.rectangle(opencv_img, top_left, bottom_right, 255, 1)
                    if score >= 0.99:
                        found = 1
                        d = datetime.today()
                        cropped_smol = opencv_img[
                            bottom_y + 42 : bottom_y + 318, top_x + 128 : top_x + 344
                        ]
                        cropped_big = opencv_img[top_y : top_y + 411, top_x:bottom_x]
                        cv2.imwrite(path + d.strftime("%d-%m-%Y") + ".png", cropped_big)
                        cv2.imwrite("today_altar.png", cropped_smol)
                        await asyncio.sleep(0.3)
                        prediction = await createprediction()
                        print(path + d.strftime("%d-%m-%Y") + ".png")
                        await asyncio.sleep(0.3)
                        for item in db:
                            if "prev_altar" in item:
                                continue
                            channel = bot.get_channel(item["channel"])
                            await channel.send(
                                d.strftime("%d-%m-%Y"),
                                file=discord.File("today_altar.png"),
                            )
                            if item["future_altar"] == 1 and prediction == 1:
                                await channel.send(file=discord.File("prediction.png"))
                            elif prediction == 0:
                                await channel.send("Cant predict this altar")
                    else:
                        await asyncio.sleep(5)
    except:
        print(traceback.format_exc())


@find_window.before_loop
async def find_window_before():
    try:
        await bot.wait_until_ready()
        now = datetime.now()
        reset = datetime.now().replace(
            hour=reset_hour, minute=reset_minute, second=reset_second, microsecond=0
        )
        if reset < now:
            reset = reset + timedelta(days=1)
        wait_time = (reset - now).total_seconds()
        print(wait_time)
        await asyncio.sleep(wait_time)
    except:
        print(traceback.format_exc())


@bot.command()
async def posthere(ctx):
    if ctx.author.id == 114881658045464581:
        res = db.search(channel_query.channel == ctx.channel.id)
        if len(res) == 0:
            db.insert({"channel": ctx.message.channel.id, "future_altar": 0})
            now = datetime.now()
            today_reset = datetime.now().replace(
                hour=reset_hour, minute=reset_minute, second=0, microsecond=0
            )
            if now.hour >= reset_hour and now.hour <= 23:
                await post_altar(ctx.channel.id, now)
            else:
                yesterday = now.replace(day=now.day - 1)
                await post_altar(ctx.channel.id, yesterday)
        else:
            await ctx.channel.send("This channel already registered.")
    else:
        await ctx.channel.send("Only <@114881658045464581> can use the bot commands")


@bot.command()
async def enableprediction(ctx):
    if ctx.author.id == 114881658045464581:
        res = db.search(channel_query.channel == ctx.channel.id)
        if res[0]["future_altar"] == 0:
            db.update({"future_altar": 1}, channel_query.channel == ctx.channel.id)
            await ctx.channel.send("Enabled")
        else:
            await ctx.channel.send("Prediction already enabled")
    else:
        await ctx.channel.send("Only <@114881658045464581> can use the bot commands")


@bot.command()
async def postprediction(ctx):
    if ctx.author.id == 114881658045464581:
        await ctx.channel.send(file=discord.File("prediction.png"))
    else:
        await ctx.channel.send("Only <@114881658045464581> can use the bot commands")


@bot.command()
async def disableprediction(ctx):
    if ctx.author.id == 114881658045464581:
        res = db.search(channel_query.channel == ctx.channel.id)
        if res[0]["future_altar"] == 1:
            db.update({"future_altar": 0}, channel_query.channel == ctx.channel.id)
            await ctx.channel.send("Prediction disabled")
        else:
            await ctx.channel.send("Prediction already disabled")
    else:
        await ctx.channel.send("Only <@114881658045464581> can use the bot commands")


@bot.command()
async def dontpost(ctx):
    if ctx.author.id == 114881658045464581:
        res = db.search(channel_query.channel == ctx.channel.id)
        if len(res) > 0:
            for item in db:
                db.remove(channel_query.channel == ctx.channel.id)
        else:
            await ctx.channel.send("This channel not registered.")


@bot.command()
async def delete(ctx, channel_id: str, msg_id: str):
    if ctx.author.id == 114881658045464581:
        await bot.http.delete_message(channel_id, msg_id)


@bot.command()
async def what(ctx):
    embed = discord.Embed(
        title="EE Altar Bot",
        description="This bot will post EE altar everyday at the time it reset. Developed by <@114881658045464581>",
        color=0x9D2CA7,
    )
    await ctx.channel.send(embed=embed)


@bot.event
async def on_ready():
    bot.remove_command("help")
    await bot.change_presence(activity=discord.Game(name="!what"))


@bot.event
async def on_message(message):
    # await client.process_commands(message)
    print("Message from {0.author}: {0.content}".format(message))
    if not message.author.bot:
        await bot.process_commands(message)


find_window.start()
bot.run("YOUR DISCORD TOKEN HERE")
