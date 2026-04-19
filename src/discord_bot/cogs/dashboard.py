from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.core.exception import DomainError

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands
from datetime import date
from src.utils.async_tools import get_lock



class DashboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="dashboard_refresh",description="ダッシュボードを再生成します")
    async def dashboard_refresh(self, interaction: discord.Interaction):
        await interaction.response.send_message("ダッシュボードを再生成します。完了までお待ちください。",ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        await self.on_delete_dashboard(user_id)
        await self.on_generate_dashboard(user_id)
    
    @commands.Cog.listener()
    async def on_delete_dashboard(self, user_id):
        user_class = await rp.PgUserRepository().find_by_id(user_id)
        user_id, username = user_class.id, user_class.name
        user = await self.bot.fetch_user(username)
        dmr = rp.PgDashboardMsgRepository()
        channel = await user.create_dm()
        
        lock = get_lock(user_id)
        async with lock:
            msgid_list = await dmr.fetch_user_msgid_list(user_id)
            for msgid in msgid_list:
                try:
                    msg = await channel.fetch_message(msgid)
                    await msg.delete()
                except discord.NotFound:
                    await dmr.delete_row_by_msgid(msgid)
                
        
    @commands.Cog.listener()
    async def on_generate_dashboard(self, user_id):
        user_class = await rp.PgUserRepository().find_by_id(user_id)
        user_id, username = user_class.id, user_class.name
        user = await self.bot.fetch_user(username)
        dmr = rp.PgDashboardMsgRepository()
        
        task_list = await rp.PgDailyTaskRepository().get_dailytasks(user_id, date.today())

        lock = get_lock(user_id)
        async with lock:
            msg_top = await user.send(discord_ui.top_message(task_list))
            await dmr.update(msg_top.id, user_id, "TOP")
            
            for task in task_list:
                status_msg = await user.send(discord_ui.task_status(task))
                await dmr.update(status_msg.id, user_id, "STATUS", task.goal_id)
                view = TaskButton(task.goal_id, cog=self, timeout=None)
                button_msg = await user.send(view=view)
                await dmr.update(button_msg.id, user_id, "BUTTON", task.goal_id)
                
    @commands.Cog.listener()
    async def on_update_dashboard(self, goal_id: int):
        user_class = await rp.PgUserRepository().find_by_goal(goal_id)
        user_id, username = user_class.id, user_class.name
        user = await self.bot.fetch_user(username)
        channel = await user.create_dm()
        
        dmr = rp.PgDashboardMsgRepository()
        
        lock = get_lock(user_id)
        async with lock:
            top_msg_id = await dmr.fetch_msgid_by_userid(user_id, "TOP")
            top_msg = await channel.fetch_message(top_msg_id)
            task_list = await rp.PgDailyTaskRepository().get_dailytasks(user_id, date.today())
            await top_msg.edit(content=discord_ui.top_message(task_list))
            
            status_msg_id = await dmr.fetch_msgid_by_goal_id(goal_id, "STATUS")
            status_msg = await channel.fetch_message(status_msg_id)
            for task in task_list:
                if task.goal_id == goal_id:
                    await status_msg.edit(content=discord_ui.task_status(task))
        
        

class TaskButton(discord.ui.View):
    def __init__(self, goal_id, cog: DashboardCog, timeout=180):
        super().__init__(timeout=timeout)
        self.goal_id = goal_id
        self.cog = cog
        
    @discord.ui.button(label="+1", style=discord.ButtonStyle.blurple)
    async def plus_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=0.1)
        await sv.record_progress_by_id(self.goal_id, 1)
        self.cog.bot.dispatch("update_dashboard", self.goal_id)

    @discord.ui.button(label="+5", style=discord.ButtonStyle.blurple)
    async def plus_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=0.1)
        await sv.record_progress_by_id(self.goal_id, 5)
        self.cog.bot.dispatch("update_dashboard", self.goal_id)
        
    @discord.ui.button(label="完了", style=discord.ButtonStyle.green)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=0.1)
        await rp.make_task_finished(self.goal_id, date.today())
        self.cog.bot.dispatch("update_dashboard", self.goal_id)
        
    @discord.ui.button(label="-1", style=discord.ButtonStyle.red)
    async def minus_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=0.1)
        await sv.record_progress_by_id(self.goal_id, -1)
        self.cog.bot.dispatch("update_dashboard", self.goal_id)
    
    
async def setup(bot):
    await bot.add_cog(DashboardCog(bot))