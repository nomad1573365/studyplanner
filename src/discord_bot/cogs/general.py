from src.core import services as sv, repository as rp
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.core.exception import DomainError
from src.core.models import *

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands

import datetime
from datetime import date
import textwrap


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="barusu",description="※※※注意※※※データの初期化です")
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    async def delete_user(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /barusu by {interaction.user.id}")
        await interaction.response.send_message("すべてのデータを消去する場合は、下のボタンを押してください。",view=DeleteButton(self), ephemeral=True)

    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="about",description="このbotについて")
    async def about(self, interaction: discord.Interaction):
        s = """
            StudyPlanner v1.0.0-Beta
            制作者: @のまど
            詳細: https://github.com/nomad1573365/studyplanner
        """
        await interaction.response.send_message(textwrap.dedent(s),ephemeral=True)
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="help",description="使い方を表示します")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 StudyPlanner 使い方ガイド",
            description="ようこそ！これは期日までに終わるように今日やるべき量を自動で計算するBotです！",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="まず最初にすること",
            value=(
                ":one: `/make_goal` で目標（主に参考書）を登録\n"
                ":two: 勉強し、DMのダッシュボードでポチポチ記録(表示されなければ、`/dashboard_refresh`を実行してください)\n"
            ),
            inline=False
        )

        embed.add_field(
            name=":tools: 主要コマンド",
            value=(
                "`/rc`: 進捗の記録\n"
                "`/weight`: 重み付けを変更\n"
                "`/edit_goal`: 目標の修正\n"
                "`/dashboard_refresh`: ダッシュボードの再生成"
            ),
            inline=True
        )

        embed.add_field(
            name=":dizzy: その他",
            value=(
                "`/barusu`: ユーザーの初期化\n"
                "\n"
                "詳細は[こちら](https://github.com/nomad1573365/studyplanner)"
            ),
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.command(name="delete_msg",description="何らかのトラブルが生じ、botからのメッセージが残ってしまった場合、ここにIDを入れてください(dm限定)")
    async def delete_msg(self, interaction: discord.Interaction, message_id: str):
        logger.info(f"COMMAND: /delete_msg by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        if not str(message_id).isdigit():
            raise DomainError("message_id は数字のみで入力してください。")
        msg_id_int = int(message_id)
        channel = await interaction.user.create_dm()
        try:
            msg = await channel.fetch_message(msg_id_int)
            await msg.delete()
            await interaction.followup.send("正常に削除されました。")
        except discord.NotFound:
            await interaction.followup.send("指定されたメッセージが見つかりませんでした。")
            
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="set_objective",description="目標を設定します(例:次の模試で総合偏差値〇〇以上)")
    async def set_objective(self, interaction: discord.Interaction, objective: str):
        await interaction.response.defer(ephemeral=True)
        user = await rp.PgUserRepository().find_by_name(str(interaction.user.id))
        objective_class = Objective(user.id, objective)
        await rp.PgObjectiveRepository().save(objective_class)
        await interaction.followup.send(":white_check_mark:正常に設定されました！",ephemeral=True)

class DeleteButton(discord.ui.View):
    def __init__(self, cog: GeneralCog, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        
    @discord.ui.button(label="消去する", style=discord.ButtonStyle.red)
    async def plus_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=1)
        try:
            user = await sv.ensure_user(str(interaction.user.id))
            await rp.PgUserRepository().delete(user)
            await interaction.followup.send(f":white_check_mark:正常に削除されました。ご利用ありがとうございました。")
        except DomainError as e:
            await interaction.followup.send(str(e), ephemeral=True, delete_after=3)
        except Exception as e:
            logger.error(
                f"DELETING USER failed: user_id={user.id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
            await interaction.followup.send("処理中にエラーが発生しました。", ephemeral=True, delete_after=3)
        
async def setup(bot):
    await bot.add_cog(GeneralCog(bot))



