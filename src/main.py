import services.services as sv
import ui.formatter as formatter
import repository as rp
import models as md
import db

import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncio
from discord.ext import commands, tasks
from discord import ui
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import datetime
from datetime import date
import textwrap


load_dotenv()
TOKEN = os.environ['TOKEN']

lock = asyncio.Lock()

intents = discord.Intents.default()
intents.message_content = True

class MyClient(discord.Client):
    user: discord.ClientUser

    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(
            self,
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
        )

    async def setup_hook(self):
        await db.init_db()
        await self.tree.sync()

client = MyClient(intents=intents)
tree = client.tree
scheduled_time = datetime.time(hour=0, minute=0)

@client.event
async def on_ready():
    Thread(target=run_health_check, daemon=True).start()
    today = date.today()
    print(f'{ today }: We have logged in as {client.user}')
    await tree.sync()
    activity = "おはようございます" 
    await client.change_presence(activity=discord.Game(activity))
    daily_update.start()

async def goal_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
    ) -> list[app_commands.Choice[str]]:
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    tasks = await sv.get_today_progresses(user_id, date.today())
    choices = []
    for task in tasks:
        goal_name = task[0]
        if current.lower() in goal_name.lower():
            choices.append(app_commands.Choice(name=goal_name, value=goal_name))
    return choices[:25]


@tree.command(name="make_goal",description="ゴール(参考書)の作成 dateはYYYY-MM-DDという形式で入れてください todayと入れると今日の日付が入ります")
async def command(interaction: discord.Interaction, goal_name: str, start_point: int, end_point: int, start_date: str, end_date: str):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    start_date = await sv.change_to_date(start_date)
    end_date = await sv.change_to_date(end_date)

    if await rp.add_goal(user_id, goal_name, start_point, end_point, start_date, end_date):
        await sv.apply_suggestions_to_daily_plan(user_id)
        await interaction.followup.send(":white_check_mark:ゴールが作成されました！")
    else:
        await interaction.followup.send(":x:年月日を正しく入力し、やり直してください:sob:")

@tree.command(name="rc",description="今日の勉強を記録(record)")
@app_commands.autocomplete(goal_name=goal_name_autocomplete)
async def command(interaction: discord.Interaction, goal_name: str, amount: int):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    if await sv.record_progress_by_name(user_id, goal_name, amount):
        await interaction.followup.send(f":white_check_mark:{ goal_name }({ amount })が記録されました！")
    else:
        await interaction.followup.send(f":x:タスク{ goal_name }を記録できませんでした。予定に{ goal_name }が存在するか確認した上、もう一度お試しください:sob:")

@tree.command(name="rc_forgot",description="記録し忘れた勉強量を、日付を指定して追加")
@app_commands.autocomplete(goal_name=goal_name_autocomplete)
async def command(interaction: discord.Interaction, target_date: str, goal_name: str, amount: int):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    target_date = await sv.change_to_date(target_date)
    if await sv.record_progress_by_name(user_id, goal_name, amount, target_date):
        await sv.apply_suggestions_to_daily_plan(user_id)
        await interaction.followup.send(f":white_check_mark:{ goal_name }({ amount })が記録されました！")
    else:
        await interaction.followup.send(f":x:タスク{ goal_name }を記録できませんでした。予定に{ goal_name }が存在するか確認した上、もう一度お試しください:sob:")


@tree.command(name="td",description="今日の予定・進捗の閲覧(today)")
async def command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    await sv.apply_suggestions_to_daily_plan(user_id)
    task_list = await sv.get_today_progresses(user_id, date.today())
    await interaction.followup.send(formatter.show_daily_summary(task_list, date.today()))


@tree.command(name="goals",description="ゴール一覧を表示")
async def command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    goal_list = await rp.get_user_goal_list(user_id, date.today())
    output = formatter.show_goals_table(goal_list)
    await interaction.followup.send(f"{ output }")

@tree.command(name="weight",description="今週の重み付けを設定(例:数学→1.5倍など)")
@app_commands.autocomplete(goal_name=goal_name_autocomplete)
async def command(interaction: discord.Interaction, goal_name: str, weight: float):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    today = date.today()
    if await sv.set_weekly_weight(user_id, goal_name, weight):
        await sv.apply_suggestions_to_daily_plan(user_id)
        await interaction.followup.send(f":white_check_mark:今週の{ goal_name }の重み付けを{ weight }倍にし、今日のリストに反映させました。")
    else:
        await interaction.followup.send(f":x:重み付けを設定できませんでした。weightの値が正であること、ゴールに{ goal_name }が存在すること確認した上、もう一度お試しください:sob:")


@tree.command(name="reset_weight",description="今週の重み付けをすべて1にリセットします")
async def command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    await rp.delete_user_weight(user_id)
    await sv.apply_suggestions_to_daily_plan(user_id)
    await interaction.followup.send(f":white_check_mark:重み付けをすべてリセットしました！")

@tree.command(name="barusu",description="※※※注意※※※データの初期化です")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
async def command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    if await rp.delete_user(user_id):
        await interaction.followup.send(f":white_check_mark:正常に削除されました。")
    else:
        await interaction.followup.send(f":x:削除に失敗しました。やり直してください。")


@tree.command(name="delete_goal",description="※注意※ゴールの削除です")
async def command(interaction: discord.Interaction, goal_name: str):
    await interaction.response.defer(ephemeral=True)
    user = rp.UserRepository()
    user_id = await user.ensure_user(str(interaction.user.id))
    if await rp.delete_goal(user_id, goal_name):
        await sv.apply_suggestions_to_daily_plan(user_id)
        await interaction.followup.send(f":white_check_mark:正常に削除されました。")
    else:
        await interaction.followup.send(f":x:削除に失敗しました。やり直してください。")
        
@tree.command(name="about",description="このbotについて")
async def command(interaction: discord.Interaction):
    s = """
        StudyPlanner v0.7.0-Alpha
        制作者: @のまど
        詳細: https://github.com/nomad1573365/studyplanner
    """
    await interaction.response.send_message(textwrap.dedent(s))
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()



@tasks.loop(time=scheduled_time)
async def daily_update():
    print(f"{date.today()}: 日次更新処理開始")
    user_records = await db.fetch_userlist()
    
    for record in user_records:
        user_id = record['id'] 
        try:
            success_count = await sv.apply_suggestions_to_daily_plan(user_id)
            print(f"User {user_id}: {success_count}件の予定を更新しました")
        except Exception as e:
            print(f"User {user_id} の更新中にエラー: {e}")
    print("すべてのsuggestionの更新が完了しました。")

client.run(TOKEN)