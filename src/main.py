import services.services as sv
import ui.formatter as formatter
import repository as rp
import models as md

import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncio
from discord.ext import commands, tasks
from discord import ui
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
from datetime import date


load_dotenv()
TOKEN = os.environ['TOKEN']

lock = asyncio.Lock()

intents = discord.Intents.all()
intents.message_content = True
client = discord.Client(intents=intents)

tree = app_commands.CommandTree(client)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()


@client.event
async def on_ready():
    Thread(target=run_health_check, daemon=True).start()
    today = date.today()
    print(f'{ today }: We have logged in as {client.user}')
    await tree.sync()
    activity = "おはようございます" 
    await client.change_presence(activity=discord.Game(activity))


@tree.command(name="make_goal",description="ゴール(参考書)の作成 dateはYYYY-MM-DDという形式で入れてください todayと入れると今日の日付が入ります")
async def command(interaction: discord.Interaction, goal_name: str, start_point: int, end_point: int, start_date: str, end_date: str):
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    today = date.today()
    if start_date == "today":
        start_date = today.strftime("%Y-%m-%d")
    if end_date == "today":
        end_date = today.strftime("%Y-%m-%d")
    start_date = date.strptime(start_date, '%Y-%m-%d')
    end_date = date.strptime(end_date, '%Y-%m-%d')

    if rp.add_goal(user_id, goal_name, start_point, end_point, start_date, end_date):
        await interaction.response.send_message("ゴールが作成されました！")
    else:
        await interaction.response.send_message("年月日を正しく入力し、やり直してください:sob:")


@tree.command(name="add_todo",description="今日の予定を手動で追加")
async def command(interaction: discord.Interaction, goal_name: str, amount: int):
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    add_plan = rp.add_daily_plan(user_id, goal_name, amount)
    if add_plan:
        await interaction.response.send_message(f"新規タスク、{ goal_name }({ amount })が今日の予定に追加されました！")
    else:
        await interaction.response.send_message(f"予定を追加できませんでした。ゴールに{ goal_name }が存在するか確認した上、もう一度お試しください:sob:")


@tree.command(name="record",description="今日の勉強を記録")
async def command(interaction: discord.Interaction, goal_name: str, amount: int):
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    if sv.record_progress_by_name(user_id, goal_name, amount):
        await interaction.response.send_message(f"{ goal_name }({ amount })が記録されました！")
    else:
        await interaction.response.send_message(f"タスク{ goal_name }を記録できませんでした。予定に{ goal_name }が存在するか確認した上、もう一度お試しください:sob:")


@tree.command(name="today",description="今日の予定・進捗の閲覧")
async def command(interaction: discord.Interaction):
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    today = date.today()
    task_list = sv.get_today_progresses(user_id, today)
    await interaction.response.send_message(formatter.show_daily_summary(task_list))


@tree.command(name="goals",description="ゴール一覧")
async def command(interaction: discord.Interaction):
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    goal_list = rp.get_user_goal_list(user_id)
    output = formatter.show_goals_table(goal_list)
    await interaction.response.send_message(f"{ output }")

@tree.command(name="weekly_sg", description="今週の進捗から、今日のノルマを提案します")
async def command(interaction: discord.Interaction):
    await interaction.response.defer()
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    today = date.today()
    suggestion_list = sv.get_weekly_suggestion(user_id, today)
    output = formatter.show_weekly_suggestion(suggestion_list)
    await interaction.followup.send(f"{output}")


@tree.command(name="weight",description="今週の重み付けを設定(例:数学→1.5倍など)")
async def command(interaction: discord.Interaction, goal_name: str, weight: float):
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    today = date.today()
    if sv.set_weekly_weight(user_id, goal_name, weight):
        await interaction.followup.send(f":white_check_mark:今週の{ goal_name }の重み付けを{ weight }倍にしました。todoリストに反映させるには改めて/syncを実行してください。")
    else:
        await interaction.followup.send(f"重み付けを設定できませんでした。{ goal_name }が存在するか確認した上、もう一度お試しください:sob:")


@tree.command(name="sync",description="/weekly_sgを基に今日のタスクを自動設定(※/weekly_sgを先に実行し、確認することを推奨)")
async def command(interaction: discord.Interaction):
    await interaction.response.defer()
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    count = sv.apply_suggestions_to_daily_plan(user_id)
    if count > 0:
        await interaction.followup.send(f":white_check_mark:{count}件の目標を今日の予定に同期しました！\n`/today` で確認して、今日も一日頑張りましょう！")
    else:
        await interaction.followup.send(":thinking:同期する項目がありませんでした。（すべてのノルマが完了しているか、0ページです）")


@tree.command(name="barusu",description="※※※注意※※※データの初期化です")
async def command(interaction: discord.Interaction):
    await interaction.response.defer()
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    if rp.delete_user(user_id):
        await interaction.followup.send(f"正常に削除されました。")
    else:
        await interaction.followup.send(f"削除に失敗しました。やり直してください。")


@tree.command(name="delete_goal",description="※注意※ゴールの削除です")
async def command(interaction: discord.Interaction, goal_name: str):
    await interaction.response.defer()
    user = rp.UserRepository()
    user_id = user.ensure_user(interaction.user.id)
    if rp.delete_goal(user_id, goal_name):
        await interaction.followup.send(f"正常に削除されました。")
    else:
        await interaction.followup.send(f"削除に失敗しました。やり直してください。")


client.run(TOKEN)