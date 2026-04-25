from src.core import services as sv, repository as rp
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.core.exception import DomainError
from src.core.exception import NotFoundError

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
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        await self.on_generate_dashboard(user_id)

    async def _delete_dashboard_messages(self, channel, user_id, msgid_list=None):
        dmr = rp.PgDashboardMsgRepository()
        if msgid_list is None:
            msgid_list = await dmr.fetch_user_msgid_list(user_id)
        for msgid in msgid_list:
            deleted_or_missing = False
            try:
                msg = await channel.fetch_message(msgid)
                await msg.delete()
                deleted_or_missing = True
            except discord.NotFound:
                logger.info(f"DASHBOARD DELETE: message already missing user_id={user_id} msg_id={msgid}")
                deleted_or_missing = True
            except Exception as e:
                logger.error(
                    f"DASHBOARD DELETE failed: user_id={user_id}, msg_id={msgid}, error={e}",
                    exc_info=(type(e), e, e.__traceback__),
                )
            if deleted_or_missing:
                try:
                    await dmr.delete_row_by_msgid(msgid)
                except Exception as e:
                    logger.error(
                        f"DASHBOARD ROW DELETE failed: user_id={user_id}, msg_id={msgid}, error={e}",
                        exc_info=(type(e), e, e.__traceback__),
                    )

    async def _generate_dashboard_unlocked(self, user_id, msgid_snapshot=None):
        user_class = await rp.PgUserRepository().find_by_id(user_id)
        if not user_class:
            logger.warning(f"DASHBOARD GENERATE skipped: user_id={user_id} not found")
            return
        user_id, username = user_class.id, user_class.name
        user = await self.bot.fetch_user(username)
        dmr = rp.PgDashboardMsgRepository()
        channel = await user.create_dm()

        synced_count = await sv.apply_suggestions_to_daily_plan(user_id)
        task_list = await rp.PgDailyTaskRepository().get_dailytasks(user_id, date.today())
        logger.info(
            f"DASHBOARD GENERATE user_id={user_id} synced={synced_count} tasks={len(task_list)}"
        )

        await self._delete_dashboard_messages(channel, user_id, msgid_snapshot)

        msg_top = await user.send(discord_ui.top_message(task_list))
        await dmr.update(msg_top.id, user_id, "TOP")
        
        for task in task_list:
            status_msg = await user.send(discord_ui.task_status(task))
            await dmr.update(status_msg.id, user_id, "STATUS", task.goal_id)
            view = TaskButton(task.goal_id, cog=self, timeout=None)
            button_msg = await user.send(view=view)
            await dmr.update(button_msg.id, user_id, "BUTTON", task.goal_id)
        
        msg_bottom = await user.send("今日もがんばりましょう！")
        await dmr.update(msg_bottom.id, user_id, "BOTTOM")
    
    @commands.Cog.listener()
    async def on_delete_dashboard(self, user_id):
        try:
            user_class = await rp.PgUserRepository().find_by_id(user_id)
            if not user_class:
                logger.warning(f"DASHBOARD DELETE skipped: user_id={user_id} not found")
                return
            user_id, username = user_class.id, user_class.name
            user = await self.bot.fetch_user(username)
            dmr = rp.PgDashboardMsgRepository()
            channel = await user.create_dm()
            
            lock = get_lock(user_id)
            async with lock:
                await self._delete_dashboard_messages(channel, user_id)
        except Exception as e:
            logger.error(
                f"DASHBOARD DELETE failed unexpectedly: user_id={user_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
                
        
    @commands.Cog.listener()
    async def on_generate_dashboard(self, user_id):
        try:
            lock = get_lock(user_id)
            async with lock:
                await self._generate_dashboard_unlocked(user_id)
        except Exception as e:
            logger.error(
                f"DASHBOARD GENERATE failed unexpectedly: user_id={user_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
                
    @commands.Cog.listener()
    async def on_update_dashboard(self, goal_id: int):
        try:
            user_class = await rp.PgUserRepository().find_by_goal(goal_id)
            user_id, username = user_class.id, user_class.name
            user = await self.bot.fetch_user(username)
            channel = await user.create_dm()
            
            dmr = rp.PgDashboardMsgRepository()
            
            lock = get_lock(user_id)
            if lock.locked():
                logger.info(
                    f"DASHBOARD UPDATE skipped because user lock is active: user_id={user_id}, goal_id={goal_id}"
                )
                return
            async with lock:
                top_msg_id = await dmr.fetch_msgid_by_userid(user_id, "TOP")
                if not top_msg_id:
                    logger.warning(f"DASHBOARD UPDATE fallback generate: TOP msg missing user_id={user_id}")
                    self.bot.dispatch("generate_dashboard", user_id)
                    return

                try:
                    top_msg = await channel.fetch_message(top_msg_id)
                except discord.NotFound:
                    logger.warning(f"DASHBOARD UPDATE fallback generate: TOP msg not found user_id={user_id}")
                    self.bot.dispatch("generate_dashboard", user_id)
                    return

                task_list = await rp.PgDailyTaskRepository().get_dailytasks(user_id, date.today())
                await top_msg.edit(content=discord_ui.top_message(task_list))
                
                status_msg_id = await dmr.fetch_msgid_by_goal_id(goal_id, "STATUS")
                if not status_msg_id:
                    logger.warning(
                        f"DASHBOARD UPDATE fallback generate: STATUS msg missing user_id={user_id}, goal_id={goal_id}"
                    )
                    self.bot.dispatch("generate_dashboard", user_id)
                    return

                try:
                    status_msg = await channel.fetch_message(status_msg_id)
                except discord.NotFound:
                    logger.warning(
                        f"DASHBOARD UPDATE fallback generate: STATUS msg not found user_id={user_id}, goal_id={goal_id}"
                    )
                    self.bot.dispatch("generate_dashboard", user_id)
                    return

                for task in task_list:
                    if task.goal_id == goal_id:
                        await status_msg.edit(content=discord_ui.task_status(task))
        except NotFoundError:
            logger.warning(f"DASHBOARD UPDATE skipped: goal_id={goal_id} has no owner user")
        except Exception as e:
            logger.error(
                f"DASHBOARD UPDATE failed unexpectedly: goal_id={goal_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
        
        

class TaskButton(discord.ui.View):
    def __init__(self, goal_id, cog: DashboardCog, timeout=180):
        super().__init__(timeout=timeout)
        self.goal_id = goal_id
        self.cog = cog
        
    @discord.ui.button(label="+1", style=discord.ButtonStyle.blurple)
    async def plus_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=1)
        try:
            await sv.record_progress_by_id(self.goal_id, 1)
            self.cog.bot.dispatch("update_dashboard", self.goal_id)
        except DomainError as e:
            await interaction.followup.send(str(e), ephemeral=True, delete_after=3)
        except Exception as e:
            logger.error(
                f"TASK_BUTTON +1 failed: goal_id={self.goal_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
            await interaction.followup.send("処理中にエラーが発生しました。", ephemeral=True, delete_after=3)

    @discord.ui.button(label="+5", style=discord.ButtonStyle.blurple)
    async def plus_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=1)
        try:
            await sv.record_progress_by_id(self.goal_id, 5)
            self.cog.bot.dispatch("update_dashboard", self.goal_id)
        except DomainError as e:
            await interaction.followup.send(str(e), ephemeral=True, delete_after=3)
        except Exception as e:
            logger.error(
                f"TASK_BUTTON +5 failed: goal_id={self.goal_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
            await interaction.followup.send("処理中にエラーが発生しました。", ephemeral=True, delete_after=3)
        
    @discord.ui.button(label="完了", style=discord.ButtonStyle.green)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=1)
        try:
            await rp.PgProgressRepository().make_task_finished(self.goal_id, date.today())
            self.cog.bot.dispatch("update_dashboard", self.goal_id)
        except Exception as e:
            logger.error(
                f"TASK_BUTTON finish failed: goal_id={self.goal_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
            await interaction.followup.send("処理中にエラーが発生しました。", ephemeral=True, delete_after=3)
        
    @discord.ui.button(label="-1", style=discord.ButtonStyle.red)
    async def minus_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("-# 処理中",ephemeral=True,delete_after=1)
        try:
            await sv.record_progress_by_id(self.goal_id, -1)
            self.cog.bot.dispatch("update_dashboard", self.goal_id)
        except DomainError as e:
            await interaction.followup.send(str(e), ephemeral=True, delete_after=3)
        except Exception as e:
            logger.error(
                f"TASK_BUTTON -1 failed: goal_id={self.goal_id}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
            await interaction.followup.send("処理中にエラーが発生しました。", ephemeral=True)
    
    
async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
