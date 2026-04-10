import models
import repository as rp

import pandas as pd
from table2ascii import table2ascii
from datetime import date
import math

separator = "---------------------------------\n"


def message_configuration(title: str, content: str, footer: str):
    output = ""
    output += separator
    output += title + "\n"
    output += separator + "\n"
    output += content
    output += separator
    output += footer
    return output

def format_timedelta(td):
    days = td.days
    hours = td.seconds // 3600
    
    if days > 0:
        return f"あと{days}日"
    elif days == 0:
        return f"あと{hours}時間"
    else:
        return f"期限切れです"

def show_goals_table(goal_list):
    title = ""
    content_unfinished = ""
    content_finished = ""
    footer = ""
    title += f"**【 :trophy: ゴール一覧 】**"
    for goal in goal_list: # [["id", "ゴール名", "開始地点", "終了地点", "開始日", "終了日", "現在地点"], ...]
        _, goal_name, start_point, end_point, start_date, end_date, current_point = goal
        total_amount = end_point - start_point + 1
        ratio = current_point / total_amount
        book_icon = progress_to_bookicon(ratio)
        remaining_days = end_date - date.today()
        if ratio < 1:
            rows = [f"{book_icon} **{goal_name}**\n",
                    f"    進捗 `{make_progressbar(ratio, 6)}`",
                    f"    残り {current_point}/{total_amount} pts",
                    f"    完了予定 {end_date.strftime('%m/%d')}（{format_timedelta(remaining_days)}）"]
            content_unfinished += "\n".join(rows) + "\n\n"
        else:
            rows = [f"{book_icon} **{goal_name} --- 完了！！**\n"]
            content_finished += "\n".join(rows)
    content = content_unfinished + content_finished
    footer = ""
    return message_configuration(title, content, footer)


def show_daily_summary(task_list, ref_date):
    title = ""
    content = ""
    footer = ""
    title += f"**【 :date: { ref_date.strftime("%m/%d") }の進捗 】**"
    complete_count = 0
    loopcount = 0
    for task in task_list: # [[名前, 予定, 実績, 現在地点], ...]
        task_name, plan, actual, start_point, total_before = task
        ratio = actual / plan if plan > 0 else 0
        book_icon = progress_to_bookicon(ratio)

        today_start = start_point + total_before

        today_end = today_start + plan - 1
        
        row1 = f"{book_icon} **{task_name} ------ {actual}/{plan}**\n"
        row2 = f"          **今日やること:  {today_start}〜{today_end}**\n"
        row3 = f"          **進捗:**  `{make_progressbar(ratio, 6)}`\n"
        content += row1 + row2 + row3 + "\n"
        if ratio >= 1:
            complete_count += 1
        loopcount += 1

    footer = f":fire: **今日の総合進捗: {complete_count}/{loopcount}**"
    return message_configuration(title, content, footer)

def show_weekly_suggestion(suggestion_list): #[[goal_id, goal_name, daily_amount],...]
    title = ""
    content = ""
    footer = ""
    title += f"**【 :bulb: ウィークリー提案 】**"
    for s in suggestion_list:
        _, goal_name, daily_amount = s
        rows = [f"📌 **{goal_name}: {daily_amount} pts / 日**",]
        content += "\n".join(rows) + "\n\n"
    footer = ""
    return message_configuration(title, content, footer)

def make_progressbar(ratio, size):
    painted_block_num = round(size*ratio)
    output = "["
    if ratio < 1:
        for i in range(0, painted_block_num):
            output += "██"
        for i in range(0, size-painted_block_num):
            output += "░░"
    else:
        for i in range(0, size):
            output += "██"
    percent_display = "COMPLETE!!" if ratio == 1 else str(round(ratio*100)) + "%" 
    output += f"] { percent_display }"    
    return output

def progress_to_bookicon(progress_ratio):
    books = [":closed_book:", ":orange_book:", ":blue_book:", ":green_book:", ":bookmark:"] # 📕 📙 📘 📗 🔖 
    if progress_ratio < 0:
        return None
    elif progress_ratio < 0.25:
        output = books[0]
    elif progress_ratio < 0.5:
        output = books[1]
    elif progress_ratio < 0.75:
        output = books[2]
    elif progress_ratio < 1:
        output = books[3]
    elif progress_ratio >= 1:
        output = books[4]
    return output