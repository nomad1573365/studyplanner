from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.core.exception import DomainError

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
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        await rp.delete_user(user_id)
        await interaction.followup.send(f":white_check_mark:正常に削除されました。")
        logger.info("/barusu succeeded")

    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="about",description="このbotについて")
    async def about(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /about by {interaction.user.id}")
        s = """
            StudyPlanner v0.8.2-Alpha
            制作者: @のまど
            詳細: https://github.com/nomad1573365/studyplanner
        """
        await interaction.response.send_message(textwrap.dedent(s))
        
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.command(name="delete_msg",description="何らかのトラブルが生じ、botからのメッセージが残ってしまった場合、ここにIDを入れてください(dm限定)")
    async def delete_msg(self, interaction: discord.Interaction, message_id: str):
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
        
        
async def setup(bot):
    await bot.add_cog(GeneralCog(bot))



